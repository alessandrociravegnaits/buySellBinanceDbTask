import asyncio
import os

from telegram_bot import TelegramTradingBot


class _DummyChat:
    def __init__(self, chat_id=1):
        self.id = chat_id


class _DummyUpdate:
    def __init__(self, chat_id=1):
        self.effective_chat = _DummyChat(chat_id)


class _DummyContext:
    def __init__(self):
        self.user_data = {}


def _make_bot(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)
    return TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)


def test_extract_btc_alert_liquidate_aliases():
    parts, value = TelegramTradingBot._extract_btc_alert_liquidate([
        "/s",
        "BTCUSDT",
        ">",
        "70000",
        "0.01",
        "btc_alert",
    ])
    assert value is True
    assert "btc_alert" not in parts

    parts, value = TelegramTradingBot._extract_btc_alert_liquidate([
        "/b",
        "BTCUSDT",
        "<",
        "60000",
        "0.01",
        "btc_liquidate=false",
    ])
    assert value is False
    assert all("btc_liquidate" not in token for token in parts)


def test_extract_btc_alert_liquidate_duplicate_raises():
    try:
        TelegramTradingBot._extract_btc_alert_liquidate([
            "/s",
            "BTCUSDT",
            ">",
            "70000",
            "0.01",
            "btc_alert",
            "btc_liquidate=1",
        ])
        assert False, "Expected duplicate flag error"
    except ValueError as exc:
        assert "duplicato" in str(exc)


def test_simple_sell_wizard_adds_btc_flag_choice(tmp_path):
    bot = _make_bot(tmp_path)

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    context = _DummyContext()
    context.user_data["ui_state"] = "simple_tf"
    context.user_data["ui_draft"] = {
        "side": "sell",
        "symbol": "BTCUSDT",
        "op": ">",
        "trigger": 70000.0,
        "qty": 0.01,
    }

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "15"))
    assert context.user_data["ui_state"] == "simple_btc_liq_choice"
    assert "protezione BTC drop" in captured["text"]

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "Si"))
    assert context.user_data["ui_state"] == "simple_confirm"
    assert context.user_data["ui_draft"]["btc_alert_liquidate"] is True

    bot._storage.close()


def test_oco_buy_wizard_adds_btc_flag_choice(tmp_path):
    bot = _make_bot(tmp_path)

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    context = _DummyContext()
    context.user_data["ui_state"] = "oco_side"
    context.user_data["ui_draft"] = {"symbol": "BTCUSDT", "legs": []}

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "buy"))
    assert context.user_data["ui_state"] == "oco_btc_liq_choice"

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "No"))
    assert context.user_data["ui_state"] == "oco_clean_entry_choice"
    assert context.user_data["ui_draft"]["btc_alert_liquidate"] is False

    bot._storage.close()


def test_buy_simple_guided_flow_can_switch_to_market_before_trigger(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    context = _DummyContext()
    context.user_data["ui_state"] = "simple_symbol"
    context.user_data["ui_draft"] = {"kind": "simple", "side": "buy"}

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "BTCUSDT"))
    assert context.user_data["ui_state"] == "simple_market_choice"
    assert "mercato" in captured["text"].lower()

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "Si"))
    assert context.user_data["ui_state"] == "simple_market_qty"
    assert "quantity" in captured["text"].lower()
    bot._storage.close()
