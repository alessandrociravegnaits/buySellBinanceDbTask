import os

from storage import SQLiteStorage
from telegram_bot import TelegramTradingBot


def test_parse_post_fill_oco_spec_trailing():
    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path="data/test_bot.sqlite3")
    spec = bot._parse_post_fill_oco_spec("oco:tp=3%,sl=trail:1.5%")
    assert spec["type"] == "oco"
    assert spec["tp"]["mode"] == "percent"
    assert spec["tp"]["value"] == 3.0
    assert spec["sl"]["mode"] == "trailing"
    assert spec["sl"]["value"] == 1.5
    bot._storage.close()


def test_parse_post_fill_oco_spec_tp_trailing_enabled():
    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path="data/test_bot.sqlite3")
    spec = bot._parse_post_fill_oco_spec("oco:tp=trail:2%,sl=1.2%")
    assert spec["tp"]["mode"] == "trailing"
    assert spec["tp"]["value"] == 2.0
    assert spec["sl"]["mode"] == "percent"
    bot._storage.close()


def test_extract_post_fill_action_duplicate_raises():
    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path="data/test_bot.sqlite3")
    parts = ["/b", "BTCUSDT", "<", "67000", "0.001", "oco:tp=3%,sl=1.5%", "oco:tp=2%,sl=1%"]
    try:
        bot._extract_post_fill_action(parts)
        assert False, "Expected ValueError for duplicate oco spec"
    except ValueError:
        pass
    finally:
        bot._storage.close()


def test_restore_active_order_keeps_post_fill_action(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    storage = SQLiteStorage(db_path, archive_dir)
    oid = storage.next_order_id()
    storage.save_simple_order(
        order_id=oid,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger_value=67000.0,
        qty=0.001,
        hook_symbol=None,
        core_order_id=oid,
        tf_minutes=15,
        next_eval_at=0,
        last_eval_at=None,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "percent", "value": 3.0},
            "sl": {"mode": "trailing", "value": 1.5},
        },
        status="active",
    )
    storage.close()

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    restored = [b for b in bot._buy_orders if b.order_id == oid]
    assert len(restored) == 1
    assert restored[0].post_fill_action is not None
    assert restored[0].post_fill_action.get("type") == "oco"
    assert restored[0].post_fill_action.get("sl", {}).get("mode") == "trailing"
    bot._storage.close()
