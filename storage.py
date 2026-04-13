"""Persistenza SQLite per ordini, impostazioni bot e storico eventi."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

import logging

log = logging.getLogger(__name__)


class SQLiteStorage:
    def __init__(self, db_path: str, archive_dir: str):
        self._db_path = db_path
        self._archive_dir = archive_dir
        db_exists_before = os.path.exists(db_path)
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(self._archive_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema(self._conn)
        self._migrate_schema(self._conn)
        if not db_exists_before:
            log.info("Creato nuovo database SQLite: %s", self._db_path)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _init_schema(conn: sqlite3.Connection):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                btc_alert_liquidate INTEGER NOT NULL DEFAULT 0,
                tf_minutes INTEGER NOT NULL DEFAULT 15,
                next_eval_at INTEGER,
                last_eval_at INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_simple (
                order_id INTEGER PRIMARY KEY,
                side TEXT NOT NULL,
                symbol TEXT NOT NULL,
                op TEXT NOT NULL,
                trigger_value REAL NOT NULL,
                qty REAL NOT NULL,
                hook_symbol TEXT,
                core_order_id INTEGER,
                post_fill_action TEXT,
                acquistopulito INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS order_function (
                order_id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                op TEXT NOT NULL,
                trigger_value REAL NOT NULL,
                qty REAL NOT NULL,
                percent REAL NOT NULL,
                hook_symbol TEXT,
                bought INTEGER NOT NULL DEFAULT 0,
                prev_price REAL,
                post_fill_action TEXT,
                acquistopulito INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS order_trailing (
                order_id INTEGER PRIMARY KEY,
                side TEXT NOT NULL,
                symbol TEXT NOT NULL,
                qty REAL NOT NULL,
                percent REAL NOT NULL,
                limit_price REAL,
                hook_symbol TEXT,
                armed INTEGER NOT NULL DEFAULT 0,
                max_price REAL,
                min_price REAL,
                arm_op TEXT,
                post_fill_action TEXT,
                acquistopulito INTEGER NOT NULL DEFAULT 0,
                oco_parent_order_id INTEGER,
                oco_leg_index INTEGER,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS order_oco (
                order_id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                hook_symbol TEXT,
                parent_order_id INTEGER,
                acquistopulito INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS order_oco_leg (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                leg_index INTEGER NOT NULL,
                ordertype TEXT NOT NULL,
                price REAL,
                stop_price REAL,
                limit_price REAL,
                trail_percent REAL,
                qty REAL NOT NULL,
                side TEXT NOT NULL,
                core_order_id INTEGER,
                status TEXT NOT NULL DEFAULT 'waiting',
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                event_type TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
        if "tf_minutes" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN tf_minutes INTEGER NOT NULL DEFAULT 15")
        if "next_eval_at" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN next_eval_at INTEGER")
        if "last_eval_at" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN last_eval_at INTEGER")
        if "btc_alert_liquidate" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN btc_alert_liquidate INTEGER NOT NULL DEFAULT 0")

        simple_cols = {row[1] for row in conn.execute("PRAGMA table_info(order_simple)").fetchall()}
        if "post_fill_action" not in simple_cols:
            conn.execute("ALTER TABLE order_simple ADD COLUMN post_fill_action TEXT")
        if "acquistopulito" not in simple_cols:
            conn.execute("ALTER TABLE order_simple ADD COLUMN acquistopulito INTEGER NOT NULL DEFAULT 0")

        function_cols = {row[1] for row in conn.execute("PRAGMA table_info(order_function)").fetchall()}
        if "post_fill_action" not in function_cols:
            conn.execute("ALTER TABLE order_function ADD COLUMN post_fill_action TEXT")
        if "acquistopulito" not in function_cols:
            conn.execute("ALTER TABLE order_function ADD COLUMN acquistopulito INTEGER NOT NULL DEFAULT 0")

        trailing_cols = {row[1] for row in conn.execute("PRAGMA table_info(order_trailing)").fetchall()}
        if "post_fill_action" not in trailing_cols:
            conn.execute("ALTER TABLE order_trailing ADD COLUMN post_fill_action TEXT")
        if "acquistopulito" not in trailing_cols:
            conn.execute("ALTER TABLE order_trailing ADD COLUMN acquistopulito INTEGER NOT NULL DEFAULT 0")
        if "oco_parent_order_id" not in trailing_cols:
            conn.execute("ALTER TABLE order_trailing ADD COLUMN oco_parent_order_id INTEGER")
        if "oco_leg_index" not in trailing_cols:
            conn.execute("ALTER TABLE order_trailing ADD COLUMN oco_leg_index INTEGER")

        oco_leg_cols = {row[1] for row in conn.execute("PRAGMA table_info(order_oco_leg)").fetchall()}
        if "trail_percent" not in oco_leg_cols:
            conn.execute("ALTER TABLE order_oco_leg ADD COLUMN trail_percent REAL")

        oco_cols = {row[1] for row in conn.execute("PRAGMA table_info(order_oco)").fetchall()}
        if "parent_order_id" not in oco_cols:
            conn.execute("ALTER TABLE order_oco ADD COLUMN parent_order_id INTEGER")
        if "acquistopulito" not in oco_cols:
            conn.execute("ALTER TABLE order_oco ADD COLUMN acquistopulito INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    def next_order_id(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COALESCE(MAX(order_id), 0) + 1 AS next_id FROM orders")
            return int(cur.fetchone()["next_id"])

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            cur = self._conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        now = self._now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO bot_settings(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
            self._conn.commit()

    def append_event(self, event_type: str, order_id: Optional[int] = None, payload: Optional[Dict[str, Any]] = None):
        now = self._now_iso()
        payload_json = json.dumps(payload or {}, ensure_ascii=True)
        with self._lock:
            self._conn.execute(
                "INSERT INTO event_log(order_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?)",
                (order_id, event_type, payload_json, now),
            )
            self._conn.commit()

    @staticmethod
    def _extract_event_price(payload_json: Optional[str]) -> Optional[float]:
        if not payload_json:
            return None
        try:
            payload = json.loads(payload_json)
        except Exception:
            return None

        for key in ("price", "fill_price", "entry_price", "exit_price"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _gain_event_types(kind: str, side: Optional[str]) -> List[str]:
        kind_norm = (kind or "").strip().lower()
        side_norm = (side or "").strip().lower()
        if kind_norm == "simple":
            return ["simple_filled"]
        if kind_norm == "function":
            return ["function_filled"]
        if kind_norm == "trailing":
            return ["trailing_sell_filled"] if side_norm == "sell" else ["trailing_buy_filled"]
        if kind_norm == "oco":
            return ["oco_leg_filled"]
        return []

    def _get_order_meta_locked(self, order_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            """
            SELECT o.kind,
                   s.side AS simple_side,
                   t.side AS trailing_side,
                   oc.side AS oco_side,
                   oc.parent_order_id
            FROM orders o
            LEFT JOIN order_simple s ON s.order_id = o.order_id
            LEFT JOIN order_trailing t ON t.order_id = o.order_id
            LEFT JOIN order_oco oc ON oc.order_id = o.order_id
            WHERE o.order_id = ?
            """,
            (order_id,),
        ).fetchone()
        if not row:
            return None

        side = row["simple_side"] or row["trailing_side"] or row["oco_side"]
        return {
            "kind": row["kind"],
            "side": side,
            "parent_order_id": row["parent_order_id"],
        }

    def _get_first_event_price_locked(self, order_id: int, event_types: List[str]) -> Optional[float]:
        if not event_types:
            return None
        placeholders = ",".join(["?"] * len(event_types))
        rows = self._conn.execute(
            f"""
            SELECT payload_json
            FROM event_log
            WHERE order_id = ? AND event_type IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            (order_id, *event_types),
        ).fetchall()
        for row in rows:
            price = self._extract_event_price(row["payload_json"])
            if price is not None:
                return price
        return None

    def _get_child_oco_order_id_locked(self, parent_order_id: int) -> Optional[int]:
        row = self._conn.execute(
            "SELECT order_id FROM order_oco WHERE parent_order_id = ? ORDER BY order_id ASC LIMIT 1",
            (parent_order_id,),
        ).fetchone()
        return int(row["order_id"]) if row else None

    def _get_order_gain_summary_locked(self, order_id: int) -> Dict[str, Optional[float]]:
        meta = self._get_order_meta_locked(order_id)
        if not meta:
            return {"entry_price": None, "exit_price": None, "gain_pct": None}

        kind = (meta.get("kind") or "").strip().lower()
        side = (meta.get("side") or "").strip().lower()
        parent_order_id = meta.get("parent_order_id")

        entry_price: Optional[float] = None
        exit_price: Optional[float] = None

        if kind == "oco" and parent_order_id is not None:
            parent_meta = self._get_order_meta_locked(int(parent_order_id))
            if parent_meta:
                parent_kind = (parent_meta.get("kind") or "").strip().lower()
                parent_side = (parent_meta.get("side") or "").strip().lower()
                parent_event_types = self._gain_event_types(parent_kind, parent_side)
                entry_price = self._get_first_event_price_locked(int(parent_order_id), parent_event_types)
                exit_price = self._get_first_event_price_locked(order_id, ["oco_leg_filled"])
        else:
            event_types = self._gain_event_types(kind, side)
            entry_price = self._get_first_event_price_locked(order_id, event_types)
            child_oco_order_id = self._get_child_oco_order_id_locked(order_id)
            if child_oco_order_id is not None:
                exit_price = self._get_first_event_price_locked(child_oco_order_id, ["oco_leg_filled"])

        gain_pct: Optional[float] = None
        if entry_price is not None and exit_price is not None and entry_price != 0:
            gain_pct = ((exit_price - entry_price) / entry_price) * 100.0

        return {
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gain_pct": gain_pct,
        }

    def get_order_gain_summary(self, order_id: int) -> Dict[str, Optional[float]]:
        with self._lock:
            return self._get_order_gain_summary_locked(order_id)

    def save_simple_order(
        self,
        order_id: int,
        chat_id: int,
        side: str,
        symbol: str,
        op: str,
        trigger_value: float,
        qty: float,
        hook_symbol: Optional[str],
        core_order_id: Optional[int],
        tf_minutes: int,
        next_eval_at: Optional[int],
        last_eval_at: Optional[int],
        post_fill_action: Optional[Dict[str, Any]] = None,
        acquistopulito: bool = False,
        btc_alert_liquidate: bool = False,
        status: str = "active",
    ):
        now = self._now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO orders(order_id, chat_id, kind, status, btc_alert_liquidate, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (order_id, chat_id, "simple", status, int(btc_alert_liquidate), now, now),
            )
            self._conn.execute(
                "UPDATE orders SET tf_minutes = ?, next_eval_at = ?, last_eval_at = ? WHERE order_id = ?",
                (tf_minutes, next_eval_at, last_eval_at, order_id),
            )
            self._conn.execute(
                """
                INSERT INTO order_simple(order_id, side, symbol, op, trigger_value, qty, hook_symbol, core_order_id, post_fill_action, acquistopulito)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    side,
                    symbol,
                    op,
                    trigger_value,
                    qty,
                    hook_symbol,
                    core_order_id,
                    json.dumps(post_fill_action, ensure_ascii=True) if post_fill_action else None,
                    int(acquistopulito),
                ),
            )
            self._conn.commit()

    def save_function_order(
        self,
        order_id: int,
        chat_id: int,
        symbol: str,
        op: str,
        trigger_value: float,
        qty: float,
        percent: float,
        hook_symbol: Optional[str],
        bought: bool,
        prev_price: Optional[float],
        tf_minutes: int,
        next_eval_at: Optional[int],
        last_eval_at: Optional[int],
        post_fill_action: Optional[Dict[str, Any]] = None,
        acquistopulito: bool = False,
        btc_alert_liquidate: bool = False,
        status: str = "active",
    ):
        now = self._now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO orders(order_id, chat_id, kind, status, btc_alert_liquidate, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (order_id, chat_id, "function", status, int(btc_alert_liquidate), now, now),
            )
            self._conn.execute(
                "UPDATE orders SET tf_minutes = ?, next_eval_at = ?, last_eval_at = ? WHERE order_id = ?",
                (tf_minutes, next_eval_at, last_eval_at, order_id),
            )
            self._conn.execute(
                """
                INSERT INTO order_function(order_id, symbol, op, trigger_value, qty, percent, hook_symbol, bought, prev_price, post_fill_action, acquistopulito)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    symbol,
                    op,
                    trigger_value,
                    qty,
                    percent,
                    hook_symbol,
                    int(bought),
                    prev_price,
                    json.dumps(post_fill_action, ensure_ascii=True) if post_fill_action else None,
                    int(acquistopulito),
                ),
            )
            self._conn.commit()

    def save_trailing_order(
        self,
        order_id: int,
        chat_id: int,
        side: str,
        symbol: str,
        qty: float,
        percent: float,
        limit_price: Optional[float],
        hook_symbol: Optional[str],
        armed: bool,
        max_price: Optional[float],
        min_price: Optional[float],
        arm_op: Optional[str],
        tf_minutes: int,
        next_eval_at: Optional[int],
        last_eval_at: Optional[int],
        post_fill_action: Optional[Dict[str, Any]] = None,
        acquistopulito: bool = False,
        btc_alert_liquidate: bool = False,
        oco_parent_order_id: Optional[int] = None,
        oco_leg_index: Optional[int] = None,
        status: str = "active",
    ):
        now = self._now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO orders(order_id, chat_id, kind, status, btc_alert_liquidate, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (order_id, chat_id, "trailing", status, int(btc_alert_liquidate), now, now),
            )
            self._conn.execute(
                "UPDATE orders SET tf_minutes = ?, next_eval_at = ?, last_eval_at = ? WHERE order_id = ?",
                (tf_minutes, next_eval_at, last_eval_at, order_id),
            )
            self._conn.execute(
                """
                INSERT INTO order_trailing(order_id, side, symbol, qty, percent, limit_price, hook_symbol, armed, max_price, min_price, arm_op, post_fill_action, acquistopulito, oco_parent_order_id, oco_leg_index)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    side,
                    symbol,
                    qty,
                    percent,
                    limit_price,
                    hook_symbol,
                    int(armed),
                    max_price,
                    min_price,
                    arm_op,
                    json.dumps(post_fill_action, ensure_ascii=True) if post_fill_action else None,
                    int(acquistopulito),
                    oco_parent_order_id,
                    oco_leg_index,
                ),
            )
            self._conn.commit()

    def save_oco_order(
        self,
        order_id: int,
        chat_id: int,
        symbol: str,
        side: str,
        legs: List[Dict[str, Any]],
        hook_symbol: Optional[str],
        tf_minutes: int,
        next_eval_at: Optional[int],
        last_eval_at: Optional[int],
        parent_order_id: Optional[int] = None,
        acquistopulito: bool = False,
        btc_alert_liquidate: bool = False,
        status: str = "active",
    ):
        """Persist an OCO order with its legs.

        `legs` is a list of dicts with keys: leg_index, ordertype, price?, stop_price?, limit_price?, qty, side
        """
        now = self._now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO orders(order_id, chat_id, kind, status, btc_alert_liquidate, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (order_id, chat_id, "oco", status, int(btc_alert_liquidate), now, now),
            )
            self._conn.execute(
                "UPDATE orders SET tf_minutes = ?, next_eval_at = ?, last_eval_at = ? WHERE order_id = ?",
                (tf_minutes, next_eval_at, last_eval_at, order_id),
            )
            self._conn.execute(
                "INSERT INTO order_oco(order_id, symbol, side, hook_symbol, parent_order_id, acquistopulito) VALUES(?, ?, ?, ?, ?, ?)",
                (order_id, symbol, side, hook_symbol, parent_order_id, int(acquistopulito)),
            )
            for leg in legs:
                self._conn.execute(
                    """
                    INSERT INTO order_oco_leg(order_id, leg_index, ordertype, price, stop_price, limit_price, trail_percent, qty, side, core_order_id, status)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        leg.get("leg_index"),
                        leg.get("ordertype"),
                        leg.get("price"),
                        leg.get("stop_price"),
                        leg.get("limit_price"),
                        leg.get("trail_percent"),
                        leg.get("qty"),
                        leg.get("side"),
                        leg.get("core_order_id"),
                        leg.get("status", "waiting"),
                    ),
                )
            self._conn.commit()

    def update_oco_leg_core_order_id(self, order_id: int, leg_index: int, core_order_id: int):
        with self._lock:
            self._conn.execute(
                "UPDATE order_oco_leg SET core_order_id = ? WHERE order_id = ? AND leg_index = ?",
                (core_order_id, order_id, leg_index),
            )
            self._conn.execute("UPDATE orders SET updated_at = ? WHERE order_id = ?", (self._now_iso(), order_id))
            self._conn.commit()

    def update_oco_leg_status(self, order_id: int, leg_index: int, status: str):
        with self._lock:
            self._conn.execute(
                "UPDATE order_oco_leg SET status = ? WHERE order_id = ? AND leg_index = ?",
                (status, order_id, leg_index),
            )
            self._conn.execute("UPDATE orders SET updated_at = ? WHERE order_id = ?", (self._now_iso(), order_id))
            self._conn.commit()

    def update_simple_core_order_id(self, order_id: int, core_order_id: int):
        with self._lock:
            self._conn.execute("UPDATE order_simple SET core_order_id = ? WHERE order_id = ?", (core_order_id, order_id))
            self._conn.execute("UPDATE orders SET updated_at = ? WHERE order_id = ?", (self._now_iso(), order_id))
            self._conn.commit()

    def update_order_status(self, order_id: int, status: str):
        with self._lock:
            self._conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?", (status, self._now_iso(), order_id))
            self._conn.commit()

    def update_order_schedule(
        self,
        order_id: int,
        next_eval_at: Optional[int],
        last_eval_at: Optional[int],
    ):
        with self._lock:
            self._conn.execute(
                "UPDATE orders SET next_eval_at = ?, last_eval_at = ?, updated_at = ? WHERE order_id = ?",
                (next_eval_at, last_eval_at, self._now_iso(), order_id),
            )
            self._conn.commit()

    def update_function_runtime(self, order_id: int, bought: bool, prev_price: Optional[float]):
        with self._lock:
            self._conn.execute(
                "UPDATE order_function SET bought = ?, prev_price = ? WHERE order_id = ?",
                (int(bought), prev_price, order_id),
            )
            self._conn.execute("UPDATE orders SET updated_at = ? WHERE order_id = ?", (self._now_iso(), order_id))
            self._conn.commit()

    def update_trailing_runtime(
        self,
        order_id: int,
        armed: bool,
        max_price: Optional[float],
        min_price: Optional[float],
        arm_op: Optional[str],
    ):
        with self._lock:
            self._conn.execute(
                """
                UPDATE order_trailing
                SET armed = ?, max_price = ?, min_price = ?, arm_op = ?
                WHERE order_id = ?
                """,
                (int(armed), max_price, min_price, arm_op, order_id),
            )
            self._conn.execute("UPDATE orders SET updated_at = ? WHERE order_id = ?", (self._now_iso(), order_id))
            self._conn.commit()

    def load_active_orders(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            simple = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, s.side, s.symbol, s.op, s.trigger_value, s.qty, s.hook_symbol, s.core_order_id
                     , s.post_fill_action, s.acquistopulito
                     , o.btc_alert_liquidate
                     , o.tf_minutes, o.next_eval_at, o.last_eval_at
                FROM orders o
                JOIN order_simple s ON s.order_id = o.order_id
                WHERE o.status = 'active'
                ORDER BY o.order_id
                """
            ).fetchall()

            function = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, f.symbol, f.op, f.trigger_value, f.qty, f.percent, f.hook_symbol, f.bought, f.prev_price
                     , f.post_fill_action, f.acquistopulito
                     , o.btc_alert_liquidate
                     , o.tf_minutes, o.next_eval_at, o.last_eval_at
                FROM orders o
                JOIN order_function f ON f.order_id = o.order_id
                WHERE o.status = 'active'
                ORDER BY o.order_id
                """
            ).fetchall()

            trailing = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, t.side, t.symbol, t.qty, t.percent, t.limit_price, t.hook_symbol, t.armed, t.max_price, t.min_price, t.arm_op
                     , t.post_fill_action, t.acquistopulito, t.oco_parent_order_id, t.oco_leg_index
                     , o.btc_alert_liquidate
                     , o.tf_minutes, o.next_eval_at, o.last_eval_at
                FROM orders o
                JOIN order_trailing t ON t.order_id = o.order_id
                WHERE o.status = 'active'
                ORDER BY o.order_id
                """
            ).fetchall()

            # OCO orders: parent + legs
            oco_parents = self._conn.execute(
                """
                 SELECT o.order_id, o.chat_id, o.status, oc.symbol, oc.side, oc.parent_order_id, oc.acquistopulito
                     , o.btc_alert_liquidate
                     , o.tf_minutes, o.next_eval_at, o.last_eval_at
                FROM orders o
                JOIN order_oco oc ON oc.order_id = o.order_id
                WHERE o.status = 'active'
                ORDER BY o.order_id
                """
            ).fetchall()

            oco = []
            for p in oco_parents:
                oid = p["order_id"]
                legs = self._conn.execute(
                    "SELECT leg_index, ordertype, price, stop_price, limit_price, trail_percent, qty, side, core_order_id, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index",
                    (oid,),
                ).fetchall()
                oco.append({
                    **dict(p),
                    "legs": [dict(l) for l in legs],
                })

        return cast(Dict[str, List[Dict[str, Any]]], {
            "simple": [dict(r) for r in simple],
            "function": [dict(r) for r in function],
            "trailing": [dict(r) for r in trailing],
            "oco": oco,
        })

    def load_historical_orders(self, days: int) -> Dict[str, List[Dict[str, Any]]]:
        if days <= 0:
            raise ValueError("days deve essere > 0")

        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
        with self._lock:
            simple = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, o.kind, o.tf_minutes, o.next_eval_at, o.last_eval_at, o.created_at, o.updated_at,
                      s.side, s.symbol, s.op, s.trigger_value, s.qty, s.hook_symbol, s.core_order_id, s.post_fill_action, s.acquistopulito,
                      o.btc_alert_liquidate
                FROM orders o
                JOIN order_simple s ON s.order_id = o.order_id
                WHERE o.status != 'active' AND o.updated_at >= ?
                ORDER BY o.updated_at DESC, o.order_id DESC
                """,
                (cutoff_iso,),
            ).fetchall()

            simple_rows = [dict(r) for r in simple]
            for row in simple_rows:
                row.update(self._get_order_gain_summary_locked(int(row["order_id"])))

            function = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, o.kind, o.tf_minutes, o.next_eval_at, o.last_eval_at, o.created_at, o.updated_at,
                      f.symbol, f.op, f.trigger_value, f.qty, f.percent, f.hook_symbol, f.bought, f.prev_price, f.post_fill_action, f.acquistopulito,
                      o.btc_alert_liquidate
                FROM orders o
                JOIN order_function f ON f.order_id = o.order_id
                WHERE o.status != 'active' AND o.updated_at >= ?
                ORDER BY o.updated_at DESC, o.order_id DESC
                """,
                (cutoff_iso,),
            ).fetchall()

            function_rows = [dict(r) for r in function]
            for row in function_rows:
                row.update(self._get_order_gain_summary_locked(int(row["order_id"])))

            trailing = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, o.kind, o.tf_minutes, o.next_eval_at, o.last_eval_at, o.created_at, o.updated_at,
                       t.side, t.symbol, t.qty, t.percent, t.limit_price, t.hook_symbol, t.armed, t.max_price, t.min_price, t.arm_op,
                      t.post_fill_action, t.acquistopulito, t.oco_parent_order_id, t.oco_leg_index,
                      o.btc_alert_liquidate
                FROM orders o
                JOIN order_trailing t ON t.order_id = o.order_id
                WHERE o.status != 'active' AND o.updated_at >= ?
                ORDER BY o.updated_at DESC, o.order_id DESC
                """,
                (cutoff_iso,),
            ).fetchall()

            trailing_rows = [dict(r) for r in trailing]
            for row in trailing_rows:
                row.update(self._get_order_gain_summary_locked(int(row["order_id"])))

            oco_parents = self._conn.execute(
                """
                SELECT o.order_id, o.chat_id, o.status, o.kind, o.tf_minutes, o.next_eval_at, o.last_eval_at, o.created_at, o.updated_at,
                      oc.symbol, oc.side, oc.parent_order_id, oc.acquistopulito, o.btc_alert_liquidate
                FROM orders o
                JOIN order_oco oc ON oc.order_id = o.order_id
                WHERE o.status != 'active' AND o.updated_at >= ?
                ORDER BY o.updated_at DESC, o.order_id DESC
                """,
                (cutoff_iso,),
            ).fetchall()

            oco = []
            for p in oco_parents:
                oid = p["order_id"]
                legs = self._conn.execute(
                    "SELECT leg_index, ordertype, price, stop_price, limit_price, trail_percent, qty, side, core_order_id, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index",
                    (oid,),
                ).fetchall()
                row = dict(p)
                row.update(self._get_order_gain_summary_locked(int(oid)))
                row["legs"] = [dict(l) for l in legs]
                oco.append(row)

        return cast(Dict[str, List[Dict[str, Any]]], {
            "simple": simple_rows,
            "function": function_rows,
            "trailing": trailing_rows,
            "oco": oco,
        })

    def archive_closed_orders_by_month(self):
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")

        with self._lock:
            months = self._conn.execute(
                """
                SELECT DISTINCT substr(updated_at, 1, 7) AS ym
                FROM orders
                WHERE status != 'active' AND substr(updated_at, 1, 7) < ?
                ORDER BY ym
                """,
                (current_month,),
            ).fetchall()

            month_list = [r["ym"] for r in months if r["ym"]]

            for ym in month_list:
                archive_path = os.path.join(self._archive_dir, f"archive_{ym.replace('-', '_')}.sqlite3")
                archive_conn = sqlite3.connect(archive_path)
                archive_conn.row_factory = sqlite3.Row
                archive_conn.execute("PRAGMA foreign_keys = ON")
                self._init_schema(archive_conn)
                self._migrate_schema(archive_conn)

                order_rows = self._conn.execute(
                    "SELECT * FROM orders WHERE status != 'active' AND substr(updated_at, 1, 7) = ?",
                    (ym,),
                ).fetchall()
                order_ids = [r["order_id"] for r in order_rows]

                for row in order_rows:
                    archive_conn.execute(
                        """
                        INSERT OR IGNORE INTO orders(
                            order_id, chat_id, kind, status, btc_alert_liquidate, tf_minutes, next_eval_at, last_eval_at, created_at, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["order_id"],
                            row["chat_id"],
                            row["kind"],
                            row["status"],
                            row["btc_alert_liquidate"],
                            row["tf_minutes"],
                            row["next_eval_at"],
                            row["last_eval_at"],
                            row["created_at"],
                            row["updated_at"],
                        ),
                    )

                for table_name in ("order_simple", "order_function", "order_trailing"):
                    for oid in order_ids:
                        child = self._conn.execute(f"SELECT * FROM {table_name} WHERE order_id = ?", (oid,)).fetchone()
                        if not child:
                            continue
                        cols = list(child.keys())
                        placeholders = ",".join(["?"] * len(cols))
                        col_list = ",".join(cols)
                        archive_conn.execute(
                            f"INSERT OR IGNORE INTO {table_name}({col_list}) VALUES({placeholders})",
                            tuple(child[c] for c in cols),
                        )

                # handle OCO parent record
                for table_name in ("order_oco",):
                    for oid in order_ids:
                        child = self._conn.execute(f"SELECT * FROM {table_name} WHERE order_id = ?", (oid,)).fetchone()
                        if not child:
                            continue
                        cols = list(child.keys())
                        placeholders = ",".join(["?"] * len(cols))
                        col_list = ",".join(cols)
                        archive_conn.execute(
                            f"INSERT OR IGNORE INTO {table_name}({col_list}) VALUES({placeholders})",
                            tuple(child[c] for c in cols),
                        )

                # handle OCO legs (may be multiple rows per order)
                for oid in order_ids:
                    legs = self._conn.execute("SELECT * FROM order_oco_leg WHERE order_id = ?", (oid,)).fetchall()
                    for leg in legs:
                        cols = list(leg.keys())
                        placeholders = ",".join(["?"] * len(cols))
                        col_list = ",".join(cols)
                        archive_conn.execute(
                            f"INSERT OR IGNORE INTO order_oco_leg({col_list}) VALUES({placeholders})",
                            tuple(leg[c] for c in cols),
                        )

                events = self._conn.execute(
                    "SELECT * FROM event_log WHERE substr(created_at, 1, 7) = ?",
                    (ym,),
                ).fetchall()
                for ev in events:
                    archive_conn.execute(
                        "INSERT OR IGNORE INTO event_log(id, order_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?, ?)",
                        (ev["id"], ev["order_id"], ev["event_type"], ev["payload_json"], ev["created_at"]),
                    )

                archive_conn.commit()
                archive_conn.close()

                if order_ids:
                    markers = ",".join(["?"] * len(order_ids))
                    self._conn.execute(f"DELETE FROM orders WHERE order_id IN ({markers})", tuple(order_ids))

                self._conn.execute("DELETE FROM event_log WHERE substr(created_at, 1, 7) = ?", (ym,))
                self._conn.commit()

