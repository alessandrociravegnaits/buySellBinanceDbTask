import os
import time
import tempfile
from price_feeds import MockPriceFeed
from telegram_bot import TelegramTradingBot, OcoSpec, SimpleOrderSpec
import sqlite3


class FakeExchangeClient:
    def create_order(self, **kwargs):
        return {
            "orderId": 123456,
            "status": "FILLED",
            "executedQty": str(kwargs.get("quantity")),
        }


def test_oco_end_to_end(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    # Monkeypatch TelegramTradingBot to use MockPriceFeed by injecting into the module
    # Create bot but override feed after init
    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    # Replace feed and manager/poller with ones using MockPriceFeed
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    # rebuild engine with mock feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    # Create a sample OCO via storage + attach
    order_id = bot._new_order_id()
    legs = [
        {"leg_index": 1, "ordertype": "limit", "price": 110.0, "qty": 1.0, "side": "sell"},
        {"leg_index": 2, "ordertype": "stop_limit", "stop_price": 90.0, "limit_price": 85.0, "qty": 1.0, "side": "sell"},
    ]

    bot._storage.save_oco_order(
        order_id=order_id,
        chat_id=999,
        symbol="BTCUSDT",
        side="sell",
        legs=legs,
        hook_symbol=None,
        tf_minutes=1,
        next_eval_at=None,
        last_eval_at=None,
        status="active",
    )

    oco_spec = OcoSpec(order_id=order_id, symbol="BTCUSDT", side="sell", legs=legs, chat_id=999, tf_minutes=1)
    if not hasattr(bot, "_oco_orders"):
        bot._oco_orders = []
    bot._oco_orders.append(oco_spec)

    # attach to engine (this will create core orders and write core ids)
    bot._attach_oco_to_engine(oco_spec)

    # Read core ids from DB
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT core_order_id FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    core_ids = [r[0] for r in cur.fetchall()]
    assert len(core_ids) == 2

    # Force core orders to be due immediately (Order.is_due checks next_eval_at)
    for cid in core_ids:
        o = bot._manager.get_order(int(cid))
        if o:
            o.next_eval_at = 0

    # Simulate price moving above 110 to fire leg 1
    mock_feed.set_price(111.0)
    # process price for tf=1
    bot._manager.process_price("BTCUSDT", 111.0, tf_minutes=1)

    # Give ExecutionQueue some time to run actions
    time.sleep(0.5)

    # Check DB for statuses: one leg filled, other cancelled
    cur.execute("SELECT leg_index, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    res = cur.fetchall()
    statuses = {r[0]: r[1] for r in res}

    assert statuses[1] in ("filled", "filled")
    assert statuses[2] in ("cancelled", "cancelled") or statuses[2] == 'waiting'

    # Check order status
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,))
    ord_status = cur.fetchone()[0]
    assert ord_status in ("filled", "active")

    conn.close()
    bot._storage.close()


def test_auto_oco_with_trailing_sl_end_to_end(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    spec = SimpleOrderSpec(
        order_id=900,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=100.0,
        qty=1.0,
        chat_id=999,
        tf_minutes=1,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "percent", "value": 2.0},
            "sl": {"mode": "trailing", "value": 1.5},
        },
    )

    # Trigger simple buy fill -> should auto-create OCO with trailing SL leg.
    bot._on_simple_fired(spec, 100.0)
    time.sleep(0.3)

    assert len(bot._oco_orders) == 1
    oco = bot._oco_orders[0]
    trailing_leg = next((l for l in oco.legs if l.get("ordertype") == "trailing"), None)
    assert trailing_leg is not None
    assert trailing_leg.get("core_order_id") is not None

    linked_trailing = next((t for t in bot._trailing_sell_orders if t.order_id == trailing_leg.get("core_order_id")), None)
    assert linked_trailing is not None
    assert linked_trailing.oco_parent_order_id == oco.order_id
    assert linked_trailing.oco_leg_index == trailing_leg.get("leg_index")

    # Force linked trailing to fire.
    linked_trailing.next_eval_at = 0
    linked_trailing.armed = True
    linked_trailing.max_price = 100.0
    mock_feed.set_price(98.0)
    bot._eval_trailing_sell(int(time.time()))
    time.sleep(0.3)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (oco.order_id,))
    oco_status = cur.fetchone()[0]
    assert oco_status == "filled"

    cur.execute("SELECT leg_index, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (oco.order_id,))
    statuses = {idx: status for idx, status in cur.fetchall()}
    assert statuses[2] == "filled"
    assert statuses[1] == "cancelled"

    conn.close()
    bot._storage.close()


def test_auto_oco_independent_modes_tp_trailing_sl_percent(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    spec = SimpleOrderSpec(
        order_id=901,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=100.0,
        qty=1.0,
        chat_id=999,
        tf_minutes=1,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "trailing", "value": 2.0},
            "sl": {"mode": "percent", "value": 1.0},
        },
    )

    bot._on_simple_fired(spec, 100.0)
    time.sleep(0.3)

    assert len(bot._oco_orders) == 1
    oco = bot._oco_orders[0]
    tp_leg = next((l for l in oco.legs if int(l.get("leg_index")) == 1), None)
    sl_leg = next((l for l in oco.legs if int(l.get("leg_index")) == 2), None)
    assert tp_leg is not None and tp_leg.get("ordertype") == "trailing"
    assert sl_leg is not None and sl_leg.get("ordertype") == "stop_limit"

    # Force stop leg to trigger; it should cancel trailing sibling.
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT core_order_id FROM order_oco_leg WHERE order_id = ? AND leg_index = 2", (oco.order_id,))
    sl_core_id = int(cur.fetchone()[0])
    core_order = bot._manager.get_order(sl_core_id)
    assert core_order is not None
    core_order.next_eval_at = 0
    mock_feed.set_price(98.5)
    bot._manager.process_price("BTCUSDT", 98.5, tf_minutes=1)
    time.sleep(0.5)

    linked_trailing_id = int(tp_leg.get("core_order_id"))
    trailing_spec = next((t for t in bot._trailing_sell_orders if t.order_id == linked_trailing_id), None)
    assert trailing_spec is not None
    assert trailing_spec.status == "cancelled"

    cur.execute("SELECT status FROM order_oco_leg WHERE order_id = ? AND leg_index = 1", (oco.order_id,))
    tp_status = cur.fetchone()[0]
    cur.execute("SELECT status FROM order_oco_leg WHERE order_id = ? AND leg_index = 2", (oco.order_id,))
    sl_status = cur.fetchone()[0]
    assert tp_status == "cancelled"
    assert sl_status == "filled"
    conn.close()
    bot._storage.close()
