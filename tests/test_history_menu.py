import asyncio
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import prevision
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


def _set_order_updated_at(storage, order_id: int, updated_at: str):
    conn = sqlite3.connect(storage._db_path)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET updated_at = ? WHERE order_id = ?", (updated_at, order_id))
    conn.commit()
    conn.close()


def test_main_menu_contains_history_button(tmp_path):
    bot = _make_bot(tmp_path)
    kb = bot._main_menu_keyboard()
    labels = [btn.text for row in kb.keyboard for btn in row]

    assert "📜 Ordini storici" in labels
    bot._storage.close()


def test_history_menu_keyboard_shows_ranges(tmp_path):
    bot = _make_bot(tmp_path)
    kb = bot._orders_history_keyboard()
    labels = [btn.text for row in kb.keyboard for btn in row]

    assert "1gg" in labels
    assert "3gg" in labels
    assert "7gg" in labels
    assert "30gg" in labels
    bot._storage.close()


def test_history_storage_filters_non_active_orders(tmp_path):
    bot = _make_bot(tmp_path)
    storage = bot._storage

    recent_oid = storage.next_order_id()
    storage.save_simple_order(
        order_id=recent_oid,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger_value=60000.0,
        qty=0.001,
        hook_symbol=None,
        core_order_id=recent_oid,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        acquistopulito=True,
        status="active",
    )

    old_oid = storage.next_order_id()
    storage.save_simple_order(
        order_id=old_oid,
        chat_id=1,
        side="sell",
        symbol="ETHUSDT",
        op=">",
        trigger_value=3000.0,
        qty=0.01,
        hook_symbol=None,
        core_order_id=old_oid,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        acquistopulito=False,
        status="cancelled",
    )
    past_iso = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat()
    _set_order_updated_at(storage, old_oid, past_iso)

    data_1d = storage.load_historical_orders(1)
    assert all(row["order_id"] != old_oid for row in data_1d["simple"])
    assert all(row["order_id"] != recent_oid for row in data_1d["simple"])

    data_7d = storage.load_historical_orders(7)
    simple_ids = [row["order_id"] for row in data_7d["simple"]]
    assert old_oid in simple_ids
    assert recent_oid not in simple_ids

    storage.close()


def test_history_flow_renders_results(tmp_path):
    bot = _make_bot(tmp_path)
    storage = bot._storage

    oid = storage.next_order_id()
    storage.save_simple_order(
        order_id=oid,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger_value=60000.0,
        qty=0.001,
        hook_symbol=None,
        core_order_id=oid,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        acquistopulito=True,
        status="filled",
    )
    _set_order_updated_at(storage, oid, (datetime.now(timezone.utc) - timedelta(hours=6)).replace(microsecond=0).isoformat())

    captured = {"text": "", "chunks": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    async def _capture_chunked(update, lines, max_chars=3500):
        captured["chunks"] = list(lines)

    bot._send = _capture_send
    bot._send_chunked = _capture_chunked

    context = _DummyContext()
    context.user_data["ui_state"] = "history_days"

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "1gg"))

    output = "\n".join(captured["chunks"] or [captured["text"]])
    assert "Ordini storici ultimi 1 giorni" in output
    assert "BTCUSDT" in output
    assert "filled" in output

    bot._storage.close()


def test_history_flow_empty_results(tmp_path):
    bot = _make_bot(tmp_path)

    captured = {"text": "", "chunks": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    async def _capture_chunked(update, lines, max_chars=3500):
        captured["chunks"] = list(lines)

    bot._send = _capture_send
    bot._send_chunked = _capture_chunked

    context = _DummyContext()
    context.user_data["ui_state"] = "history_days"

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "1gg"))

    output = "\n".join(captured["chunks"] or [captured["text"]])
    assert "Nessun ordine trovato" in output

    bot._storage.close()


def test_history_flow_renders_gain_for_linked_exit(tmp_path):
    bot = _make_bot(tmp_path)
    storage = bot._storage

    parent_oid = storage.next_order_id()
    storage.save_simple_order(
        order_id=parent_oid,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger_value=60000.0,
        qty=0.001,
        hook_symbol=None,
        core_order_id=parent_oid,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        acquistopulito=True,
        status="filled",
    )

    oco_oid = storage.next_order_id()
    storage.save_oco_order(
        order_id=oco_oid,
        chat_id=1,
        symbol="BTCUSDT",
        side="sell",
        legs=[{"leg_index": 1, "ordertype": "limit", "price": 110.0, "qty": 0.001, "side": "sell"}],
        hook_symbol=None,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        parent_order_id=parent_oid,
        status="filled",
    )

    storage.append_event("simple_filled", parent_oid, {"price": 100.0, "exchange_symbol": "BTCUSDT"})
    storage.append_event(
        "oco_leg_filled",
        oco_oid,
        {"leg_index": 1, "ordertype": "limit", "price": 110.0, "exchange_symbol": "BTCUSDT"},
    )
    _set_order_updated_at(storage, parent_oid, (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat())
    _set_order_updated_at(storage, oco_oid, (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat())

    captured = {"text": "", "chunks": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    async def _capture_chunked(update, lines, max_chars=3500):
        captured["chunks"] = list(lines)

    bot._send = _capture_send
    bot._send_chunked = _capture_chunked

    context = _DummyContext()
    context.user_data["ui_state"] = "history_days"

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "1gg"))

    output = "\n".join(captured["chunks"] or [captured["text"]])
    assert "gain=+10.00%" in output
    assert "100 -> 110" in output

    bot._storage.close()


def test_history_flow_renders_json_post_fill_action(tmp_path):
    bot = _make_bot(tmp_path)
    storage = bot._storage

    oid = storage.next_order_id()
    storage.save_simple_order(
        order_id=oid,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger_value=60000.0,
        qty=0.001,
        hook_symbol=None,
        core_order_id=oid,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        post_fill_action={"type": "oco", "tp": {"mode": "percent", "value": 1.5}, "sl": {"mode": "percent", "value": 0.8}},
        acquistopulito=True,
        status="filled",
    )
    _set_order_updated_at(storage, oid, (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat())

    captured = {"text": "", "chunks": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["text"] = text

    async def _capture_chunked(update, lines, max_chars=3500):
        captured["chunks"] = list(lines)

    bot._send = _capture_send
    bot._send_chunked = _capture_chunked

    context = _DummyContext()
    context.user_data["ui_state"] = "history_days"

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "1gg"))

    output = "\n".join(captured["chunks"] or [captured["text"]])
    assert "post_fill=oco(tp=percent:1.5,sl=percent:0.8)" in output

    bot._storage.close()


def test_prevision_sends_command_in_separate_message(tmp_path, monkeypatch):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    captured = {"chunked": [], "messages": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["messages"].append(text)

    async def _capture_chunked(update, lines, max_chars=3500):
        captured["chunked"].append(list(lines))

    bot._send = _capture_send
    bot._send_chunked = _capture_chunked

    def _fake_analyze_symbol(symbol, tf_minutes, budget_quote, lookback_bars):
        return prevision.AnalysisResult(
            symbol="BTCUSDC",
            tf_minutes=15,
            close=100.0,
            swing_high=110.0,
            swing_low=90.0,
            score=2,
            bias="moderate",
            support_level=95.0,
            bounce_percent=1.5,
            take_profit_percent=3.0,
            stop_percent=1.2,
            btc_alert=True,
            acquistopulito=False,
            quantity=0.01,
            command="/B BTCUSDC 1.5 0.01 95 tf=15 btc_alert",
            summary_lines=["linea 1", "linea 2"],
        )

    monkeypatch.setattr(prevision, "analyze_symbol", _fake_analyze_symbol)

    asyncio.run(bot._cmd_prevision(_DummyUpdate(), ["/prevision", "BTCUSDC", "100", "15", "90"]))

    assert captured["chunked"] == [["Prevision pronta:", "linea 1", "linea 2"]]
    assert captured["messages"] == ["/B BTCUSDC 1.5 0.01 95 tf=15 btc_alert"]

    bot._storage.close()


def test_prevision_guided_flow_sends_command_in_separate_message(tmp_path, monkeypatch):
    bot = _make_bot(tmp_path)
    bot._validate_spot_symbol = lambda symbol, field_name="SYMBOL": (True, "")

    captured = {"chunked": [], "messages": []}

    async def _capture_send(update, text, reply_markup=None):
        captured["messages"].append(text)

    async def _capture_chunked(update, lines, max_chars=3500):
        captured["chunked"].append(list(lines))

    async def _noop_show_main_menu(update, text=None):
        return None

    bot._send = _capture_send
    bot._send_chunked = _capture_chunked
    bot._show_main_menu = _noop_show_main_menu

    def _fake_analyze_symbol(symbol, tf_minutes, budget_quote, lookback_bars):
        return prevision.AnalysisResult(
            symbol="BTCUSDC",
            tf_minutes=15,
            close=100.0,
            swing_high=110.0,
            swing_low=90.0,
            score=2,
            bias="moderate",
            support_level=95.0,
            bounce_percent=1.5,
            take_profit_percent=3.0,
            stop_percent=1.2,
            btc_alert=True,
            acquistopulito=False,
            quantity=0.01,
            command="/B BTCUSDC 1.5 0.01 95 tf=15 btc_alert",
            summary_lines=["linea 1", "linea 2"],
        )

    monkeypatch.setattr(prevision, "analyze_symbol", _fake_analyze_symbol)

    context = _DummyContext()
    context.user_data["ui_state"] = "prevision_lookback"
    context.user_data["ui_draft"] = {
        "symbol": "BTCUSDC",
        "budget": 100.0,
        "tf": 15,
    }

    asyncio.run(bot._handle_guided_flow(_DummyUpdate(), context, "90"))

    assert captured["chunked"] == [["Prevision pronta:", "linea 1", "linea 2"]]
    assert "/B BTCUSDC 1.5 0.01 95 tf=15 btc_alert" in captured["messages"]

    bot._storage.close()