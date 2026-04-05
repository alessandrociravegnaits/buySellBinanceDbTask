import asyncio
import os

import pytest

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


def test_cmd_simple_rejects_invalid_symbol(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (False, "SYMBOL non valido")

    with pytest.raises(ValueError, match="SYMBOL non valido"):
        asyncio.run(bot._cmd_simple(_DummyUpdate(), ["/b", "FAKEUSDT", ">", "1", "0.1"], side="buy"))

    assert len(bot._buy_orders) == 0
    assert len(bot._sell_orders) == 0
    bot._storage.close()


def test_cmd_simple_accepts_valid_symbol(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    asyncio.run(bot._cmd_simple(_DummyUpdate(), ["/b", "BTCUSDT", ">", "1", "0.1"], side="buy"))

    assert len(bot._buy_orders) == 1
    assert "Ordine buy inserito" in captured["text"]
    bot._storage.close()


def test_guided_flow_keeps_state_on_invalid_symbol(tmp_path):
    bot = _make_bot(tmp_path)
    context = _DummyContext()
    bot._set_ui_state(context, "simple_symbol", {"kind": "simple", "side": "buy"})
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (False, "SYMBOL non valido")

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    handled = asyncio.run(bot._handle_guided_flow(update=None, context=context, text="FAKEUSDT"))

    assert handled is True
    assert bot._get_ui_state(context) == "simple_symbol"
    assert "Reinserisci SYMBOL" in captured["text"]
    bot._storage.close()
