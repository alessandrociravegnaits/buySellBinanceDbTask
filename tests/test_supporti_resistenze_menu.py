import asyncio
import os

import pandas as pd
import pytest

import telegram_bot
from telegram_bot import TelegramTradingBot


class _DummyChat:
    def __init__(self, chat_id=1):
        self.id = chat_id


class _DummyMessage:
    def __init__(self, text: str = ""):
        self.text = text


class _DummyUpdate:
    def __init__(self, text: str = "", chat_id: int = 1):
        self.effective_chat = _DummyChat(chat_id)
        self.effective_message = _DummyMessage(text)


class _DummyContext:
    def __init__(self):
        self.user_data = {}


def _make_bot(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)
    return TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)


def _fake_ohlcv_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [1710000000000, 1710000060000, 1710000120000],
            "open": [10.0, 10.1, 9.9],
            "high": [10.2, 10.3, 10.0],
            "low": [9.8, 9.9, 9.7],
            "close": [10.0, 10.2, 9.95],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )


def test_main_menu_contains_supporti_resistenze_button(tmp_path):
    bot = _make_bot(tmp_path)
    labels = [btn.text for row in bot._main_menu_keyboard().keyboard for btn in row]

    assert "🧭 Supporti&Resistenze" in labels
    bot._storage.close()


def test_cmd_sr_outputs_levels_in_range(monkeypatch, tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")
    bot._fetch_ohlcv_for_indicators = lambda symbol, tf_minutes, limit=400: _fake_ohlcv_frame()

    monkeypatch.setattr(
        telegram_bot,
        "richiedi_supporti_resistenze",
        lambda candles, **kwargs: {
            "symbol": kwargs.get("symbol", "XRPUSDC"),
            "timeframe": kwargs.get("timeframe", "15m"),
            "last_close": 10.0,
            "supports": [
                {"level": 9.6, "touches": 4, "distance_pct_from_last_close": -4.0},
                {"level": 7.8, "touches": 2, "distance_pct_from_last_close": -22.0},
            ],
            "resistances": [
                {"level": 10.4, "touches": 3, "distance_pct_from_last_close": 4.0},
                {"level": 12.5, "touches": 2, "distance_pct_from_last_close": 25.0},
            ],
            "secure_support": {"level": 9.6, "confidence": 0.82},
            "secure_resistance": {"level": 10.4, "confidence": 0.79},
            "secure_support_ok": True,
            "secure_resistance_ok": True,
        },
    )

    captured = {"messages": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["messages"].append(text)

    bot._send = _capture_send

    asyncio.run(bot._cmd_sr(_DummyUpdate(), ["/sr", "XRPUSDC", "15", "20"]))

    output = "\n".join(captured["messages"])
    assert "Supporti&Resistenze XRPUSDC" in output
    assert "Supporti vicini" in output
    assert "9.6" in output
    assert "7.8" not in output
    assert "Resistenze vicine" in output
    assert "10.4" in output
    assert "12.5" not in output
    assert "Secure levels" in output

    bot._storage.close()


def test_supporti_resistenze_guided_flow_calls_sr(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    captured = {"parts": None, "menu_shown": False}

    async def _capture_send(update, text, reply_markup=None):
        return None

    async def _capture_cmd_sr(update, parts):
        captured["parts"] = parts

    async def _capture_show_main_menu(update, intro=None):
        captured["menu_shown"] = True

    bot._send = _capture_send
    bot._cmd_sr = _capture_cmd_sr
    bot._show_main_menu = _capture_show_main_menu

    context = _DummyContext()
    context.user_data["ui_state"] = "sr_symbol"
    context.user_data["ui_draft"] = {"kind": "supporti_resistenze"}

    update = _DummyUpdate()

    asyncio.run(bot._handle_guided_flow(update, context, "XRPUSDC"))
    assert context.user_data.get("ui_state") == "sr_tf"

    asyncio.run(bot._handle_guided_flow(update, context, "15"))
    assert context.user_data.get("ui_state") == "sr_ampiezza"

    asyncio.run(bot._handle_guided_flow(update, context, "20%"))
    assert context.user_data.get("ui_state") == "sr_secure_choice"

    asyncio.run(bot._handle_guided_flow(update, context, "si"))

    assert "ui_state" not in context.user_data
    assert captured["menu_shown"] is True
    assert captured["parts"] is not None
    assert captured["parts"][0] == "/sr"
    assert captured["parts"][1] == "XRPUSDC"
    assert captured["parts"][2] == "15"
    assert captured["parts"][4] == "si"

    bot._storage.close()


def test_cmd_sr_rejects_range_over_100(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    with pytest.raises(ValueError, match="Ampiezza valida"):
        asyncio.run(bot._cmd_sr(_DummyUpdate(), ["/sr", "XRPUSDC", "15", "150"]))

    bot._storage.close()


def test_sr_week_alias_and_label_are_stable(tmp_path):
    bot = _make_bot(tmp_path)
    assert bot._parse_sr_tf_choice("w") == 10080
    assert bot._parse_sr_tf_choice("1w") == 10080
    assert bot._sr_minutes_to_label(10080) == "1w"
    bot._storage.close()
