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


class _DummyMessage:
    def __init__(self, text: str):
        self.text = text


class _DummyUpdateWithMessage(_DummyUpdate):
    def __init__(self, text: str, chat_id=1):
        super().__init__(chat_id=chat_id)
        self.effective_message = _DummyMessage(text)


class _DummyContext:
    def __init__(self):
        self.user_data = {}


class _DummyApplication:
    def __init__(self):
        self.bot_data = {}


class _DummySlashContext(_DummyContext):
    def __init__(self):
        super().__init__()
        self.application = _DummyApplication()


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


def test_orders_menu_hides_separate_market_buttons(tmp_path):
    bot = _make_bot(tmp_path)
    kb = bot._orders_menu_keyboard()
    labels = [btn.text for row in kb.keyboard for btn in row]

    assert "📉 Sell market" not in labels
    assert "📈 Buy market" not in labels
    bot._storage.close()


def test_cmd_simple_market_buy_executes_immediately(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    class _FakeExchange:
        def create_order(self, **kwargs):
            return {"orderId": 1234, "status": "FILLED", "executedQty": str(kwargs.get("quantity"))}

    bot._exchange_client = _FakeExchange()
    bot._feed.get_price = lambda symbol, tf: 100.0

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    asyncio.run(bot._cmd_simple(_DummyUpdate(), ["/b", "BTCUSDT", "0.1"], side="buy", market=True))

    assert len(bot._buy_orders) == 1
    assert bot._buy_orders[0].op == "market"
    assert bot._buy_orders[0].status == "filled"
    assert "market eseguito" in captured["text"]
    bot._storage.close()


def test_slash_bm_routes_to_market_buy(tmp_path):
    bot = _make_bot(tmp_path)
    context = _DummySlashContext()
    calls = []

    async def _capture_cmd_simple(update, parts, side, market=False):
        calls.append({"parts": parts, "side": side, "market": market})

    bot._cmd_simple = _capture_cmd_simple

    asyncio.run(bot._on_slash_text(_DummyUpdateWithMessage("/bm BTCUSDT 0.1"), context))

    assert len(calls) == 1
    assert calls[0]["side"] == "buy"
    assert calls[0]["market"] is True
    assert calls[0]["parts"] == ["/b", "BTCUSDT", "0.1"]
    bot._storage.close()


def test_slash_sm_routes_to_market_sell(tmp_path):
    bot = _make_bot(tmp_path)
    context = _DummySlashContext()
    calls = []

    async def _capture_cmd_simple(update, parts, side, market=False):
        calls.append({"parts": parts, "side": side, "market": market})

    bot._cmd_simple = _capture_cmd_simple

    asyncio.run(bot._on_slash_text(_DummyUpdateWithMessage("/sm BTCUSDT 0.1"), context))

    assert len(calls) == 1
    assert calls[0]["side"] == "sell"
    assert calls[0]["market"] is True
    assert calls[0]["parts"] == ["/s", "BTCUSDT", "0.1"]
    bot._storage.close()
