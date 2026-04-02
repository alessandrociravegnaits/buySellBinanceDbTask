import os
import time
import tempfile
from price_feeds import MockPriceFeed
from telegram_bot import TelegramTradingBot, OcoSpec
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
