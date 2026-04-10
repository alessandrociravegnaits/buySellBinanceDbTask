import asyncio
import os
import sqlite3
import sys
import time

import pandas as pd

from core import build_engine
from price_feeds import MockPriceFeed
from storage import SQLiteStorage
from telegram_bot import OcoSpec, SimpleOrderSpec, TelegramTradingBot


class _DummyChat:
    def __init__(self, chat_id=1):
        self.id = chat_id


class _DummyUpdate:
    def __init__(self, chat_id=1):
        self.effective_chat = _DummyChat(chat_id)


class _FakeExchangeCounter:
    def __init__(self):
        self.calls = 0

    def create_order(self, **kwargs):
        self.calls += 1
        return {
            "orderId": 999,
            "status": "FILLED",
            "executedQty": str(kwargs.get("quantity")),
        }


def _make_bot(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)
    return TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)


def test_storage_persists_acquistopulito_for_buy_and_oco(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    storage = SQLiteStorage(db_path, archive_dir)

    buy_id = storage.next_order_id()
    storage.save_simple_order(
        order_id=buy_id,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op=">",
        trigger_value=1.0,
        qty=0.01,
        hook_symbol=None,
        core_order_id=buy_id,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        acquistopulito=True,
        status="active",
    )

    oco_id = storage.next_order_id()
    storage.save_oco_order(
        order_id=oco_id,
        chat_id=1,
        symbol="BTCUSDT",
        side="buy",
        legs=[{"leg_index": 1, "ordertype": "limit", "price": 1.0, "qty": 0.01, "side": "buy"}],
        hook_symbol=None,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        acquistopulito=True,
        status="active",
    )

    data = storage.load_active_orders()
    buy = next(r for r in data["simple"] if r["order_id"] == buy_id)
    oco = next(r for r in data["oco"] if r["order_id"] == oco_id)

    assert int(buy["acquistopulito"]) == 1
    assert int(oco["acquistopulito"]) == 1

    storage.close()


def test_extract_acquistopulito_token_parser():
    parts, value = TelegramTradingBot._extract_acquistopulito(["/b", "BTCUSDT", ">", "1", "0.1", "acquistopulito"])
    assert value is True
    assert "acquistopulito" not in parts

    parts, value = TelegramTradingBot._extract_acquistopulito(["/b", "BTCUSDT", ">", "1", "0.1", "acquistopulito=false"])
    assert value is False
    assert all("acquistopulito" not in token for token in parts)


def test_cmd_buy_sets_acquistopulito(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    async def _noop_send(update, text, reply_markup=None):
        return None

    bot._send = _noop_send

    asyncio.run(bot._cmd_simple(_DummyUpdate(), ["/b", "BTCUSDT", ">", "1", "0.1", "acquistopulito"], side="buy"))

    assert len(bot._buy_orders) == 1
    assert bot._buy_orders[0].acquistopulito is True

    conn = sqlite3.connect(bot._storage._db_path)
    cur = conn.cursor()
    cur.execute("SELECT acquistopulito FROM order_simple WHERE order_id = ?", (bot._buy_orders[0].order_id,))
    row = cur.fetchone()
    assert row is not None and int(row[0]) == 1
    conn.close()
    bot._storage.close()


def test_cmd_sell_rejects_acquistopulito(tmp_path):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    try:
        asyncio.run(bot._cmd_simple(_DummyUpdate(), ["/s", "BTCUSDT", ">", "1", "0.1", "acquistopulito"], side="sell"))
        assert False, "Expected ValueError for sell + acquistopulito"
    except ValueError as exc:
        assert "acquistopulito supportato solo su ordini buy" in str(exc)

    bot._storage.close()


def test_simple_buy_clean_entry_blocked_rearms_order(tmp_path):
    bot = _make_bot(tmp_path)
    exchange = _FakeExchangeCounter()
    bot._exchange_client = exchange
    bot._feed = MockPriceFeed(initial_price=100.0)
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=bot._feed)

    bot._evaluate_clean_entry = lambda symbol, tf_minutes, price: (False, "blocked", {})

    spec = SimpleOrderSpec(
        order_id=500,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=101.0,
        qty=1.0,
        chat_id=1,
        tf_minutes=1,
        next_eval_at=0,
        acquistopulito=True,
        status="active",
    )
    bot._attach_simple_to_engine(spec)

    core_order = bot._manager.get_order(spec.core_order_id)
    assert core_order is not None
    core_order.next_eval_at = 0

    bot._manager.process_price("BTCUSDT", 100.0, tf_minutes=1)
    time.sleep(0.35)

    assert exchange.calls == 0
    assert spec.status == "active"
    assert bot._manager.get_order(spec.core_order_id) is not None
    bot._storage.close()


def test_oco_buy_clean_entry_blocked_does_not_execute(tmp_path):
    bot = _make_bot(tmp_path)
    exchange = _FakeExchangeCounter()
    bot._exchange_client = exchange
    bot._feed = MockPriceFeed(initial_price=100.0)
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=bot._feed)

    bot._evaluate_clean_entry = lambda symbol, tf_minutes, price: (False, "blocked", {})

    order_id = bot._new_order_id()
    legs = [
        {"leg_index": 1, "ordertype": "limit", "price": 99.0, "qty": 1.0, "side": "buy"},
        {"leg_index": 2, "ordertype": "stop_limit", "stop_price": 105.0, "limit_price": 105.0, "qty": 1.0, "side": "buy"},
    ]
    bot._storage.save_oco_order(
        order_id=order_id,
        chat_id=1,
        symbol="BTCUSDT",
        side="buy",
        legs=legs,
        hook_symbol=None,
        tf_minutes=1,
        next_eval_at=0,
        last_eval_at=None,
        acquistopulito=True,
        status="active",
    )

    spec = OcoSpec(
        order_id=order_id,
        symbol="BTCUSDT",
        side="buy",
        legs=legs,
        chat_id=1,
        tf_minutes=1,
        next_eval_at=0,
        acquistopulito=True,
        status="active",
    )
    bot._oco_orders = [spec]
    bot._attach_oco_to_engine(spec)

    core_id = int(spec.legs[0]["core_order_id"])
    core_order = bot._manager.get_order(core_id)
    assert core_order is not None
    core_order.next_eval_at = 0

    bot._manager.process_price("BTCUSDT", 98.5, tf_minutes=1)
    time.sleep(0.35)

    assert exchange.calls == 0
    assert spec.status == "active"
    assert spec.legs[0].get("status", "waiting") == "waiting"
    assert bot._manager.get_order(core_id) is not None

    bot._storage.close()


def test_cmd_setpulito_preset_updates_global_config(tmp_path):
    bot = _make_bot(tmp_path)
    captured = {"text": ""}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    bot._send = _capture_send

    asyncio.run(bot._cmd_setpulito(_DummyUpdate(), ["/setpulito", "preset", "conservativo"]))

    assert bot._clean_entry_preset == "conservativo"
    assert bot._clean_entry_config["rsi_min"] == 55.0
    assert bot._clean_entry_config["adx_min"] == 22.0
    assert bot._clean_entry_config["required_checks"] == 5
    assert "setPulito aggiornato" in captured["text"]
    assert bot._storage.get_setting("clean_entry_preset") == "conservativo"

    bot._storage.close()


def test_cmd_setpulito_manual_overrides_are_persisted(tmp_path):
    bot = _make_bot(tmp_path)

    async def _noop_send(update, text, reply_markup=None):
        return None

    bot._send = _noop_send

    asyncio.run(
        bot._cmd_setpulito(
            _DummyUpdate(),
            ["/setpulito", "manuale", "rsi=52", "adx=20", "checks=4", "volume=0", "trend=1", "priceema=1"],
        )
    )

    assert bot._clean_entry_preset == "manuale"
    assert bot._clean_entry_config["rsi_min"] == 52.0
    assert bot._clean_entry_config["adx_min"] == 20.0
    assert bot._clean_entry_config["required_checks"] == 4
    assert bot._clean_entry_config["require_volume"] is False
    assert bot._storage.get_setting("clean_entry_require_volume") == "0"

    bot._storage.close()


def test_evaluate_clean_entry_respects_global_required_checks(tmp_path, monkeypatch):
    bot = _make_bot(tmp_path)
    frame = pd.DataFrame(
        {
            "timestamp": [1, 2, 3],
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            "close": [100, 101, 100],
            "volume": [100, 120, 130],
        }
    )

    def _fake_fetch(symbol, tf_minutes, limit=200):
        return frame

    class _FakeIndicators:
        @staticmethod
        def from_ohlcv(_frame):
            class _Runner:
                @staticmethod
                def compute_default_set():
                    return pd.DataFrame(
                        [
                            {
                                "rsi_14": 55.0,
                                "adx_14": 23.0,
                                "ema_20": 110.0,
                                "volume_ma_20": 200.0,
                            }
                        ]
                    )

            return _Runner()

    bot._fetch_ohlcv_for_indicators = _fake_fetch
    monkeypatch.setattr(sys.modules[TelegramTradingBot.__module__], "TechnicalIndicators", _FakeIndicators)

    bot._clean_entry_config = bot._normalize_clean_entry_config(
        {
            "rsi_min": 50,
            "adx_min": 18,
            "required_checks": 4,
            "require_trend": True,
            "require_volume": False,
            "require_price_above_ema": True,
        }
    )
    passed_high, _, snap_high = bot._evaluate_clean_entry("BTCUSDT", 15, 100.0)
    assert passed_high is False
    assert snap_high["passed_checks"] == 2

    bot._clean_entry_config = bot._normalize_clean_entry_config(
        {
            "rsi_min": 50,
            "adx_min": 18,
            "required_checks": 2,
            "require_trend": True,
            "require_volume": False,
            "require_price_above_ema": True,
        }
    )
    passed_low, _, snap_low = bot._evaluate_clean_entry("BTCUSDT", 15, 100.0)
    assert passed_low is True
    assert snap_low["passed_checks"] == 2

    bot._storage.close()
