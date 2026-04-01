"""Interfaccia Telegram con persistenza SQLite e storico eventi."""

import logging
import os
import queue
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from core import Action, Order, OrderBehavior, Trigger, build_engine
from price_feeds import Binance1mClosePriceFeed
from storage import SQLiteStorage

log = logging.getLogger(__name__)

VALID_TF_MINUTES = {1, 5, 15, 30, 60, 120, 240, 1440}


@dataclass
class SimpleOrderSpec:
    order_id: int
    side: str
    symbol: str
    op: str
    trigger: float
    qty: float
    chat_id: int
    hook_symbol: Optional[str] = None
    core_order_id: Optional[int] = None
    tf_minutes: int = 15
    next_eval_at: Optional[int] = None
    last_eval_at: Optional[int] = None
    status: str = "active"


@dataclass
class TrailingSellSpec:
    order_id: int
    symbol: str
    qty: float
    percent: float
    chat_id: int
    limit: Optional[float]
    hook_symbol: Optional[str]
    armed: bool = False
    max_price: Optional[float] = None
    arm_op: Optional[str] = None
    tf_minutes: int = 15
    next_eval_at: Optional[int] = None
    last_eval_at: Optional[int] = None
    status: str = "active"


@dataclass
class TrailingBuySpec:
    order_id: int
    symbol: str
    qty: float
    percent: float
    chat_id: int
    limit: float
    armed: bool = False
    min_price: Optional[float] = None
    arm_op: Optional[str] = None
    tf_minutes: int = 15
    next_eval_at: Optional[int] = None
    last_eval_at: Optional[int] = None
    status: str = "active"


@dataclass
class FunctionSpec:
    order_id: int
    symbol: str
    op: str
    trigger: float
    qty: float
    percent: float
    chat_id: int
    hook_symbol: Optional[str]
    bought: bool = False
    prev_price: Optional[float] = None
    tf_minutes: int = 15
    next_eval_at: Optional[int] = None
    last_eval_at: Optional[int] = None
    status: str = "active"


class TelegramTradingBot:
    def __init__(self, token: str, authorized_chat_id: Optional[int] = None, db_path: str = "data/bot.sqlite3"):
        self._token = token
        self._authorized_chat_id = authorized_chat_id

        self._feed = Binance1mClosePriceFeed()
        self._manager, self._poller = build_engine(symbols=["BTCUSDT"], price_feed=self._feed)
        self._storage = SQLiteStorage(db_path=db_path, archive_dir="data/archive")

        self._next_action_id = 1

        self._sell_orders: List[SimpleOrderSpec] = []
        self._buy_orders: List[SimpleOrderSpec] = []
        self._function_orders: List[FunctionSpec] = []
        self._trailing_sell_orders: List[TrailingSellSpec] = []
        self._trailing_buy_orders: List[TrailingBuySpec] = []

        self._default_tf_minutes = 15
        self._timeframe_seconds = 900
        self._echo_enabled = True
        self._alert_enabled = False
        self._alert_percent = 0.0
        self._alert_reference_price: Optional[float] = None

        self._last_timeframe_tick = 0.0
        self._last_alert_tick = 0.0
        self._last_archive_check = 0.0

        self._notifications: "queue.Queue[Tuple[int, str]]" = queue.Queue()
        self._app: Optional[Application] = None

        self._load_settings()
        self._restore_active_orders()

    def _load_settings(self):
        tf = self._storage.get_setting("default_tf_minutes")
        tf_seconds = self._storage.get_setting("timeframe_seconds")
        echo = self._storage.get_setting("echo_enabled")
        alert_enabled = self._storage.get_setting("alert_enabled")
        alert_percent = self._storage.get_setting("alert_percent")

        if tf:
            self._default_tf_minutes = int(tf)
        if tf_seconds:
            self._timeframe_seconds = int(tf_seconds)
        else:
            self._timeframe_seconds = self._default_tf_minutes * 60
        if echo:
            self._echo_enabled = echo == "1"
        if alert_enabled:
            self._alert_enabled = alert_enabled == "1"
        if alert_percent:
            self._alert_percent = float(alert_percent)

    def _restore_active_orders(self):
        data = self._storage.load_active_orders()

        for row in data["simple"]:
            spec = SimpleOrderSpec(
                order_id=row["order_id"],
                side=row["side"],
                symbol=row["symbol"],
                op=row["op"],
                trigger=row["trigger_value"],
                qty=row["qty"],
                chat_id=row["chat_id"],
                hook_symbol=row["hook_symbol"],
                core_order_id=row["core_order_id"],
                tf_minutes=row.get("tf_minutes", 15),
                next_eval_at=row.get("next_eval_at"),
                last_eval_at=row.get("last_eval_at"),
                status=row["status"],
            )
            spec.next_eval_at = self._next_boundary_epoch(spec.tf_minutes)
            self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, None)
            self._attach_simple_to_engine(spec)
            if spec.side == "sell":
                self._sell_orders.append(spec)
            else:
                self._buy_orders.append(spec)

        for row in data["function"]:
            spec = FunctionSpec(
                    order_id=row["order_id"],
                    symbol=row["symbol"],
                    op=row["op"],
                    trigger=row["trigger_value"],
                    qty=row["qty"],
                    percent=row["percent"],
                    chat_id=row["chat_id"],
                    hook_symbol=row["hook_symbol"],
                    bought=bool(row["bought"]),
                    prev_price=row["prev_price"],
                    tf_minutes=row.get("tf_minutes", 15),
                    next_eval_at=self._next_boundary_epoch(row.get("tf_minutes", 15)),
                    last_eval_at=None,
                    status=row["status"],
                )
            self._function_orders.append(spec)
            self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, None)

        for row in data["trailing"]:
            if row["side"] == "sell":
                spec = TrailingSellSpec(
                        order_id=row["order_id"],
                        symbol=row["symbol"],
                        qty=row["qty"],
                        percent=row["percent"],
                        chat_id=row["chat_id"],
                        limit=row["limit_price"],
                        hook_symbol=row["hook_symbol"],
                        armed=bool(row["armed"]),
                        max_price=row["max_price"],
                        arm_op=row["arm_op"],
                        tf_minutes=row.get("tf_minutes", 15),
                        next_eval_at=self._next_boundary_epoch(row.get("tf_minutes", 15)),
                        last_eval_at=None,
                        status=row["status"],
                    )
                self._trailing_sell_orders.append(spec)
                self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, None)
            else:
                spec = TrailingBuySpec(
                        order_id=row["order_id"],
                        symbol=row["symbol"],
                        qty=row["qty"],
                        percent=row["percent"],
                        chat_id=row["chat_id"],
                        limit=row["limit_price"],
                        armed=bool(row["armed"]),
                        min_price=row["min_price"],
                        arm_op=row["arm_op"],
                        tf_minutes=row.get("tf_minutes", 15),
                        next_eval_at=self._next_boundary_epoch(row.get("tf_minutes", 15)),
                        last_eval_at=None,
                        status=row["status"],
                    )
                self._trailing_buy_orders.append(spec)
                self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, None)

    @staticmethod
    def _next_boundary_epoch(tf_minutes: int, now_ts: Optional[int] = None) -> int:
        now = int(now_ts if now_ts is not None else time.time())
        tf_seconds = int(tf_minutes) * 60
        return (now // tf_seconds + 1) * tf_seconds

    def _extract_tf(self, parts: List[str]) -> Tuple[List[str], int]:
        tf_minutes = self._default_tf_minutes
        filtered = []
        for token in parts:
            lower = token.lower()
            if lower.startswith("tf="):
                tf_minutes = int(lower.split("=", 1)[1])
                continue
            filtered.append(token)

        if tf_minutes not in VALID_TF_MINUTES:
            raise ValueError("Timeframe valido: 1,5,15,30,60,120,240,1440")
        return filtered, tf_minutes

    def _new_order_id(self) -> int:
        return self._storage.next_order_id()

    def _is_authorized(self, update: Update) -> bool:
        if self._authorized_chat_id is None:
            return True
        return bool(update.effective_chat and update.effective_chat.id == self._authorized_chat_id)

    async def _send(self, update: Update, text: str):
        if update.effective_chat:
            await update.effective_chat.send_message(text)

    def _queue_message(self, chat_id: int, text: str):
        self._notifications.put((chat_id, text))

    @staticmethod
    def _exec_symbol(symbol: str, hook_symbol: Optional[str]) -> str:
        """Simbolo di esecuzione: pairhook se presente, altrimenti simbolo trigger."""
        return hook_symbol or symbol

    def _parse_simple_order(self, parts: List[str]) -> Tuple[str, str, float, float, Optional[str]]:
        if len(parts) < 5:
            raise ValueError("Formato: /s SYMBOL <|> TRIGGER QTY [@PAIRHOOK]")
        symbol = parts[1].upper()
        op = parts[2]
        if op not in {"<", ">"}:
            raise ValueError("Operatore non valido: usa < oppure >")
        trigger = float(parts[3])
        qty = float(parts[4])
        hook = None
        if len(parts) >= 6 and parts[5].startswith("@"):
            hook = parts[5][1:].upper()
        return symbol, op, trigger, qty, hook

    def _build_trigger(self, trigger_id: int, op: str, threshold: float) -> Trigger:
        if op == "<":
            return Trigger(trigger_id, lambda p, t=threshold: p < t, f"prezzo < {threshold}")
        return Trigger(trigger_id, lambda p, t=threshold: p > t, f"prezzo > {threshold}")

    def _attach_simple_to_engine(self, spec: SimpleOrderSpec):
        self._poller.add_symbol(spec.symbol)
        if spec.hook_symbol:
            self._poller.add_symbol(spec.hook_symbol)

        action_symbol = spec.hook_symbol or spec.symbol
        action_id = self._next_action_id
        self._next_action_id += 1

        action = Action(
            id=action_id,
            description=f"{spec.side.upper()} {action_symbol}",
            execute=lambda p, s=spec: self._on_simple_fired(s, p),
        )
        trigger = self._build_trigger(0, spec.op, spec.trigger)
        core_order_id = spec.core_order_id or spec.order_id

        self._manager.add_order(
            Order(
                id=core_order_id,
                symbol=spec.symbol,
                triggers=[trigger],
                action=action,
                behavior=OrderBehavior.CANCEL_ON_FIRE,
                tf_minutes=spec.tf_minutes,
                next_eval_at=float(spec.next_eval_at) if spec.next_eval_at is not None else None,
                last_eval_at=float(spec.last_eval_at) if spec.last_eval_at is not None else None,
            )
        )
        spec.core_order_id = core_order_id
        self._storage.update_simple_core_order_id(spec.order_id, core_order_id)

    def _on_simple_fired(self, spec: SimpleOrderSpec, price: float):
        if spec.status != "active":
            return
        spec.status = "filled"
        verb = "Vendita" if spec.side == "sell" else "Acquisto"
        symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
        self._queue_message(spec.chat_id, f"{verb} {symbol} qty={spec.qty} eseguita a {price}")
        self._storage.update_order_status(spec.order_id, "filled")
        self._storage.append_event("simple_filled", spec.order_id, {"price": price})

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        if update.effective_chat:
            context.application.bot_data["last_chat_id"] = update.effective_chat.id
        await self._send(update, "Bot avviato. Usa /info per i comandi disponibili.")

    async def _info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        if update.effective_chat:
            context.application.bot_data["last_chat_id"] = update.effective_chat.id
        text = (
            "Menu comandi:\n"
            "/s SYMBOL <|> TRIGGER QTY [@PAIRHOOK] [tf=MIN] - ordine sell\n"
            "/b SYMBOL <|> TRIGGER QTY [@PAIRHOOK] [tf=MIN] - ordine buy\n"
            "/f SYMBOL <|> TRIGGER QTY PERCENT [@PAIRHOOK] [tf=MIN] - buy poi trailing sell\n"
            "/S SYMBOL PERCENT QTY [LIMIT] [@PAIRHOOK] [tf=MIN] - trailing sell\n"
            "/B SYMBOL PERCENT QTY LIMIT [tf=MIN] - trailing buy\n"
            "/t MINUTI - default tf nuovi ordini (1,5,15,30,60,120,240,1440)\n"
            "/a 0|1 [PERCENT] - alert BTCUSDT\n"
            "/e 0|1 - echo prezzi\n"
            "/o - lista ordini con order_id\n"
            "/c ORDER_ID | /c a - cancella"
        )
        await self._send(update, text)

    async def _on_slash_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update) or not update.effective_message:
            return
        if update.effective_chat:
            context.application.bot_data["last_chat_id"] = update.effective_chat.id

        text = (update.effective_message.text or "").strip()
        if not text.startswith("/"):
            return

        parts = text.split()
        cmd = parts[0]

        try:
            if cmd == "/s":
                await self._cmd_simple(update, parts, side="sell")
            elif cmd == "/b":
                await self._cmd_simple(update, parts, side="buy")
            elif cmd == "/f":
                await self._cmd_f(update, parts)
            elif cmd == "/S":
                await self._cmd_S(update, parts)
            elif cmd == "/B":
                await self._cmd_B(update, parts)
            elif cmd == "/t":
                await self._cmd_t(update, parts)
            elif cmd == "/a":
                await self._cmd_a(update, parts)
            elif cmd == "/e":
                await self._cmd_e(update, parts)
            elif cmd == "/o":
                await self._cmd_o(update)
            elif cmd == "/c":
                await self._cmd_c(update, parts)
            elif cmd in {"/start", "/info"}:
                return
            else:
                await self._send(update, "Comando non riconosciuto. Usa /info")
        except Exception as exc:
            await self._send(update, f"Errore comando: {exc}")

    async def _cmd_simple(self, update: Update, parts: List[str], side: str):
        parts, tf_minutes = self._extract_tf(parts)
        symbol, op, trigger_val, qty, hook = self._parse_simple_order(parts)
        chat_id = update.effective_chat.id
        order_id = self._new_order_id()
        next_eval_at = self._next_boundary_epoch(tf_minutes)

        spec = SimpleOrderSpec(
            order_id=order_id,
            side=side,
            symbol=symbol,
            op=op,
            trigger=trigger_val,
            qty=qty,
            chat_id=chat_id,
            hook_symbol=hook,
            tf_minutes=tf_minutes,
            next_eval_at=next_eval_at,
        )
        self._attach_simple_to_engine(spec)

        self._storage.save_simple_order(
            order_id=spec.order_id,
            chat_id=spec.chat_id,
            side=spec.side,
            symbol=spec.symbol,
            op=spec.op,
            trigger_value=spec.trigger,
            qty=spec.qty,
            hook_symbol=spec.hook_symbol,
            core_order_id=spec.core_order_id,
            tf_minutes=spec.tf_minutes,
            next_eval_at=spec.next_eval_at,
            last_eval_at=spec.last_eval_at,
            status=spec.status,
        )
        self._storage.append_event("simple_created", spec.order_id, {"side": side, "symbol": symbol, "tf": tf_minutes})

        if side == "sell":
            self._sell_orders.append(spec)
        else:
            self._buy_orders.append(spec)
        exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
        await self._send(update, f"Ordine {side} inserito: order_id={spec.order_id} watch={spec.symbol} exec={exec_symbol}")

    async def _cmd_f(self, update: Update, parts: List[str]):
        parts, tf_minutes = self._extract_tf(parts)
        if len(parts) < 6:
            raise ValueError("Formato: /f SYMBOL <|> TRIGGER QTY PERCENT [@PAIRHOOK]")

        symbol = parts[1].upper()
        op = parts[2]
        trigger_val = float(parts[3])
        qty = float(parts[4])
        percent = float(parts[5])
        hook = parts[6][1:].upper() if len(parts) >= 7 and parts[6].startswith("@") else None
        if op not in {"<", ">"}:
            raise ValueError("Operatore non valido: usa < oppure >")

        chat_id = update.effective_chat.id
        order_id = self._new_order_id()
        spec = FunctionSpec(
            order_id,
            symbol,
            op,
            trigger_val,
            qty,
            percent,
            chat_id,
            hook,
            False,
            None,
            tf_minutes,
            self._next_boundary_epoch(tf_minutes),
            None,
        )
        self._function_orders.append(spec)
        self._poller.add_symbol(symbol)
        if hook:
            self._poller.add_symbol(hook)

        self._storage.save_function_order(
            order_id=order_id,
            chat_id=chat_id,
            symbol=symbol,
            op=op,
            trigger_value=trigger_val,
            qty=qty,
            percent=percent,
            hook_symbol=hook,
            bought=False,
            prev_price=None,
            tf_minutes=tf_minutes,
            next_eval_at=spec.next_eval_at,
            last_eval_at=spec.last_eval_at,
            status="active",
        )
        self._storage.append_event("function_created", order_id, {"symbol": symbol, "tf": tf_minutes})
        exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
        await self._send(update, f"Ordine function inserito: order_id={order_id} watch={spec.symbol} exec={exec_symbol}")

    async def _cmd_S(self, update: Update, parts: List[str]):
        parts, tf_minutes = self._extract_tf(parts)
        if len(parts) < 4:
            raise ValueError("Formato: /S SYMBOL PERCENT QTY [LIMIT] [@PAIRHOOK]")

        symbol = parts[1].upper()
        percent = float(parts[2])
        qty = float(parts[3])
        limit = None
        hook = None
        for token in parts[4:]:
            if token.startswith("@"):
                hook = token[1:].upper()
            else:
                limit = float(token)

        chat_id = update.effective_chat.id
        order_id = self._new_order_id()
        spec = TrailingSellSpec(
            order_id,
            symbol,
            qty,
            percent,
            chat_id,
            limit,
            hook,
            False,
            None,
            None,
            tf_minutes,
            self._next_boundary_epoch(tf_minutes),
            None,
        )
        self._init_trailing_sell(spec)
        self._trailing_sell_orders.append(spec)
        self._poller.add_symbol(symbol)
        if hook:
            self._poller.add_symbol(hook)

        self._storage.save_trailing_order(
            order_id=spec.order_id,
            chat_id=spec.chat_id,
            side="sell",
            symbol=spec.symbol,
            qty=spec.qty,
            percent=spec.percent,
            limit_price=spec.limit,
            hook_symbol=spec.hook_symbol,
            armed=spec.armed,
            max_price=spec.max_price,
            min_price=None,
            arm_op=spec.arm_op,
            tf_minutes=spec.tf_minutes,
            next_eval_at=spec.next_eval_at,
            last_eval_at=spec.last_eval_at,
            status=spec.status,
        )
        self._storage.append_event("trailing_sell_created", order_id, {"symbol": symbol, "tf": tf_minutes})
        exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
        await self._send(update, f"Trailing sell inserito: order_id={order_id} watch={spec.symbol} exec={exec_symbol}")

    async def _cmd_B(self, update: Update, parts: List[str]):
        parts, tf_minutes = self._extract_tf(parts)
        if len(parts) < 5:
            raise ValueError("Formato: /B SYMBOL PERCENT QTY LIMIT")

        symbol = parts[1].upper()
        percent = float(parts[2])
        qty = float(parts[3])
        limit = float(parts[4])

        chat_id = update.effective_chat.id
        order_id = self._new_order_id()
        spec = TrailingBuySpec(
            order_id,
            symbol,
            qty,
            percent,
            chat_id,
            limit,
            False,
            None,
            None,
            tf_minutes,
            self._next_boundary_epoch(tf_minutes),
            None,
        )
        self._init_trailing_buy(spec)
        self._trailing_buy_orders.append(spec)
        self._poller.add_symbol(symbol)

        self._storage.save_trailing_order(
            order_id=spec.order_id,
            chat_id=spec.chat_id,
            side="buy",
            symbol=spec.symbol,
            qty=spec.qty,
            percent=spec.percent,
            limit_price=spec.limit,
            hook_symbol=None,
            armed=spec.armed,
            max_price=None,
            min_price=spec.min_price,
            arm_op=spec.arm_op,
            tf_minutes=spec.tf_minutes,
            next_eval_at=spec.next_eval_at,
            last_eval_at=spec.last_eval_at,
            status=spec.status,
        )
        self._storage.append_event("trailing_buy_created", order_id, {"symbol": symbol, "tf": tf_minutes})
        await self._send(update, f"Trailing buy inserito: order_id={order_id}")

    async def _cmd_t(self, update: Update, parts: List[str]):
        if len(parts) < 2:
            raise ValueError("Formato: /t MINUTI")
        tf_min = int(parts[1])
        if tf_min not in VALID_TF_MINUTES:
            raise ValueError("Timeframe valido: 1,5,15,30,60,120,240,1440")
        self._default_tf_minutes = tf_min
        self._timeframe_seconds = tf_min * 60
        self._storage.set_setting("default_tf_minutes", str(self._default_tf_minutes))
        self._storage.set_setting("timeframe_seconds", str(self._timeframe_seconds))
        self._storage.append_event(
            "setting_updated",
            payload={"default_tf_minutes": self._default_tf_minutes, "timeframe_seconds": self._timeframe_seconds},
        )
        await self._send(update, f"Default timeframe nuovi ordini impostato a {tf_min} minuti")

    async def _cmd_a(self, update: Update, parts: List[str]):
        if len(parts) < 2:
            raise ValueError("Formato: /a 0|1 [PERCENT]")
        enabled = bool(int(parts[1]))
        self._alert_enabled = enabled
        if enabled:
            if len(parts) < 3:
                raise ValueError("Se abiliti alert devi passare PERCENT")
            self._alert_percent = float(parts[2])
            self._alert_reference_price = self._feed.get_price("BTCUSDT")
            self._poller.add_symbol("BTCUSDT")
        else:
            self._alert_reference_price = None

        self._storage.set_setting("alert_enabled", "1" if self._alert_enabled else "0")
        self._storage.set_setting("alert_percent", str(self._alert_percent))
        self._storage.append_event(
            "setting_updated",
            payload={"alert_enabled": self._alert_enabled, "alert_percent": self._alert_percent},
        )
        await self._send(update, f"Alert impostato: enabled={self._alert_enabled}, percent={self._alert_percent}")

    async def _cmd_e(self, update: Update, parts: List[str]):
        if len(parts) < 2:
            raise ValueError("Formato: /e 0|1")
        self._echo_enabled = bool(int(parts[1]))
        self._storage.set_setting("echo_enabled", "1" if self._echo_enabled else "0")
        self._storage.append_event("setting_updated", payload={"echo_enabled": self._echo_enabled})
        await self._send(update, f"Echo impostato a {self._echo_enabled}")

    async def _cmd_o(self, update: Update):
        lines = ["Ordini registrati (order_id):"]
        lines.append("SELL:")
        for s in self._sell_orders:
            lines.append(f"{s.order_id} watch={s.symbol} exec={self._exec_symbol(s.symbol, s.hook_symbol)} {s.op} {s.trigger} qty={s.qty} tf={s.tf_minutes}m next={s.next_eval_at} status={s.status}")
        lines.append("BUY:")
        for b in self._buy_orders:
            lines.append(f"{b.order_id} watch={b.symbol} exec={self._exec_symbol(b.symbol, b.hook_symbol)} {b.op} {b.trigger} qty={b.qty} tf={b.tf_minutes}m next={b.next_eval_at} status={b.status}")
        lines.append("FUNCTION:")
        for f in self._function_orders:
            lines.append(f"{f.order_id} watch={f.symbol} exec={self._exec_symbol(f.symbol, f.hook_symbol)} {f.op} {f.trigger} qty={f.qty} pct={f.percent} tf={f.tf_minutes}m next={f.next_eval_at} status={f.status}")
        lines.append("TRAILING SELL:")
        for t in self._trailing_sell_orders:
            lines.append(f"{t.order_id} watch={t.symbol} exec={self._exec_symbol(t.symbol, t.hook_symbol)} pct={t.percent} qty={t.qty} limit={t.limit} tf={t.tf_minutes}m next={t.next_eval_at} status={t.status}")
        lines.append("TRAILING BUY:")
        for t in self._trailing_buy_orders:
            lines.append(f"{t.order_id} {t.symbol} pct={t.percent} qty={t.qty} limit={t.limit} tf={t.tf_minutes}m next={t.next_eval_at} status={t.status}")
        lines.append(f"Timeframe={self._timeframe_seconds}s echo={self._echo_enabled} alert={self._alert_enabled}")
        await self._send(update, "\n".join(lines))

    async def _cmd_c(self, update: Update, parts: List[str]):
        if len(parts) < 2:
            raise ValueError("Formato: /c ORDER_ID oppure /c a")

        target = parts[1]
        if target == "a":
            ids = [s.order_id for s in self._sell_orders + self._buy_orders]
            ids += [s.order_id for s in self._function_orders + self._trailing_sell_orders + self._trailing_buy_orders]
            for oid in ids:
                self._cancel_order_by_id(oid)
            await self._send(update, "Tutti gli ordini cancellati")
            return

        order_id = int(target)
        self._cancel_order_by_id(order_id)
        await self._send(update, f"Ordine cancellato: order_id={order_id}")

    def _cancel_order_by_id(self, order_id: int):
        for collection in (self._sell_orders, self._buy_orders):
            for spec in collection:
                if spec.order_id == order_id and spec.status == "active":
                    spec.status = "cancelled"
                    if spec.core_order_id is not None:
                        self._manager.cancel_order(spec.core_order_id)
                    self._storage.update_order_status(order_id, "cancelled")
                    self._storage.append_event("order_cancelled", order_id)
                    return

        for collection in (self._function_orders, self._trailing_sell_orders, self._trailing_buy_orders):
            for spec in collection:
                if spec.order_id == order_id and spec.status == "active":
                    spec.status = "cancelled"
                    self._storage.update_order_status(order_id, "cancelled")
                    self._storage.append_event("order_cancelled", order_id)
                    return

        raise ValueError("order_id non trovato")

    def _init_trailing_sell(self, spec: TrailingSellSpec):
        price = self._feed.get_price(spec.symbol)
        spec.max_price = price
        if spec.limit is None:
            spec.armed = True
            spec.arm_op = None
        else:
            spec.arm_op = "<" if price >= spec.limit else ">"

    def _init_trailing_buy(self, spec: TrailingBuySpec):
        price = self._feed.get_price(spec.symbol)
        spec.min_price = price
        spec.arm_op = "<" if price >= spec.limit else ">"

    @staticmethod
    def _is_due(spec, now_ts: int) -> bool:
        if getattr(spec, "next_eval_at", None) is None:
            return False
        return now_ts >= int(spec.next_eval_at)

    def _mark_evaluated(self, spec, now_ts: int):
        spec.last_eval_at = now_ts
        spec.next_eval_at = self._next_boundary_epoch(spec.tf_minutes, now_ts)
        self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, spec.last_eval_at)

    def _eval_function_orders(self, now_ts: int):
        for spec in list(self._function_orders):
            if spec.status != "active":
                continue
            if not self._is_due(spec, now_ts):
                continue

            price = self._feed.get_price(spec.symbol)
            self._mark_evaluated(spec, now_ts)
            if spec.prev_price is None:
                spec.prev_price = price
                self._storage.update_function_runtime(spec.order_id, spec.bought, spec.prev_price)
                continue

            trigger_hit = (spec.op == "<" and spec.prev_price > spec.trigger and price < spec.trigger)
            trigger_hit = trigger_hit or (spec.op == ">" and spec.prev_price < spec.trigger and price > spec.trigger)

            if trigger_hit and not spec.bought:
                spec.bought = True
                spec.status = "filled"
                self._storage.update_function_runtime(spec.order_id, spec.bought, price)
                self._storage.update_order_status(spec.order_id, "filled")
                self._storage.append_event("function_filled", spec.order_id, {"price": price})
                exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
                self._queue_message(spec.chat_id, f"Function BUY scattato su watch={spec.symbol} exec={exec_symbol} a {price}")

                trailing_order_id = self._new_order_id()
                sell_spec = TrailingSellSpec(
                    order_id=trailing_order_id,
                    symbol=spec.symbol,
                    qty=spec.qty,
                    percent=spec.percent,
                    chat_id=spec.chat_id,
                    limit=None,
                    hook_symbol=spec.hook_symbol,
                    tf_minutes=spec.tf_minutes,
                    next_eval_at=self._next_boundary_epoch(spec.tf_minutes),
                )
                self._init_trailing_sell(sell_spec)
                self._trailing_sell_orders.append(sell_spec)
                self._storage.save_trailing_order(
                    order_id=sell_spec.order_id,
                    chat_id=sell_spec.chat_id,
                    side="sell",
                    symbol=sell_spec.symbol,
                    qty=sell_spec.qty,
                    percent=sell_spec.percent,
                    limit_price=sell_spec.limit,
                    hook_symbol=sell_spec.hook_symbol,
                    armed=sell_spec.armed,
                    max_price=sell_spec.max_price,
                    min_price=None,
                    arm_op=sell_spec.arm_op,
                    tf_minutes=sell_spec.tf_minutes,
                    next_eval_at=sell_spec.next_eval_at,
                    last_eval_at=sell_spec.last_eval_at,
                    status=sell_spec.status,
                )
                self._storage.append_event("trailing_sell_created_from_function", sell_spec.order_id)

            spec.prev_price = price
            self._storage.update_function_runtime(spec.order_id, spec.bought, spec.prev_price)

    def _eval_trailing_sell(self, now_ts: int):
        to_close: List[TrailingSellSpec] = []
        for spec in self._trailing_sell_orders:
            if spec.status != "active":
                continue
            if not self._is_due(spec, now_ts):
                continue
            price = self._feed.get_price(spec.symbol)
            self._mark_evaluated(spec, now_ts)

            if not spec.armed and spec.limit is not None:
                if (spec.arm_op == "<" and price < spec.limit) or (spec.arm_op == ">" and price > spec.limit):
                    spec.armed = True
                    spec.max_price = price
            else:
                if spec.max_price is None or price > spec.max_price:
                    spec.max_price = price
                trigger_price = spec.max_price * (1.0 - (spec.percent / 100.0))
                if price < trigger_price:
                    spec.status = "filled"
                    to_close.append(spec)
                    exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
                    self._queue_message(spec.chat_id, f"Trailing SELL eseguito su watch={spec.symbol} exec={exec_symbol} qty={spec.qty} a {price}")
                    self._storage.update_order_status(spec.order_id, "filled")
                    self._storage.append_event("trailing_sell_filled", spec.order_id, {"price": price})

            self._storage.update_trailing_runtime(spec.order_id, spec.armed, spec.max_price, None, spec.arm_op)

        for spec in to_close:
            self._trailing_sell_orders.remove(spec)

    def _eval_trailing_buy(self, now_ts: int):
        to_close: List[TrailingBuySpec] = []
        for spec in self._trailing_buy_orders:
            if spec.status != "active":
                continue
            if not self._is_due(spec, now_ts):
                continue
            price = self._feed.get_price(spec.symbol)
            self._mark_evaluated(spec, now_ts)

            if not spec.armed:
                if (spec.arm_op == "<" and price < spec.limit) or (spec.arm_op == ">" and price > spec.limit):
                    spec.armed = True
                    spec.min_price = price
            else:
                if spec.min_price is None or price < spec.min_price:
                    spec.min_price = price
                trigger_price = spec.min_price * (1.0 + (spec.percent / 100.0))
                if price > trigger_price:
                    spec.status = "filled"
                    to_close.append(spec)
                    self._queue_message(spec.chat_id, f"Trailing BUY eseguito su {spec.symbol} qty={spec.qty} a {price}")
                    self._storage.update_order_status(spec.order_id, "filled")
                    self._storage.append_event("trailing_buy_filled", spec.order_id, {"price": price})

            self._storage.update_trailing_runtime(spec.order_id, spec.armed, None, spec.min_price, spec.arm_op)

        for spec in to_close:
            self._trailing_buy_orders.remove(spec)

    def _eval_alert(self, chat_id: Optional[int], now: float):
        if not self._alert_enabled or now - self._last_alert_tick < 60:
            return
        self._last_alert_tick = now
        price = self._feed.get_price("BTCUSDT")
        if self._alert_reference_price is None:
            self._alert_reference_price = price
            return

        variation = ((price - self._alert_reference_price) / self._alert_reference_price) * 100.0
        if abs(variation) > abs(self._alert_percent) and chat_id is not None:
            self._queue_message(chat_id, f"ALERT BTCUSDT: variazione {variation:.4f}%")
        self._alert_reference_price = price

    def _tracked_symbols(self) -> List[str]:
        symbols = {"BTCUSDT"}
        symbols.update(s.symbol for s in self._sell_orders if s.status == "active")
        symbols.update(s.symbol for s in self._buy_orders if s.status == "active")
        symbols.update(s.symbol for s in self._function_orders if s.status == "active")
        symbols.update(s.symbol for s in self._trailing_sell_orders if s.status == "active")
        symbols.update(s.symbol for s in self._trailing_buy_orders if s.status == "active")
        return sorted(symbols)

    def _eval_echo(self, chat_id: Optional[int], now: float):
        if not self._echo_enabled or now - self._last_timeframe_tick < self._timeframe_seconds:
            return
        self._last_timeframe_tick = now
        if chat_id is None:
            return

        lines = []
        for symbol in self._tracked_symbols():
            try:
                lines.append(f"{symbol}: {self._feed.get_price(symbol)}")
            except Exception as exc:
                lines.append(f"{symbol}: errore {exc}")
        self._queue_message(chat_id, "Echo prezzi:\n" + "\n".join(lines))

    def _sync_simple_order_schedule(self):
        for spec in self._sell_orders + self._buy_orders:
            if spec.status != "active" or spec.core_order_id is None:
                continue
            core_order = self._manager.get_order(spec.core_order_id)
            if core_order is None:
                continue
            next_eval = int(core_order.next_eval_at) if core_order.next_eval_at is not None else None
            last_eval = int(core_order.last_eval_at) if core_order.last_eval_at is not None else None
            spec.next_eval_at = next_eval
            spec.last_eval_at = last_eval
            self._storage.update_order_schedule(spec.order_id, next_eval, last_eval)

    async def _job_tick(self, context: ContextTypes.DEFAULT_TYPE):
        now = time.time()
        now_i = int(now)
        chat_id = self._authorized_chat_id or context.application.bot_data.get("last_chat_id")

        try:
            self._eval_function_orders(now_i)
            self._eval_trailing_sell(now_i)
            self._eval_trailing_buy(now_i)
            self._sync_simple_order_schedule()
            self._eval_alert(chat_id, now)
            self._eval_echo(chat_id, now)

            if now - self._last_archive_check > 3600:
                self._last_archive_check = now
                self._storage.archive_closed_orders_by_month()
        except Exception as exc:
            log.exception("Errore nel job di controllo: %s", exc)

    async def _job_flush_notifications(self, context: ContextTypes.DEFAULT_TYPE):
        while not self._notifications.empty():
            chat_id, text = self._notifications.get_nowait()
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except Exception as exc:
                log.error("Invio Telegram fallito: %s", exc)

    async def _capture_chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat:
            context.application.bot_data["last_chat_id"] = update.effective_chat.id

    def build_application(self) -> Application:
        app = ApplicationBuilder().token(self._token).build()
        app.add_handler(CommandHandler("start", self._start))
        app.add_handler(CommandHandler("info", self._info))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/"), self._on_slash_text))
        app.add_handler(MessageHandler(filters.ALL, self._capture_chat_id))

        app.job_queue.run_repeating(self._job_tick, interval=1.0, first=2.0)
        app.job_queue.run_repeating(self._job_flush_notifications, interval=1.0, first=1.0)
        self._app = app
        return app

    def run(self):
        self._poller.start()
        app = self.build_application()
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES)
        finally:
            self._storage.close()
            self._poller.stop()


def build_bot_from_env() -> TelegramTradingBot:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN non impostato")

    raw_chat_id = os.getenv("AUTHORIZED_CHAT_ID")
    chat_id = int(raw_chat_id) if raw_chat_id else None
    db_path = os.getenv("BOT_DB_PATH", "data/bot.sqlite3")
    return TelegramTradingBot(token=token, authorized_chat_id=chat_id, db_path=db_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    build_bot_from_env().run()


