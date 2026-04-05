import asyncio
import os

from telegram_bot import TelegramTradingBot


class _FakeExchangeClient:
    def get_account(self):
        return {
            "updateTime": 1712300000000,
            "permissions": ["SPOT"],
            "balances": [
                {"asset": "USDT", "free": "100.0", "locked": "0.0"},
                {"asset": "BTC", "free": "0.1", "locked": "0.0"},
                {"asset": "ETH", "free": "0.0", "locked": "0.0"},
            ],
        }

    def get_open_orders(self):
        return [
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "origQty": "0.01",
                "price": "50000",
                "stopPrice": "0",
                "status": "NEW",
            },
            {
                "symbol": "ADAUSDT",
                "side": "SELL",
                "type": "STOP_LOSS_LIMIT",
                "origQty": "50",
                "price": "0.5",
                "stopPrice": "0.49",
                "status": "NEW",
            },
        ]

    def get_symbol_ticker(self, symbol: str):
        if symbol == "BTCUSDT":
            return {"price": "60000"}
        raise RuntimeError("ticker non disponibile")


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


def test_main_menu_contains_account_button(tmp_path):
    bot = _make_bot(tmp_path)

    kb = bot._main_menu_keyboard()
    labels = [btn.text for row in kb.keyboard for btn in row]

    assert "💰 Account" in labels
    bot._storage.close()


def test_cmd_account_requires_authenticated_client(tmp_path):
    bot = _make_bot(tmp_path)
    bot._exchange_client = None

    captured = {"messages": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["messages"].append(text)

    bot._send = _capture_send

    asyncio.run(bot._cmd_account(_DummyUpdate(), _DummyContext()))

    assert any("Account non disponibile" in msg for msg in captured["messages"])
    bot._storage.close()


def test_cmd_account_renders_balances_and_open_orders(tmp_path):
    bot = _make_bot(tmp_path)
    bot._exchange_client = _FakeExchangeClient()
    bot._public_exchange_client = bot._exchange_client

    captured = {"messages": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["messages"].append(text)

    bot._send = _capture_send

    asyncio.run(bot._cmd_account(_DummyUpdate(), _DummyContext()))

    output = "\n".join(captured["messages"])
    assert "Account Binance Spot" in output
    assert "- USDT: free=100" in output
    assert "- BTC: free=0.1" in output
    assert "Totale ordini aperti: 2" in output
    assert "BTCUSDT BUY LIMIT" in output

    bot._storage.close()
