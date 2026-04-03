import asyncio
import os

from telegram_bot import (
    FunctionSpec,
    OcoSpec,
    SimpleOrderSpec,
    TelegramTradingBot,
    TrailingBuySpec,
    TrailingSellSpec,
)


def _make_bot(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)
    return TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)


def test_cancel_order_targets_builds_synthetic_labels(tmp_path):
    bot = _make_bot(tmp_path)

    bot._sell_orders = [
        SimpleOrderSpec(order_id=12, side="sell", symbol="BTCUSDT", op=">", trigger=1.0, qty=0.1, chat_id=1, status="active")
    ]
    bot._buy_orders = [
        SimpleOrderSpec(order_id=11, side="buy", symbol="ETHUSDT", op="<", trigger=1.0, qty=0.1, chat_id=1, status="active")
    ]
    bot._function_orders = [
        FunctionSpec(order_id=13, symbol="ADAUSDT", op="<", trigger=1.0, qty=0.1, percent=1.0, chat_id=1, hook_symbol=None, status="active")
    ]
    bot._trailing_sell_orders = [
        TrailingSellSpec(order_id=15, symbol="SOLUSDT", qty=0.1, percent=1.0, chat_id=1, limit=None, hook_symbol=None, status="active")
    ]
    bot._trailing_buy_orders = [
        TrailingBuySpec(order_id=14, symbol="XRPUSDT", qty=0.1, percent=1.0, chat_id=1, limit=1.0, status="active")
    ]
    bot._oco_orders = [
        OcoSpec(order_id=16, symbol="BNBUSDT", side="sell", legs=[], chat_id=1, status="active")
    ]

    targets = bot._cancel_order_targets()
    assert targets == [
        (11, "#11:ETHUSDT:buy"),
        (12, "#12:BTCUSDT:sell"),
        (13, "#13:ADAUSDT:function"),
        (14, "#14:XRPUSDT:tb"),
        (15, "#15:SOLUSDT:ts"),
        (16, "#16:BNBUSDT:oco"),
    ]

    bot._storage.close()


def test_cancel_order_keyboard_limits_buttons(tmp_path):
    bot = _make_bot(tmp_path)

    bot._sell_orders = [
        SimpleOrderSpec(order_id=i, side="sell", symbol=f"S{i}USDT", op=">", trigger=1.0, qty=0.1, chat_id=1, status="active")
        for i in range(1, 15)
    ]

    kb = bot._cancel_order_keyboard(max_buttons=6)
    flat = [btn.text for row in kb.keyboard for btn in row]

    assert "#1:S1USDT:sell" in flat
    assert "#6:S6USDT:sell" in flat
    assert "#7:S7USDT:sell" not in flat
    assert "Tutti ✅" in flat
    assert "Annulla" in flat

    bot._storage.close()


def test_extract_order_id_from_cancel_input():
    assert TelegramTradingBot._extract_order_id_from_cancel_input("#123:BTCUSDT:sell") == "123"
    assert TelegramTradingBot._extract_order_id_from_cancel_input("  #44:ETHUSDT:oco ") == "44"
    assert TelegramTradingBot._extract_order_id_from_cancel_input("987") == "987"


def test_cmd_o_shows_only_active_orders(tmp_path):
    bot = _make_bot(tmp_path)

    bot._sell_orders = [
        SimpleOrderSpec(order_id=1, side="sell", symbol="BTCUSDT", op=">", trigger=1.0, qty=0.1, chat_id=1, status="active"),
        SimpleOrderSpec(order_id=2, side="sell", symbol="ETHUSDT", op=">", trigger=1.0, qty=0.1, chat_id=1, status="cancelled"),
    ]

    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    asyncio.run(bot._cmd_o(update=None))

    output = captured["text"]
    assert "Ordini attivi (order_id):" in output
    assert "1 watch=BTCUSDT" in output
    assert "2 watch=ETHUSDT" not in output

    bot._storage.close()
