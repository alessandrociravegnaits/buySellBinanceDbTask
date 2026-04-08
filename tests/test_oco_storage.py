import os
import sqlite3
import tempfile
import json
from storage import SQLiteStorage


def test_save_and_update_oco(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    storage = SQLiteStorage(db_path, archive_dir)

    order_id = storage.next_order_id()
    legs = [
        {"leg_index": 1, "ordertype": "limit", "price": 110.0, "qty": 1.0, "side": "sell"},
        {"leg_index": 2, "ordertype": "limit", "price": 90.0, "qty": 1.0, "side": "sell"},
    ]

    storage.save_oco_order(
        order_id=order_id,
        chat_id=123,
        symbol="BTCUSDT",
        side="sell",
        legs=legs,
        hook_symbol=None,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        status="active",
    )

    # Verify parent
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT order_id, symbol, side FROM order_oco WHERE order_id = ?", (order_id,))
    row = cur.fetchone()
    assert row is not None and row[0] == order_id and row[1] == "BTCUSDT"

    # Verify legs
    cur.execute("SELECT leg_index, ordertype, price, qty, side FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    legs_rows = cur.fetchall()
    assert len(legs_rows) == 2
    assert legs_rows[0][0] == 1 and legs_rows[0][1] == "limit"

    # Update core id and status
    storage.update_oco_leg_core_order_id(order_id, 1, -101)
    storage.update_oco_leg_status(order_id, 1, "filled")

    cur.execute("SELECT core_order_id, status FROM order_oco_leg WHERE order_id = ? AND leg_index = 1", (order_id,))
    r = cur.fetchone()
    assert r[0] == -101 and r[1] == "filled"

    conn.close()
    storage.close()


def test_post_fill_action_persistence(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    storage = SQLiteStorage(db_path, archive_dir)

    parent_id = storage.next_order_id()
    post_fill_action = {
        "type": "oco",
        "tp": {"mode": "percent", "value": 3.0},
        "sl": {"mode": "fixed", "value": 65000.0},
    }
    storage.save_simple_order(
        order_id=parent_id,
        chat_id=1,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger_value=67000.0,
        qty=0.001,
        hook_symbol=None,
        core_order_id=parent_id,
        btc_alert_liquidate=False,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        post_fill_action=post_fill_action,
        status="active",
    )

    oco_id = storage.next_order_id()
    storage.save_oco_order(
        order_id=oco_id,
        chat_id=1,
        symbol="BTCUSDT",
        side="sell",
        legs=[{"leg_index": 1, "ordertype": "limit", "price": 70000.0, "qty": 0.001, "side": "sell"}],
        hook_symbol=None,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        parent_order_id=parent_id,
        status="active",
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT post_fill_action FROM order_simple WHERE order_id = ?", (parent_id,))
    row = cur.fetchone()
    assert row is not None
    assert json.loads(row[0])["type"] == "oco"

    cur.execute("SELECT parent_order_id FROM order_oco WHERE order_id = ?", (oco_id,))
    oco_row = cur.fetchone()
    assert oco_row is not None
    assert oco_row[0] == parent_id

    conn.close()
    storage.close()


def test_btc_alert_liquidate_flag_persistence(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    storage = SQLiteStorage(db_path, archive_dir)

    simple_id = storage.next_order_id()
    storage.save_simple_order(
        order_id=simple_id,
        chat_id=7,
        side="sell",
        symbol="ETHUSDT",
        op=">",
        trigger_value=3000.0,
        qty=0.25,
        hook_symbol=None,
        core_order_id=None,
        btc_alert_liquidate=True,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        post_fill_action=None,
        status="active",
    )

    oco_id = storage.next_order_id()
    storage.save_oco_order(
        order_id=oco_id,
        chat_id=7,
        symbol="BTCUSDT",
        side="sell",
        legs=[{"leg_index": 1, "ordertype": "limit", "price": 72000.0, "qty": 0.001, "side": "sell"}],
        hook_symbol=None,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        btc_alert_liquidate=True,
        status="active",
    )

    active = storage.load_active_orders()
    assert active["simple"][0]["btc_alert_liquidate"] == 1
    assert active["oco"][0]["btc_alert_liquidate"] == 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT btc_alert_liquidate FROM orders WHERE order_id = ?", (simple_id,))
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT btc_alert_liquidate FROM orders WHERE order_id = ?", (oco_id,))
    assert cur.fetchone()[0] == 1
    conn.close()
    storage.close()


def test_oco_trailing_leg_persistence(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    storage = SQLiteStorage(db_path, archive_dir)
    order_id = storage.next_order_id()
    legs = [
        {"leg_index": 1, "ordertype": "limit", "price": 71000.0, "qty": 0.01, "side": "sell"},
        {"leg_index": 2, "ordertype": "trailing", "trail_percent": 1.5, "qty": 0.01, "side": "sell"},
    ]

    storage.save_oco_order(
        order_id=order_id,
        chat_id=321,
        symbol="BTCUSDT",
        side="sell",
        legs=legs,
        hook_symbol=None,
        tf_minutes=15,
        next_eval_at=None,
        last_eval_at=None,
        parent_order_id=99,
        status="active",
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT ordertype, trail_percent FROM order_oco_leg WHERE order_id = ? AND leg_index = 2", (order_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "trailing"
    assert float(row[1]) == 1.5
    conn.close()
    storage.close()
