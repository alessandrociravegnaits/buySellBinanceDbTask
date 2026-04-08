import os
import sqlite3
import time

from core import build_engine
from price_feeds import MockPriceFeed
from telegram_bot import OcoSpec, SimpleOrderSpec, TelegramTradingBot, TrailingSellSpec


class FakeExchangeClient:
    def __init__(self):
        self.calls = []

    def create_order(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "orderId": 123456,
            "status": "FILLED",
            "executedQty": str(kwargs.get("quantity")),
        }


def test_oco_end_to_end(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

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
    bot._oco_orders.append(oco_spec)
    bot._attach_oco_to_engine(oco_spec)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT core_order_id FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    core_ids = [r[0] for r in cur.fetchall()]
    assert len(core_ids) == 2

    for cid in core_ids:
        order = bot._manager.get_order(int(cid))
        if order:
            order.next_eval_at = 0

    mock_feed.set_price(111.0)
    bot._manager.process_price("BTCUSDT", 111.0, tf_minutes=1)
    time.sleep(0.5)

    cur.execute("SELECT leg_index, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    statuses = {idx: status for idx, status in cur.fetchall()}
    assert statuses[1] == "filled"
    assert statuses[2] == "cancelled"

    cur.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,))
    assert cur.fetchone()[0] == "filled"

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

    linked_trailing.next_eval_at = 0
    linked_trailing.armed = True
    linked_trailing.max_price = 100.0
    mock_feed.set_price(98.0)
    bot._eval_trailing_sell(int(time.time()))
    time.sleep(0.3)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (oco.order_id,))
    assert cur.fetchone()[0] == "filled"

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


def test_btc_alert_liquidates_flagged_sell_orders(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    simple_spec = SimpleOrderSpec(
        order_id=1001,
        side="sell",
        symbol="ETHUSDT",
        op=">",
        trigger=3000.0,
        qty=0.25,
        chat_id=999,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._attach_simple_to_engine(simple_spec)
    bot._sell_orders.append(simple_spec)
    bot._storage.save_simple_order(
        order_id=simple_spec.order_id,
        chat_id=simple_spec.chat_id,
        side=simple_spec.side,
        symbol=simple_spec.symbol,
        op=simple_spec.op,
        trigger_value=simple_spec.trigger,
        qty=simple_spec.qty,
        hook_symbol=simple_spec.hook_symbol,
        core_order_id=simple_spec.core_order_id,
        btc_alert_liquidate=simple_spec.btc_alert_liquidate,
        tf_minutes=simple_spec.tf_minutes,
        next_eval_at=simple_spec.next_eval_at,
        last_eval_at=simple_spec.last_eval_at,
        post_fill_action=simple_spec.post_fill_action,
        status=simple_spec.status,
    )

    trailing_spec = TrailingSellSpec(
        order_id=1002,
        symbol="BNBUSDT",
        qty=0.5,
        percent=1.5,
        chat_id=999,
        limit=None,
        hook_symbol=None,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._init_trailing_sell(trailing_spec)
    bot._trailing_sell_orders.append(trailing_spec)
    bot._storage.save_trailing_order(
        order_id=trailing_spec.order_id,
        chat_id=trailing_spec.chat_id,
        side="sell",
        symbol=trailing_spec.symbol,
        qty=trailing_spec.qty,
        percent=trailing_spec.percent,
        limit_price=trailing_spec.limit,
        hook_symbol=trailing_spec.hook_symbol,
        armed=trailing_spec.armed,
        max_price=trailing_spec.max_price,
        min_price=None,
        arm_op=trailing_spec.arm_op,
        btc_alert_liquidate=trailing_spec.btc_alert_liquidate,
        tf_minutes=trailing_spec.tf_minutes,
        next_eval_at=trailing_spec.next_eval_at,
        last_eval_at=trailing_spec.last_eval_at,
        post_fill_action=None,
        status=trailing_spec.status,
    )

    oco_order_id = bot._new_order_id()
    oco_legs = [
        {"leg_index": 1, "ordertype": "limit", "price": 120.0, "qty": 0.4, "side": "sell"},
        {"leg_index": 2, "ordertype": "stop_limit", "stop_price": 80.0, "limit_price": 79.5, "qty": 0.4, "side": "sell"},
    ]
    bot._storage.save_oco_order(
        order_id=oco_order_id,
        chat_id=999,
        symbol="BTCUSDT",
        side="sell",
        legs=oco_legs,
        hook_symbol=None,
        tf_minutes=1,
        next_eval_at=None,
        last_eval_at=None,
        btc_alert_liquidate=True,
        status="active",
    )
    oco_spec = OcoSpec(
        order_id=oco_order_id,
        symbol="BTCUSDT",
        side="sell",
        legs=oco_legs,
        chat_id=999,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._oco_orders.append(oco_spec)
    bot._attach_oco_to_engine(oco_spec)

    bot._btc_alert_liquidation_percent = 1.0
    bot._btc_alert_liquidation_reference_price = 100.0
    bot._last_btc_liquidation_tick = 0.0

    mock_feed.set_price(95.0)
    bot._eval_btc_liquidation(None, time.time())

    assert len(bot._exchange_client.calls) == 3
    traded_symbols = {call["symbol"] for call in bot._exchange_client.calls}
    assert traded_symbols == {"ETHUSDT", "BNBUSDT", "BTCUSDT"}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (simple_spec.order_id,))
    assert cur.fetchone()[0] == "filled"
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (trailing_spec.order_id,))
    assert cur.fetchone()[0] == "filled"
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (oco_spec.order_id,))
    assert cur.fetchone()[0] == "filled"
    cur.execute("SELECT leg_index, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (oco_spec.order_id,))
    leg_statuses = {idx: status for idx, status in cur.fetchall()}
    assert leg_statuses[1] == "cancelled"
    assert leg_statuses[2] == "cancelled"
    conn.close()
    bot._storage.close()


def test_btc_alert_liquidation_ignores_upward_move(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    simple_spec = SimpleOrderSpec(
        order_id=2001,
        side="sell",
        symbol="ETHUSDT",
        op=">",
        trigger=3000.0,
        qty=0.25,
        chat_id=999,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._attach_simple_to_engine(simple_spec)
    bot._sell_orders.append(simple_spec)
    bot._storage.save_simple_order(
        order_id=simple_spec.order_id,
        chat_id=simple_spec.chat_id,
        side=simple_spec.side,
        symbol=simple_spec.symbol,
        op=simple_spec.op,
        trigger_value=simple_spec.trigger,
        qty=simple_spec.qty,
        hook_symbol=simple_spec.hook_symbol,
        core_order_id=simple_spec.core_order_id,
        btc_alert_liquidate=simple_spec.btc_alert_liquidate,
        tf_minutes=simple_spec.tf_minutes,
        next_eval_at=simple_spec.next_eval_at,
        last_eval_at=simple_spec.last_eval_at,
        post_fill_action=simple_spec.post_fill_action,
        status=simple_spec.status,
    )

    bot._btc_alert_liquidation_percent = 1.0
    bot._btc_alert_liquidation_reference_price = 100.0
    bot._last_btc_liquidation_tick = 0.0

    mock_feed.set_price(103.0)
    bot._eval_btc_liquidation(None, time.time())

    assert len(bot._exchange_client.calls) == 0
    assert simple_spec.status == "active"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (simple_spec.order_id,))
    assert cur.fetchone()[0] == "active"
    conn.close()
    bot._storage.close()
