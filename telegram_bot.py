"""Interfaccia Telegram con persistenza SQLite e storico eventi."""

import logging
import os
import queue
import time
import re
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from core import Action, Order, OrderBehavior, Trigger, build_engine
from indicators import TechnicalIndicators
from price_feeds import Binance1mClosePriceFeed
from storage import SQLiteStorage

log = logging.getLogger(__name__)

VALID_TF_MINUTES = {1, 5, 15, 30, 60, 120, 240, 1440}
UI_STATE_KEY = "ui_state"
UI_DRAFT_KEY = "ui_draft"
CLEAN_ENTRY_PRESETS: Dict[str, Dict[str, Any]] = {
    "conservativo": {
        "rsi_min": 55.0,
        "adx_min": 22.0,
        "required_checks": 5,
        "require_trend": True,
        "require_volume": True,
        "require_price_above_ema": True,
    },
    "bilanciato": {
        "rsi_min": 50.0,
        "adx_min": 18.0,
        "required_checks": 4,
        "require_trend": True,
        "require_volume": True,
        "require_price_above_ema": True,
    },
    "aggressivo": {
        "rsi_min": 45.0,
        "adx_min": 14.0,
        "required_checks": 3,
        "require_trend": True,
        "require_volume": False,
        "require_price_above_ema": True,
    },
}


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
    post_fill_action: Optional[Dict[str, Any]] = None
    acquistopulito: bool = False
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
    post_fill_action: Optional[Dict[str, Any]] = None
    oco_parent_order_id: Optional[int] = None
    oco_leg_index: Optional[int] = None
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
    post_fill_action: Optional[Dict[str, Any]] = None
    acquistopulito: bool = False
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
    post_fill_action: Optional[Dict[str, Any]] = None
    acquistopulito: bool = False
    status: str = "active"


@dataclass
class OcoSpec:
    order_id: int
    symbol: str
    side: str
    legs: List[Dict[str, Any]]
    chat_id: int
    parent_order_id: Optional[int] = None
    tf_minutes: int = 15
    next_eval_at: Optional[int] = None
    last_eval_at: Optional[int] = None
    acquistopulito: bool = False
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
        self._clean_entry_preset = "bilanciato"
        self._clean_entry_config = self._default_clean_entry_config()

        self._last_timeframe_tick = 0.0
        self._last_alert_tick = 0.0
        self._last_archive_check = 0.0

        self._notifications: "queue.Queue[Tuple[int, str]]" = queue.Queue()
        self._app: Optional[Application] = None
        self._exchange_client = None
        self._public_exchange_client = None
        self._binance_api_error_cls = Exception
        self._binance_request_error_cls = Exception
        self._binance_order_error_cls = Exception
        self._symbol_validation_cache: Dict[str, Tuple[float, bool, str]] = {}
        self._symbol_validation_ttl_seconds = int(os.getenv("SYMBOL_VALIDATION_CACHE_TTL_SEC", "600"))
        self._symbol_validation_soft_fail = os.getenv("SYMBOL_VALIDATION_SOFT_FAIL", "0") == "1"
        self._init_exchange_client()

        self._load_settings()
        self._restore_active_orders()

    def _init_exchange_client(self):
        """Initialize Binance spot client for real order execution."""
        try:
            from binance.client import Client
            from binance.exceptions import BinanceAPIException, BinanceOrderException, BinanceRequestException
        except Exception as exc:
            log.warning("Client Binance non disponibile per esecuzione ordini: %s", exc)
            return

        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        if not api_key or not api_secret:
            log.warning("BINANCE_API_KEY/BINANCE_SECRET_KEY non impostate: esecuzione ordini disabilitata")
            try:
                self._public_exchange_client = Client()
            except TypeError:
                self._public_exchange_client = Client(None, None)
            except Exception as exc:
                log.warning("Client Binance pubblico non disponibile per validazione simboli: %s", exc)
            return

        self._exchange_client = Client(api_key, api_secret)
        self._public_exchange_client = self._exchange_client
        self._binance_api_error_cls = BinanceAPIException
        self._binance_request_error_cls = BinanceRequestException
        self._binance_order_error_cls = BinanceOrderException

    def _validate_spot_symbol(self, symbol: str, field_name: str = "SYMBOL") -> Tuple[bool, str]:
        normalized = (symbol or "").strip().upper()
        if not normalized:
            return False, f"{field_name} vuoto: inserisci una coppia valida (es. BTCUSDT)"

        now = time.time()
        cached = self._symbol_validation_cache.get(normalized)
        if cached and cached[0] > now:
            return cached[1], cached[2]

        client = self._exchange_client or self._public_exchange_client
        if client is None:
            message = "Validazione simbolo Binance non disponibile al momento"
            self._storage.append_event("symbol_validation_skipped_unavailable", payload={"symbol": normalized, "field": field_name})
            if self._symbol_validation_soft_fail:
                return True, ""
            return False, f"{message}. Riprova tra poco."

        try:
            info = client.get_symbol_info(normalized)
        except (self._binance_api_error_cls, self._binance_request_error_cls, self._binance_order_error_cls) as exc:
            self._storage.append_event(
                "symbol_validation_failed",
                payload={"symbol": normalized, "field": field_name, "error": str(exc), "error_type": type(exc).__name__},
            )
            if self._symbol_validation_soft_fail:
                return True, ""
            return False, "Validazione simbolo Binance non disponibile al momento. Riprova tra poco."
        except Exception as exc:
            self._storage.append_event(
                "symbol_validation_failed",
                payload={"symbol": normalized, "field": field_name, "error": str(exc), "error_type": type(exc).__name__},
            )
            if self._symbol_validation_soft_fail:
                return True, ""
            return False, "Errore durante validazione simbolo Binance. Riprova tra poco."

        if not info:
            message = f"{field_name} '{normalized}' non esiste su Binance Spot. Inserisci una coppia valida (es. BTCUSDT)."
            self._symbol_validation_cache[normalized] = (now + self._symbol_validation_ttl_seconds, False, message)
            self._storage.append_event("symbol_validation_failed", payload={"symbol": normalized, "field": field_name, "reason": "not_found"})
            return False, message

        status = str(info.get("status") or "UNKNOWN").upper()
        if status != "TRADING":
            message = f"{field_name} '{normalized}' presente ma non tradabile ora (status={status})."
            self._symbol_validation_cache[normalized] = (now + self._symbol_validation_ttl_seconds, False, message)
            self._storage.append_event(
                "symbol_validation_failed", payload={"symbol": normalized, "field": field_name, "reason": "not_trading", "status": status}
            )
            return False, message

        self._symbol_validation_cache[normalized] = (now + self._symbol_validation_ttl_seconds, True, "")
        self._storage.append_event("symbol_validation_ok", payload={"symbol": normalized, "field": field_name})
        return True, ""

    def _execute_simple_order_on_exchange(self, spec: SimpleOrderSpec) -> Dict[str, Any]:
        """Submit a MARKET order to Binance Spot and return raw API response."""
        if self._exchange_client is None:
            raise RuntimeError("Client Binance non inizializzato (chiavi mancanti o libreria non disponibile)")

        from binance.client import Client

        symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
        side = Client.SIDE_SELL if spec.side == "sell" else Client.SIDE_BUY
        return self._exchange_client.create_order(
            symbol=symbol,
            side=side,
            type=Client.ORDER_TYPE_MARKET,
            quantity=spec.qty,
            recvWindow=5000,
        )

    def _execute_market_order_on_exchange(self, side: str, symbol: str, qty: float) -> Dict[str, Any]:
        """Submit a MARKET order to Binance Spot and return raw API response."""
        if self._exchange_client is None:
            raise RuntimeError("Client Binance non inizializzato (chiavi mancanti o libreria non disponibile)")

        from binance.client import Client

        exchange_side = Client.SIDE_SELL if side == "sell" else Client.SIDE_BUY
        return self._exchange_client.create_order(
            symbol=symbol,
            side=exchange_side,
            type=Client.ORDER_TYPE_MARKET,
            quantity=qty,
            recvWindow=5000,
        )

    @staticmethod
    def _exchange_fields(resp: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "exchange_order_id": resp.get("orderId"),
            "exchange_status": resp.get("status"),
            "executed_qty": resp.get("executedQty"),
        }

    def _is_binance_exc(self, exc: Exception) -> bool:
        return isinstance(exc, (self._binance_api_error_cls, self._binance_request_error_cls, self._binance_order_error_cls))

    def _handle_exchange_error(
        self,
        order_id: int,
        chat_id: int,
        event_type: str,
        user_msg_prefix: str,
        payload: Dict[str, Any],
        exc: Exception,
    ):
        self._storage.update_order_status(order_id, "error")
        self._storage.append_event(
            event_type,
            order_id,
            {**payload, "error": str(exc), "error_type": type(exc).__name__},
        )
        msg_kind = "Errore esecuzione" if self._is_binance_exc(exc) else "Errore interno esecuzione"
        self._queue_message(chat_id, f"{msg_kind} {user_msg_prefix}: {exc}")
        if self._is_binance_exc(exc):
            log.error("Errore Binance su ordine %s: %s", order_id, exc)
        else:
            log.exception("Errore inatteso su ordine %s", order_id)

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

        preset = (self._storage.get_setting("clean_entry_preset") or "").strip().lower()
        if preset in CLEAN_ENTRY_PRESETS:
            self._clean_entry_preset = preset
            loaded_cfg = dict(CLEAN_ENTRY_PRESETS[preset])
        else:
            self._clean_entry_preset = "manuale" if preset else "bilanciato"
            loaded_cfg = self._default_clean_entry_config()

        setting_map = {
            "clean_entry_rsi_min": "rsi_min",
            "clean_entry_adx_min": "adx_min",
            "clean_entry_required_checks": "required_checks",
            "clean_entry_require_trend": "require_trend",
            "clean_entry_require_volume": "require_volume",
            "clean_entry_require_price_above_ema": "require_price_above_ema",
        }
        for setting_key, cfg_key in setting_map.items():
            raw_value = self._storage.get_setting(setting_key)
            if raw_value is None:
                continue
            loaded_cfg[cfg_key] = raw_value
        self._clean_entry_config = self._normalize_clean_entry_config(loaded_cfg)

    @staticmethod
    def _default_clean_entry_config() -> Dict[str, Any]:
        return dict(CLEAN_ENTRY_PRESETS["bilanciato"])

    @staticmethod
    def _parse_bool_like(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        raw = str(value).strip().lower()
        if raw in {"1", "true", "t", "yes", "y", "si", "s", "on", "abilita"}:
            return True
        if raw in {"0", "false", "f", "no", "n", "off", "disabilita"}:
            return False
        raise ValueError(f"Valore booleano non valido: {value}")

    def _normalize_clean_entry_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._default_clean_entry_config()
        merged.update(cfg or {})

        rsi_min = float(merged.get("rsi_min", 50.0))
        adx_min = float(merged.get("adx_min", 18.0))
        required_checks = int(float(merged.get("required_checks", 4)))
        require_trend = self._parse_bool_like(merged.get("require_trend", True))
        require_volume = self._parse_bool_like(merged.get("require_volume", True))
        require_price_above_ema = self._parse_bool_like(merged.get("require_price_above_ema", True))

        enabled_checks = 2 + int(require_trend) + int(require_volume) + int(require_price_above_ema)
        required_checks = max(1, min(required_checks, enabled_checks))

        return {
            "rsi_min": rsi_min,
            "adx_min": adx_min,
            "required_checks": required_checks,
            "require_trend": require_trend,
            "require_volume": require_volume,
            "require_price_above_ema": require_price_above_ema,
        }

    def _clean_entry_summary(self, cfg: Optional[Dict[str, Any]] = None) -> str:
        current = self._normalize_clean_entry_config(cfg or self._clean_entry_config)
        return (
            f"setPulito preset={self._clean_entry_preset} | "
            f"RSI>={current['rsi_min']:.1f} ADX>={current['adx_min']:.1f} checks>={current['required_checks']} | "
            f"trend={int(current['require_trend'])} volume={int(current['require_volume'])} "
            f"price>=EMA={int(current['require_price_above_ema'])}"
        )

    def _persist_clean_entry_settings(self):
        cfg = self._normalize_clean_entry_config(self._clean_entry_config)
        self._storage.set_setting("clean_entry_preset", self._clean_entry_preset)
        self._storage.set_setting("clean_entry_rsi_min", str(cfg["rsi_min"]))
        self._storage.set_setting("clean_entry_adx_min", str(cfg["adx_min"]))
        self._storage.set_setting("clean_entry_required_checks", str(cfg["required_checks"]))
        self._storage.set_setting("clean_entry_require_trend", "1" if cfg["require_trend"] else "0")
        self._storage.set_setting("clean_entry_require_volume", "1" if cfg["require_volume"] else "0")
        self._storage.set_setting("clean_entry_require_price_above_ema", "1" if cfg["require_price_above_ema"] else "0")
        self._storage.append_event(
            "setting_updated",
            payload={
                "clean_entry_preset": self._clean_entry_preset,
                "clean_entry_config": cfg,
            },
        )

    def _apply_clean_entry_preset(self, preset: str):
        key = preset.strip().lower()
        if key not in CLEAN_ENTRY_PRESETS:
            raise ValueError("Preset valido: conservativo, bilanciato, aggressivo")
        self._clean_entry_preset = key
        self._clean_entry_config = self._normalize_clean_entry_config(dict(CLEAN_ENTRY_PRESETS[key]))

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
                post_fill_action=self._decode_post_fill_action(row.get("post_fill_action")),
                acquistopulito=bool(row.get("acquistopulito", 0)),
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
                    post_fill_action=self._decode_post_fill_action(row.get("post_fill_action")),
                    acquistopulito=bool(row.get("acquistopulito", 0)),
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
                        post_fill_action=self._decode_post_fill_action(row.get("post_fill_action")),
                        oco_parent_order_id=row.get("oco_parent_order_id"),
                        oco_leg_index=row.get("oco_leg_index"),
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
                        post_fill_action=self._decode_post_fill_action(row.get("post_fill_action")),
                        acquistopulito=bool(row.get("acquistopulito", 0)),
                        status=row["status"],
                    )
                self._trailing_buy_orders.append(spec)
                self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, None)

        # restore OCO orders
        self._oco_orders: List[OcoSpec] = []
        for row in data.get("oco", []):
            spec = OcoSpec(
                order_id=row["order_id"],
                symbol=row["symbol"],
                side=row["side"],
                legs=row.get("legs", []),
                chat_id=row["chat_id"],
                parent_order_id=row.get("parent_order_id"),
                tf_minutes=row.get("tf_minutes", 15),
                next_eval_at=self._next_boundary_epoch(row.get("tf_minutes", 15)),
                last_eval_at=None,
                acquistopulito=bool(row.get("acquistopulito", 0)),
                status=row["status"],
            )
            self._oco_orders.append(spec)
            self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, None)
            # attach to engine
            self._attach_oco_to_engine(spec)

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

    @staticmethod
    def _extract_acquistopulito(parts: List[str]) -> Tuple[List[str], bool]:
        """Extract optional clean-entry flag from command tokens.

        Supported tokens:
        - acquistopulito
        - acquistopulito=true|false|1|0|si|no
        """
        filtered: List[str] = []
        value: Optional[bool] = None
        for token in parts:
            lower = token.lower()
            if lower == "acquistopulito":
                if value is not None:
                    raise ValueError("Flag acquistopulito duplicato")
                value = True
                continue
            if lower.startswith("acquistopulito="):
                if value is not None:
                    raise ValueError("Flag acquistopulito duplicato")
                raw = lower.split("=", 1)[1].strip()
                if raw in {"1", "true", "si", "yes", "on"}:
                    value = True
                elif raw in {"0", "false", "no", "off"}:
                    value = False
                else:
                    raise ValueError("Valore acquistopulito non valido: usa true/false")
                continue
            filtered.append(token)
        return filtered, bool(value)

    @staticmethod
    def _decode_post_fill_action(raw: Optional[str]) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            decoded = json.loads(raw)
            return decoded if isinstance(decoded, dict) else None
        except Exception:
            return None

    @staticmethod
    def _parse_action_mode(raw_value: str, allow_trailing: bool) -> Dict[str, Any]:
        value = raw_value.strip().lower()
        if allow_trailing and value.startswith("trail:"):
            trail_v = value.split(":", 1)[1].strip().rstrip("%")
            parsed = float(trail_v)
            if parsed <= 0:
                raise ValueError("Valore trailing deve essere > 0")
            return {"mode": "trailing", "value": parsed}
        if value.endswith("%"):
            parsed = float(value[:-1])
            if parsed <= 0:
                raise ValueError("Valore percentuale deve essere > 0")
            return {"mode": "percent", "value": parsed}
        parsed = float(value)
        if parsed <= 0:
            raise ValueError("Valore fisso deve essere > 0")
        return {"mode": "fixed", "value": parsed}

    def _parse_post_fill_oco_spec(self, token: str) -> Dict[str, Any]:
        payload = token[4:].strip()
        if not payload:
            raise ValueError("Spec OCO vuota. Usa oco:tp=...,sl=...")
        fields: Dict[str, str] = {}
        for chunk in payload.split(","):
            piece = chunk.strip()
            if not piece:
                continue
            if "=" not in piece:
                raise ValueError(f"Campo OCO non valido: {piece}")
            k, v = piece.split("=", 1)
            fields[k.strip().lower()] = v.strip()
        if "tp" not in fields or "sl" not in fields:
            raise ValueError("Spec OCO richiede tp=... e sl=...")
        return {
            "type": "oco",
            "tp": self._parse_action_mode(fields["tp"], allow_trailing=True),
            "sl": self._parse_action_mode(fields["sl"], allow_trailing=True),
        }

    def _extract_post_fill_action(self, parts: List[str]) -> Tuple[List[str], Optional[Dict[str, Any]]]:
        filtered: List[str] = []
        spec: Optional[Dict[str, Any]] = None
        for token in parts:
            if token.lower().startswith("oco:"):
                if spec is not None:
                    raise ValueError("Spec OCO duplicata nel comando")
                spec = self._parse_post_fill_oco_spec(token)
                continue
            filtered.append(token)
        return filtered, spec

    @staticmethod
    def _mode_to_user_token(mode: str, value: Any) -> str:
        if mode == "trailing":
            return f"trail:{value}%"
        if mode == "percent":
            return f"{value}%"
        return str(value)

    def _post_fill_action_to_token(self, spec: Dict[str, Any]) -> str:
        if spec.get("type") != "oco":
            raise ValueError("post_fill_action non supportata")
        tp = spec.get("tp") or {}
        sl = spec.get("sl") or {}
        tp_token = self._mode_to_user_token(str(tp.get("mode")), tp.get("value"))
        sl_token = self._mode_to_user_token(str(sl.get("mode")), sl.get("value"))
        return f"oco:tp={tp_token},sl={sl_token}"

    def _build_post_fill_action_from_guided(self, tp_text: str, sl_text: str) -> Dict[str, Any]:
        return {
            "type": "oco",
            "tp": self._parse_action_mode(tp_text, allow_trailing=True),
            "sl": self._parse_action_mode(sl_text, allow_trailing=True),
        }

    def _new_order_id(self) -> int:
        return self._storage.next_order_id()

    def _is_authorized(self, update: Update) -> bool:
        # Compatibility mode for tests/manual instantiation: if no chat id is configured,
        # allow access. Production startup enforces AUTHORIZED_CHAT_ID via build_bot_from_env.
        if self._authorized_chat_id is None:
            return True
        return bool(update.effective_chat and update.effective_chat.id == self._authorized_chat_id)

    async def _send(self, update: Update, text: str, reply_markup: Optional[ReplyKeyboardMarkup] = None):
        if update.effective_chat:
            await update.effective_chat.send_message(text, reply_markup=reply_markup)

    @staticmethod
    def _main_menu_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("🆕 Nuovo ordine"), KeyboardButton("📋 Ordini attivi")],
            [KeyboardButton("⚙️ Impostazioni"), KeyboardButton("ℹ️ Info")],
            [KeyboardButton("💰 Account")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _orders_menu_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("📉 Sell semplice"), KeyboardButton("📈 Buy semplice")],
            [KeyboardButton("⚙️ Function"), KeyboardButton("📉 Trailing Sell")],
            [KeyboardButton("📈 Trailing Buy")],
            [KeyboardButton("🔗 OCO Order")],
            [KeyboardButton("← Indietro")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _settings_menu_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("⏱️ Timeframe"), KeyboardButton("🚨 Alert")],
            [KeyboardButton("🔊 Echo"), KeyboardButton("🧽 setPulito")],
            [KeyboardButton("🗑️ Cancella ordine")],
            [KeyboardButton("← Indietro")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _set_pulito_mode_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("🛠️ Manuale"), KeyboardButton("⚡ Automatico")],
            [KeyboardButton("📊 Stato")],
            [KeyboardButton("Annulla")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _set_pulito_preset_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("Conservativo"), KeyboardButton("Bilanciato")],
            [KeyboardButton("Aggressivo")],
            [KeyboardButton("← Indietro"), KeyboardButton("Annulla")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _set_pulito_manual_fields_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("RSI minimo"), KeyboardButton("ADX minimo")],
            [KeyboardButton("Check minimi"), KeyboardButton("Trend (on/off)")],
            [KeyboardButton("Volume (on/off)"), KeyboardButton("Prezzo>=EMA (on/off)")],
            [KeyboardButton("✅ Salva"), KeyboardButton("📊 Stato")],
            [KeyboardButton("← Indietro"), KeyboardButton("Annulla")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _operator_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("<"), KeyboardButton(">")], [KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _yes_no_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("✅ Si"), KeyboardButton("❌ No")], [KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _tf_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("1"), KeyboardButton("5"), KeyboardButton("15"), KeyboardButton("30")],
            [KeyboardButton("60"), KeyboardButton("120"), KeyboardButton("240"), KeyboardButton("1440")],
            [KeyboardButton("Default"), KeyboardButton("Annulla")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _oco_type_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("limit"), KeyboardButton("stop_limit")], [KeyboardButton("market")], [KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _side_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("⬆️ buy"), KeyboardButton("⬇️ sell")], [KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _confirm_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("✅ Conferma"), KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _cancel_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _echo_alert_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("Abilita ✅"), KeyboardButton("Disabilita ❌")], [KeyboardButton("Annulla")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def _cancel_order_targets(self) -> List[Tuple[int, str]]:
        targets: List[Tuple[int, str]] = []

        for spec in self._sell_orders:
            if spec.status == "active":
                targets.append((spec.order_id, f"#{spec.order_id}:{spec.symbol}:sell"))
        for spec in self._buy_orders:
            if spec.status == "active":
                targets.append((spec.order_id, f"#{spec.order_id}:{spec.symbol}:buy"))
        for spec in self._function_orders:
            if spec.status == "active":
                targets.append((spec.order_id, f"#{spec.order_id}:{spec.symbol}:function"))
        for spec in self._trailing_sell_orders:
            if spec.status == "active":
                targets.append((spec.order_id, f"#{spec.order_id}:{spec.symbol}:ts"))
        for spec in self._trailing_buy_orders:
            if spec.status == "active":
                targets.append((spec.order_id, f"#{spec.order_id}:{spec.symbol}:tb"))
        for spec in getattr(self, "_oco_orders", []):
            if spec.status == "active":
                targets.append((spec.order_id, f"#{spec.order_id}:{spec.symbol}:oco"))

        targets.sort(key=lambda x: x[0])
        return targets

    def _cancel_order_keyboard(self, max_buttons: int = 12) -> ReplyKeyboardMarkup:
        keyboard: List[List[KeyboardButton]] = []
        labels = [label for _, label in self._cancel_order_targets()[:max_buttons]]
        for i in range(0, len(labels), 2):
            row_labels = labels[i:i + 2]
            keyboard.append([KeyboardButton(lbl) for lbl in row_labels])
        keyboard.append([KeyboardButton("Tutti ✅")])
        keyboard.append([KeyboardButton("Annulla")])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _extract_order_id_from_cancel_input(text: str) -> str:
        value = text.strip()
        if value.startswith("#") and ":" in value:
            candidate = value[1:].split(":", 1)[0].strip()
            if candidate:
                return candidate
        return value

    @staticmethod
    def _post_fill_mode_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("Percentuale %"), KeyboardButton("Valore fisso")],
            [KeyboardButton("Trailing %")],
            [KeyboardButton("Annulla")],
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def _parse_post_fill_mode_choice(normalized: str) -> Optional[str]:
        if "percent" in normalized:
            return "percent"
        if "fisso" in normalized:
            return "fixed"
        if "trailing" in normalized:
            return "trailing"
        return None

    @staticmethod
    def _format_post_fill_value(mode: str, raw_text: str) -> str:
        cleaned = raw_text.strip().replace("%", "")
        value = float(cleaned)
        if value <= 0:
            raise ValueError("Valore deve essere > 0")
        if mode == "percent":
            return f"{value}%"
        if mode == "trailing":
            return f"trail:{value}%"
        return str(value)

    @staticmethod
    def _parse_set_pulito_preset_choice(normalized: str) -> Optional[str]:
        if "conserv" in normalized:
            return "conservativo"
        if "bilanc" in normalized:
            return "bilanciato"
        if "aggress" in normalized:
            return "aggressivo"
        return None

    @staticmethod
    def _parse_set_pulito_manual_field_choice(normalized: str) -> Optional[str]:
        if "rsi" in normalized:
            return "rsi_min"
        if "adx" in normalized:
            return "adx_min"
        if "check" in normalized:
            return "required_checks"
        if "trend" in normalized:
            return "require_trend"
        if "volume" in normalized:
            return "require_volume"
        if "prezzo" in normalized or "ema" in normalized:
            return "require_price_above_ema"
        return None

    async def _show_main_menu(self, update: Update, intro: Optional[str] = None):
        text = intro or "Menu principale: scegli un'azione."
        await self._send(update, text, reply_markup=self._main_menu_keyboard())

    async def _show_orders_menu(self, update: Update):
        await self._send(update, "Nuovo ordine: scegli il tipo.", reply_markup=self._orders_menu_keyboard())

    async def _show_settings_menu(self, update: Update):
        await self._send(update, "Impostazioni: scegli cosa configurare.", reply_markup=self._settings_menu_keyboard())

    @staticmethod
    def _set_ui_state(context: ContextTypes.DEFAULT_TYPE, state: str, draft: Optional[Dict[str, Any]] = None):
        context.user_data[UI_STATE_KEY] = state
        if draft is not None:
            context.user_data[UI_DRAFT_KEY] = draft

    @staticmethod
    def _clear_ui_state(context: ContextTypes.DEFAULT_TYPE):
        context.user_data.pop(UI_STATE_KEY, None)
        context.user_data.pop(UI_DRAFT_KEY, None)

    @staticmethod
    def _get_ui_state(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        return context.user_data.get(UI_STATE_KEY)

    @staticmethod
    def _get_draft(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        draft = context.user_data.get(UI_DRAFT_KEY)
        if not isinstance(draft, dict):
            draft = {}
            context.user_data[UI_DRAFT_KEY] = draft
        return draft
    @staticmethod
    def _normalize_menu_text(text: str) -> str:
        """Normalize menu text by stripping emojis/punctuation and normalizing whitespace."""
        cleaned = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    def _queue_message(self, chat_id: int, text: str):
        self._notifications.put((chat_id, text))

    async def _send_chunked(self, update: Update, lines: List[str], max_chars: int = 3500):
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1
            if current and current_len + line_len > max_chars:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len

        if current:
            chunks.append("\n".join(current))

        for chunk in chunks:
            await self._send(update, chunk)

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _fmt_amount(value: float) -> str:
        return f"{value:.8f}".rstrip("0").rstrip(".") or "0"

    def _estimate_asset_usdt(self, asset: str, total_qty: float) -> Optional[float]:
        normalized = (asset or "").upper()
        if total_qty <= 0:
            return 0.0
        if normalized == "USDT":
            return total_qty

        client = self._public_exchange_client or self._exchange_client
        if client is None:
            return None

        try:
            ticker = client.get_symbol_ticker(symbol=f"{normalized}USDT")
            price = self._to_float((ticker or {}).get("price"))
            if price <= 0:
                return None
            return total_qty * price
        except Exception:
            return None

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
        for token in parts[5:]:
            if token.startswith("@"):
                hook = token[1:].upper()
                break
        return symbol, op, trigger, qty, hook

    @staticmethod
    def _resolve_target_price(fill_price: float, side: str, mode: str, value: float, kind: str) -> float:
        if mode == "fixed":
            return value
        if side == "buy":
            return fill_price * (1.0 + value / 100.0) if kind == "tp" else fill_price * (1.0 - value / 100.0)
        return fill_price * (1.0 - value / 100.0) if kind == "tp" else fill_price * (1.0 + value / 100.0)

    def _create_auto_oco_from_post_fill(
        self,
        parent_order_id: int,
        chat_id: int,
        symbol: str,
        hook_symbol: Optional[str],
        side: str,
        qty: float,
        tf_minutes: int,
        fill_price: float,
        spec: Dict[str, Any],
    ):
        if side != "buy":
            raise ValueError("Auto OCO supportato solo per ordini di ingresso buy")
        if spec.get("type") != "oco":
            raise ValueError(f"Tipo post_fill_action non supportato: {spec.get('type')}")

        tp_cfg = spec.get("tp") or {}
        sl_cfg = spec.get("sl") or {}
        tp_mode = tp_cfg.get("mode")
        sl_mode = sl_cfg.get("mode")
        tp_value = float(tp_cfg.get("value"))
        sl_value = float(sl_cfg.get("value"))

        exec_symbol = self._exec_symbol(symbol, hook_symbol)

        def build_leg(kind: str, leg_index: int, mode: str, value: float) -> Dict[str, Any]:
            if mode == "trailing":
                return {
                    "leg_index": leg_index,
                    "ordertype": "trailing",
                    "trail_percent": value,
                    "qty": qty,
                    "side": "sell",
                    "status": "waiting",
                }

            target_price = self._resolve_target_price(fill_price, side, mode, value, kind)
            if side == "buy":
                is_take_profit = target_price >= fill_price
            else:
                is_take_profit = target_price <= fill_price

            if is_take_profit:
                return {
                    "leg_index": leg_index,
                    "ordertype": "limit",
                    "price": target_price,
                    "qty": qty,
                    "side": "sell",
                    "status": "waiting",
                }
            return {
                "leg_index": leg_index,
                "ordertype": "stop_limit",
                "stop_price": target_price,
                "limit_price": target_price,
                "qty": qty,
                "side": "sell",
                "status": "waiting",
            }

        legs: List[Dict[str, Any]] = [
            build_leg("tp", 1, str(tp_mode), tp_value),
            build_leg("sl", 2, str(sl_mode), sl_value),
        ]

        oco_id = self._new_order_id()
        oco_spec = OcoSpec(
            order_id=oco_id,
            symbol=exec_symbol,
            side="sell",
            legs=legs,
            chat_id=chat_id,
            parent_order_id=parent_order_id,
            tf_minutes=tf_minutes,
            next_eval_at=self._next_boundary_epoch(tf_minutes),
            acquistopulito=False,
            status="active",
        )
        self._storage.save_oco_order(
            order_id=oco_spec.order_id,
            chat_id=oco_spec.chat_id,
            symbol=oco_spec.symbol,
            side=oco_spec.side,
            legs=oco_spec.legs,
            hook_symbol=None,
            tf_minutes=oco_spec.tf_minutes,
            next_eval_at=oco_spec.next_eval_at,
            last_eval_at=oco_spec.last_eval_at,
            parent_order_id=parent_order_id,
            acquistopulito=False,
            status=oco_spec.status,
        )
        self._attach_oco_to_engine(oco_spec)
        self._oco_orders.append(oco_spec)
        self._storage.append_event(
            "auto_oco_created",
            parent_order_id,
            {
                "oco_order_id": oco_id,
                "exchange_symbol": exec_symbol,
                "fill_price": fill_price,
                "tp_mode": tp_mode,
                "tp_value": tp_value,
                "sl_mode": sl_mode,
                "sl_value": sl_value,
            },
        )
        self._queue_message(chat_id, f"Auto OCO creato da ordine {parent_order_id}: oco_id={oco_id} su {exec_symbol}")

    def _dispatch_post_fill_action(
        self,
        parent_order_id: int,
        chat_id: int,
        symbol: str,
        hook_symbol: Optional[str],
        side: str,
        qty: float,
        tf_minutes: int,
        fill_price: float,
        post_fill_action: Optional[Dict[str, Any]],
    ):
        if not post_fill_action:
            return
        try:
            self._create_auto_oco_from_post_fill(
                parent_order_id=parent_order_id,
                chat_id=chat_id,
                symbol=symbol,
                hook_symbol=hook_symbol,
                side=side,
                qty=qty,
                tf_minutes=tf_minutes,
                fill_price=fill_price,
                spec=post_fill_action,
            )
            self._storage.append_event("post_fill_action_triggered", parent_order_id, {"action": post_fill_action})
        except Exception as exc:
            self._storage.append_event(
                "post_fill_action_failed",
                parent_order_id,
                {"action": post_fill_action, "error": str(exc), "error_type": type(exc).__name__},
            )
            self._queue_message(chat_id, f"Post-fill action fallita per ordine {parent_order_id}: {exc}")

    @staticmethod
    def _tf_to_binance_interval(tf_minutes: int) -> str:
        mapping = {
            1: "1m",
            5: "5m",
            15: "15m",
            30: "30m",
            60: "1h",
            120: "2h",
            240: "4h",
            1440: "1d",
        }
        if tf_minutes not in mapping:
            raise ValueError(f"Timeframe non supportato: {tf_minutes}")
        return mapping[tf_minutes]

    def _fetch_ohlcv_for_indicators(self, symbol: str, tf_minutes: int, limit: int = 200) -> pd.DataFrame:
        client = getattr(self._feed, "_client", None)
        if client is None:
            raise RuntimeError("Feed corrente non espone client OHLCV")

        interval = self._tf_to_binance_interval(tf_minutes)
        rows = client.get_klines(symbol=symbol, interval=interval, limit=max(limit, 100))
        if not rows:
            raise RuntimeError(f"Nessuna candela disponibile per {symbol} tf={tf_minutes}")

        trimmed = rows[-limit:]
        frame = pd.DataFrame(
            {
                "timestamp": [r[0] for r in trimmed],
                "open": [r[1] for r in trimmed],
                "high": [r[2] for r in trimmed],
                "low": [r[3] for r in trimmed],
                "close": [r[4] for r in trimmed],
                "volume": [r[5] for r in trimmed],
            }
        )
        return frame

    def _evaluate_clean_entry(self, symbol: str, tf_minutes: int, price: float) -> Tuple[bool, str, Dict[str, Any]]:
        frame = self._fetch_ohlcv_for_indicators(symbol, tf_minutes)
        indicators = TechnicalIndicators.from_ohlcv(frame).compute_default_set()
        if indicators.empty:
            return False, "indicatori_vuoti", {}

        cfg = self._normalize_clean_entry_config(self._clean_entry_config)
        last_ind = indicators.iloc[-1].to_dict()
        last_close = float(frame["close"].astype(float).iloc[-1])
        checks: Dict[str, bool] = {
            "rsi_ok": (last_ind.get("rsi_14") or 0) >= float(cfg["rsi_min"]),
            "adx_ok": (last_ind.get("adx_14") or 0) >= float(cfg["adx_min"]),
        }
        if cfg["require_trend"]:
            checks["trend_ok"] = last_close >= float(last_ind.get("ema_20") or last_close)
        if cfg["require_volume"]:
            checks["volume_ok"] = float(frame["volume"].astype(float).iloc[-1]) >= float(last_ind.get("volume_ma_20") or 0)
        if cfg["require_price_above_ema"]:
            checks["price_ok"] = price >= float(last_ind.get("ema_20") or price)

        passed_checks = sum(1 for ok in checks.values() if ok)
        passed = passed_checks >= int(cfg["required_checks"])

        snapshot = {
            "close": last_close,
            "rsi_14": last_ind.get("rsi_14"),
            "adx_14": last_ind.get("adx_14"),
            "ema_20": last_ind.get("ema_20"),
            "volume_ma_20": last_ind.get("volume_ma_20"),
            "config": cfg,
            "checks": checks,
            "passed_checks": passed_checks,
        }
        return passed, "ok" if passed else "criteria_not_met", snapshot

    def _should_execute_clean_entry(
        self,
        *,
        order_id: int,
        symbol: str,
        tf_minutes: int,
        side: str,
        price: float,
        acquistopulito: bool,
        context: str,
    ) -> bool:
        if not acquistopulito or side != "buy":
            return True

        try:
            passed, reason, snapshot = self._evaluate_clean_entry(symbol=symbol, tf_minutes=tf_minutes, price=price)
            self._storage.append_event(
                "clean_entry_check",
                order_id,
                {
                    "context": context,
                    "symbol": symbol,
                    "tf_minutes": tf_minutes,
                    "price": price,
                    "passed": passed,
                    "reason": reason,
                    **snapshot,
                },
            )
            return passed
        except Exception as exc:
            self._storage.append_event(
                "clean_entry_error",
                order_id,
                {
                    "context": context,
                    "symbol": symbol,
                    "tf_minutes": tf_minutes,
                    "price": price,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            log.error("Errore clean-entry ordine %s: %s", order_id, exc)
            return False

    def _rearm_simple_order_after_clean_block(self, spec: SimpleOrderSpec):
        spec.next_eval_at = self._next_boundary_epoch(spec.tf_minutes)
        self._attach_simple_to_engine(spec)
        self._storage.update_order_schedule(spec.order_id, spec.next_eval_at, spec.last_eval_at)

    def _rearm_oco_leg_after_clean_block(self, oco_spec: OcoSpec, leg_spec: Dict[str, Any]):
        leg_index = int(leg_spec.get("leg_index"))
        core_id = int(leg_spec.get("core_order_id") or -(oco_spec.order_id * 10 + leg_index))

        side = (leg_spec.get("side") or oco_spec.side).lower()
        ordertype = leg_spec.get("ordertype")
        if ordertype == "market":
            trigger = Trigger(leg_index, lambda p: True, f"market leg {leg_index}")
        else:
            if side == "buy":
                if ordertype == "limit":
                    trigger = self._build_trigger(leg_index, "<", leg_spec.get("price"))
                else:
                    trigger = self._build_trigger(leg_index, ">", leg_spec.get("stop_price"))
            else:
                if ordertype == "limit":
                    trigger = self._build_trigger(leg_index, ">", leg_spec.get("price"))
                else:
                    trigger = self._build_trigger(leg_index, "<", leg_spec.get("stop_price"))

        action_id = self._next_action_id
        self._next_action_id += 1
        action = Action(
            id=action_id,
            description=f"OCO {oco_spec.order_id} leg{leg_index}",
            execute=lambda p, o_id=oco_spec.order_id, l_idx=leg_index, l_spec=leg_spec: self._on_oco_leg_fired(o_id, l_idx, l_spec, p),
        )
        order_obj = Order(
            id=core_id,
            symbol=oco_spec.symbol,
            triggers=[trigger],
            action=action,
            behavior=OrderBehavior.CANCEL_ON_FIRE,
            tf_minutes=oco_spec.tf_minutes,
            next_eval_at=float(self._next_boundary_epoch(oco_spec.tf_minutes)),
            last_eval_at=float(time.time()),
        )
        self._manager.add_order(order_obj)
        leg_spec["core_order_id"] = core_id
        leg_spec["status"] = "waiting"
        self._storage.update_oco_leg_core_order_id(oco_spec.order_id, leg_index, core_id)
        self._storage.update_oco_leg_status(oco_spec.order_id, leg_index, "waiting")

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

    def _attach_oco_to_engine(self, spec: OcoSpec):
        """Create core engine orders for each OCO leg and wire cancel-sibling behavior."""
        # ensure poller monitors symbol
        self._poller.add_symbol(spec.symbol)

        for leg in spec.legs:
            leg_index = int(leg.get("leg_index"))
            ordertype = leg.get("ordertype")

            if ordertype == "trailing":
                trailing_order_id = self._new_order_id()
                trail_percent = float(leg.get("trail_percent") or 0.0)
                if trail_percent <= 0:
                    raise ValueError(f"trail_percent non valido per OCO {spec.order_id} leg {leg_index}")

                trailing_spec = TrailingSellSpec(
                    order_id=trailing_order_id,
                    symbol=spec.symbol,
                    qty=float(leg.get("qty") or 0.0),
                    percent=trail_percent,
                    chat_id=spec.chat_id,
                    limit=None,
                    hook_symbol=None,
                    tf_minutes=spec.tf_minutes,
                    next_eval_at=self._next_boundary_epoch(spec.tf_minutes),
                    oco_parent_order_id=spec.order_id,
                    oco_leg_index=leg_index,
                )
                self._init_trailing_sell(trailing_spec)
                self._trailing_sell_orders.append(trailing_spec)
                self._storage.save_trailing_order(
                    order_id=trailing_spec.order_id,
                    chat_id=trailing_spec.chat_id,
                    side="sell",
                    symbol=trailing_spec.symbol,
                    qty=trailing_spec.qty,
                    percent=trailing_spec.percent,
                    limit_price=trailing_spec.limit,
                    hook_symbol=trailing_spec.hook_symbol,
                    armed=trailing_spec.armed,
                    max_price=trailing_spec.max_price,
                    min_price=None,
                    arm_op=trailing_spec.arm_op,
                    tf_minutes=trailing_spec.tf_minutes,
                    next_eval_at=trailing_spec.next_eval_at,
                    last_eval_at=trailing_spec.last_eval_at,
                    post_fill_action=None,
                    oco_parent_order_id=trailing_spec.oco_parent_order_id,
                    oco_leg_index=trailing_spec.oco_leg_index,
                    status=trailing_spec.status,
                )
                leg["core_order_id"] = trailing_order_id
                self._storage.update_oco_leg_core_order_id(spec.order_id, leg_index, trailing_order_id)
                self._storage.append_event(
                    "oco_leg_trailing_linked",
                    spec.order_id,
                    {"leg_index": leg_index, "trailing_order_id": trailing_order_id, "trail_percent": trail_percent},
                )
                continue

            # generate unique negative core id to avoid colliding with persisted order_id
            core_id = -(spec.order_id * 10 + leg_index)

            # build trigger depending on leg type and side
            side = leg.get("side", spec.side)

            if ordertype == "market":
                trigger = Trigger(leg_index, lambda p: True, f"market leg {leg_index}")
            else:
                if side == "buy":
                    if ordertype == "limit":
                        val = leg.get("price")
                        trigger = self._build_trigger(leg_index, "<", val)
                    else:  # stop_limit
                        val = leg.get("stop_price")
                        trigger = self._build_trigger(leg_index, ">", val)
                else:  # sell
                    if ordertype == "limit":
                        val = leg.get("price")
                        trigger = self._build_trigger(leg_index, ">", val)
                    else:  # stop_limit
                        val = leg.get("stop_price")
                        trigger = self._build_trigger(leg_index, "<", val)

            action_id = self._next_action_id
            self._next_action_id += 1

            def make_action(o_id, l_idx, l_spec):
                return Action(
                    id=action_id,
                    description=f"OCO {o_id} leg{l_idx}",
                    execute=lambda price, o_id=o_id, l_idx=l_idx, l_spec=l_spec: self._on_oco_leg_fired(o_id, l_idx, l_spec, price),
                )

            action = make_action(spec.order_id, leg_index, leg)

            order_obj = Order(
                id=core_id,
                symbol=spec.symbol,
                triggers=[trigger],
                action=action,
                behavior=OrderBehavior.CANCEL_ON_FIRE,
                tf_minutes=spec.tf_minutes,
                next_eval_at=float(spec.next_eval_at) if spec.next_eval_at is not None else None,
                last_eval_at=float(spec.last_eval_at) if spec.last_eval_at is not None else None,
            )

            self._manager.add_order(order_obj)
            # persist core id mapping
            self._storage.update_oco_leg_core_order_id(spec.order_id, leg_index, core_id)
            # keep in-memory leg mapping in sync with persisted core id
            leg["core_order_id"] = core_id

    def _cancel_linked_trailing_order(self, trailing_order_id: int):
        for spec in list(self._trailing_sell_orders):
            if spec.order_id == trailing_order_id and spec.status == "active":
                spec.status = "cancelled"
                self._storage.update_order_status(trailing_order_id, "cancelled")
                self._storage.append_event("order_cancelled", trailing_order_id)
                return

    def _finalize_oco_leg_filled(
        self,
        oco_spec: OcoSpec,
        leg_index: int,
        price: float,
        exchange_symbol: str,
        exchange_resp: Dict[str, Any],
    ):
        fired_leg = None
        for leg in oco_spec.legs:
            if int(leg.get("leg_index")) == int(leg_index):
                fired_leg = leg
                break

        oco_spec.status = "filled"
        for leg in oco_spec.legs:
            current_idx = int(leg.get("leg_index"))
            if current_idx == leg_index:
                leg["status"] = "filled"
                self._storage.update_oco_leg_status(oco_spec.order_id, current_idx, "filled")
                continue
            if (leg.get("status") or "waiting").lower() != "waiting":
                continue
            leg["status"] = "cancelled"
            self._storage.update_oco_leg_status(oco_spec.order_id, current_idx, "cancelled")
            linked_id = leg.get("core_order_id")
            if linked_id:
                if leg.get("ordertype") == "trailing":
                    self._cancel_linked_trailing_order(int(linked_id))
                else:
                    self._manager.cancel_order(int(linked_id))
            self._storage.append_event("oco_leg_cancelled", oco_spec.order_id, {"leg_index": current_idx})

        self._storage.update_order_status(oco_spec.order_id, "filled")
        self._storage.append_event(
            "oco_leg_filled",
            oco_spec.order_id,
            {
                "leg_index": leg_index,
                "ordertype": (fired_leg or {}).get("ordertype"),
                "price": price,
                "exchange_symbol": exchange_symbol,
                **self._exchange_fields(exchange_resp),
            },
        )

        self._queue_message(
            oco_spec.chat_id,
            f"OCO {oco_spec.order_id} leg {leg_index} eseguita su {exchange_symbol} a {price} (exchange orderId={exchange_resp.get('orderId')}); sibling cancellato",
        )

    def _on_oco_leg_fired(self, order_id: int, leg_index: int, leg_spec: Dict[str, Any], price: float):
        oco_spec = None
        for s in getattr(self, "_oco_orders", []):
            if s.order_id == order_id:
                oco_spec = s
                break
        if oco_spec is None or oco_spec.status != "active":
            return

        leg_status = (leg_spec.get("status") or "waiting").lower()
        if leg_status != "waiting":
            return

        symbol = self._exec_symbol(oco_spec.symbol, None)
        leg_side = (leg_spec.get("side") or oco_spec.side).lower()
        qty = float(leg_spec.get("qty") or 0.0)
        if qty <= 0:
            raise ValueError(f"Qty non valida per OCO leg {leg_index}: {qty}")

        if not self._should_execute_clean_entry(
            order_id=order_id,
            symbol=oco_spec.symbol,
            tf_minutes=oco_spec.tf_minutes,
            side=leg_side,
            price=price,
            acquistopulito=oco_spec.acquistopulito,
            context="oco_leg_fired",
        ):
            self._storage.append_event(
                "clean_entry_blocked",
                order_id,
                {"context": "oco_leg_fired", "leg_index": leg_index, "side": leg_side, "price": price},
            )
            self._rearm_oco_leg_after_clean_block(oco_spec, leg_spec)
            return

        try:
            exchange_resp = self._execute_market_order_on_exchange(leg_side, symbol, qty)
            self._finalize_oco_leg_filled(oco_spec, leg_index, price, symbol, exchange_resp)
        except Exception as exc:
            oco_spec.status = "error"
            self._handle_exchange_error(
                order_id=order_id,
                chat_id=oco_spec.chat_id,
                event_type="oco_leg_exchange_error",
                user_msg_prefix=f"OCO {order_id} leg {leg_index} su {symbol}",
                payload={"leg_index": leg_index, "price": price, "exchange_symbol": symbol, "qty": qty, "side": leg_side},
                exc=exc,
            )

    def _on_simple_fired(self, spec: SimpleOrderSpec, price: float):
        if spec.status != "active":
            return

        if not self._should_execute_clean_entry(
            order_id=spec.order_id,
            symbol=spec.symbol,
            tf_minutes=spec.tf_minutes,
            side=spec.side,
            price=price,
            acquistopulito=spec.acquistopulito,
            context="simple_fired",
        ):
            self._storage.append_event(
                "clean_entry_blocked",
                spec.order_id,
                {"context": "simple_fired", "side": spec.side, "price": price},
            )
            self._rearm_simple_order_after_clean_block(spec)
            return

        verb = "Vendita" if spec.side == "sell" else "Acquisto"
        symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)

        try:
            exchange_resp = self._execute_simple_order_on_exchange(spec)
            spec.status = "filled"
            self._storage.update_order_status(spec.order_id, "filled")
            self._storage.append_event(
                "simple_filled",
                spec.order_id,
                {
                    "price": price,
                    "exchange_symbol": symbol,
                    "exchange_order_id": exchange_resp.get("orderId"),
                    "exchange_status": exchange_resp.get("status"),
                    "executed_qty": exchange_resp.get("executedQty"),
                },
            )
            self._queue_message(
                spec.chat_id,
                f"{verb} {symbol} qty={spec.qty} eseguita a {price} (exchange orderId={exchange_resp.get('orderId')})",
            )
            if spec.side == "buy":
                self._dispatch_post_fill_action(
                    parent_order_id=spec.order_id,
                    chat_id=spec.chat_id,
                    symbol=spec.symbol,
                    hook_symbol=spec.hook_symbol,
                    side=spec.side,
                    qty=spec.qty,
                    tf_minutes=spec.tf_minutes,
                    fill_price=price,
                    post_fill_action=spec.post_fill_action,
                )
        except (self._binance_api_error_cls, self._binance_request_error_cls, self._binance_order_error_cls) as exc:
            spec.status = "error"
            self._handle_exchange_error(
                order_id=spec.order_id,
                chat_id=spec.chat_id,
                event_type="simple_exchange_error",
                user_msg_prefix=f"{verb.lower()} {symbol}",
                payload={"price": price, "exchange_symbol": symbol, "qty": spec.qty, "side": spec.side},
                exc=exc,
            )
        except Exception as exc:
            spec.status = "error"
            self._handle_exchange_error(
                order_id=spec.order_id,
                chat_id=spec.chat_id,
                event_type="simple_exchange_error",
                user_msg_prefix=f"{verb.lower()} {symbol}",
                payload={"price": price, "exchange_symbol": symbol, "qty": spec.qty, "side": spec.side},
                exc=exc,
            )

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        if update.effective_chat:
            context.application.bot_data["last_chat_id"] = update.effective_chat.id
        await self._show_main_menu(update, "Bot avviato. Usa i bottoni per navigare.")

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
            "/setpulito [preset|manuale|reset] - config globale clean-entry\n"
            "/o - lista ordini con order_id\n"
            "/account - riepilogo account Binance Spot\n"
            "/c ORDER_ID | /c a - cancella"
        )

        # Runtime settings summary (current values)
        oco_count = len(getattr(self, "_oco_orders", [])) if hasattr(self, "_oco_orders") else 0
        linked_trailing_count = len(
            [t for t in self._trailing_sell_orders if t.oco_parent_order_id is not None and t.status == "active"]
        )
        status_lines = [
            "\n\nValori correnti:\n",
            f"- Default TF (minuti): {self._default_tf_minutes}",
            f"- Timeframe seconds: {self._timeframe_seconds}",
            f"- Echo abilitato: {self._echo_enabled}",
            f"- Alert abilitato: {self._alert_enabled}",
            f"- Alert percent: {self._alert_percent}",
            f"- Alert reference price: {self._alert_reference_price}",
            f"- {self._clean_entry_summary()}",
            f"- Ordini attivi: sell={len(self._sell_orders)} buy={len(self._buy_orders)} function={len(self._function_orders)} trailing_sell={len(self._trailing_sell_orders)} trailing_buy={len(self._trailing_buy_orders)} oco={oco_count}",
            f"- Trailing SELL linked a OCO attivi: {linked_trailing_count}",
        ]

        await self._send(update, text + "\n".join(status_lines), reply_markup=self._main_menu_keyboard())

    async def _on_menu_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update) or not update.effective_message:
            return
        if update.effective_chat:
            context.application.bot_data["last_chat_id"] = update.effective_chat.id

        text = (update.effective_message.text or "").strip()
        lowered = self._normalize_menu_text(text)

        if lowered == "annulla":
            self._clear_ui_state(context)
            await self._show_main_menu(update, "Operazione annullata.")
            return

        if self._get_ui_state(context):
            handled = await self._handle_guided_flow(update, context, text)
            if handled:
                return

        # main menu shortcuts
        tokens = set(lowered.split())
        if lowered in {"menu", "help"} or "menu" in tokens or "help" in tokens:
            await self._show_main_menu(update)
            return
        # robust Info match: check tokens so 'ℹ️ Info' or 'info ℹ️' both match
        if "info" in tokens or lowered == "info":
            await self._info(update, context)
            return
        if "account" in tokens or lowered == "account":
            await self._cmd_account(update, context)
            return

        if lowered == "nuovo ordine":
            await self._show_orders_menu(update)
            return
        if lowered == "ordini attivi":
            await self._cmd_o(update)
            return
        if lowered == "impostazioni":
            await self._show_settings_menu(update)
            return
        if lowered == "indietro":
            await self._show_main_menu(update)
            return

        if lowered == "sell semplice":
            self._set_ui_state(context, "simple_symbol", {"kind": "simple", "side": "sell"})
            await self._send(update, "SELL semplice: inserisci SYMBOL (es. BTCUSDT)", reply_markup=self._cancel_keyboard())
            return
        if lowered == "buy semplice":
            self._set_ui_state(context, "simple_symbol", {"kind": "simple", "side": "buy"})
            await self._send(update, "BUY semplice: inserisci SYMBOL (es. BTCUSDT)", reply_markup=self._cancel_keyboard())
            return
        if lowered == "function":
            self._set_ui_state(context, "function_symbol", {"kind": "function"})
            await self._send(update, "FUNCTION: inserisci SYMBOL (es. BTCUSDT)", reply_markup=self._cancel_keyboard())
            return
        if lowered == "trailing sell":
            self._set_ui_state(context, "ts_symbol", {"kind": "trailing_sell"})
            await self._send(update, "TRAILING SELL: inserisci SYMBOL (es. BTCUSDT)", reply_markup=self._cancel_keyboard())
            return
        if lowered == "trailing buy":
            self._set_ui_state(context, "tb_symbol", {"kind": "trailing_buy"})
            await self._send(update, "TRAILING BUY: inserisci SYMBOL (es. BTCUSDT)", reply_markup=self._cancel_keyboard())
            return
        if lowered in {"oco", "oco order"}:
            self._set_ui_state(context, "oco_symbol", {"kind": "oco"})
            await self._send(update, "OCO: inserisci SYMBOL (es. BTCUSDT)", reply_markup=self._cancel_keyboard())
            return
        if lowered == "timeframe":
            self._set_ui_state(context, "set_timeframe", {})
            await self._send(update, "Seleziona timeframe di default", reply_markup=self._tf_keyboard())
            return
        if lowered == "alert":
            self._set_ui_state(context, "set_alert_mode", {})
            await self._send(update, "Alert BTCUSDT: scegli azione", reply_markup=self._echo_alert_keyboard())
            return
        if lowered == "echo":
            self._set_ui_state(context, "set_echo", {})
            await self._send(update, "Echo prezzi: scegli azione", reply_markup=self._echo_alert_keyboard())
            return
        if "setpulito" in tokens or ("set" in tokens and "pulito" in tokens):
            self._set_ui_state(context, "set_pulito_mode", {})
            await self._send(
                update,
                f"Config setPulito. {self._clean_entry_summary()}\nScegli Modalita.",
                reply_markup=self._set_pulito_mode_keyboard(),
            )
            return
        if lowered == "cancella ordine":
            self._set_ui_state(context, "cancel_order", {})
            await self._send(
                update,
                "Seleziona ordine (#id:pair:tipo), inserisci order_id manuale oppure scegli Tutti",
                reply_markup=self._cancel_order_keyboard(),
            )
            return

    async def _handle_guided_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
        state = self._get_ui_state(context)
        if not state:
            return False
        draft = self._get_draft(context)
        lowered = text.lower()
        normalized = self._normalize_menu_text(text)

        try:
            if state == "simple_symbol":
                symbol = text.upper()
                ok, message = self._validate_spot_symbol(symbol)
                if not ok:
                    await self._send(update, f"{message}\nReinserisci SYMBOL.", reply_markup=self._cancel_keyboard())
                    return True
                draft["symbol"] = symbol
                self._set_ui_state(context, "simple_op", draft)
                await self._send(update, "Scegli operatore trigger", reply_markup=self._operator_keyboard())
                return True
            if state == "simple_op":
                op_input = text.strip()
                mapped = None
                if op_input in ("<", "◀️", "◀", "←"):
                    mapped = "<"
                elif op_input in (">", "▶️", "▶", "→"):
                    mapped = ">"
                if mapped is None:
                    await self._send(update, "Operatore non valido: usa i bottoni < o >", reply_markup=self._operator_keyboard())
                    return True
                draft["op"] = mapped
                self._set_ui_state(context, "simple_trigger", draft)
                await self._send(update, "Inserisci valore trigger (es. 60000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "simple_trigger":
                draft["trigger"] = float(text)
                self._set_ui_state(context, "simple_qty", draft)
                await self._send(update, "Inserisci quantity (es. 0.001)", reply_markup=self._cancel_keyboard())
                return True
            if state == "simple_qty":
                draft["qty"] = float(text)
                self._set_ui_state(context, "simple_hook_choice", draft)
                await self._send(update, "Vuoi usare un pairhook?", reply_markup=self._yes_no_keyboard())
                return True
            if state == "simple_hook_choice":
                if normalized == "si":
                    self._set_ui_state(context, "simple_hook_symbol", draft)
                    await self._send(update, "Inserisci simbolo hook (es. ETHUSDT)", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "no":
                    draft["hook"] = None
                    self._set_ui_state(context, "simple_tf", draft)
                    await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "simple_hook_symbol":
                hook = text.upper()
                ok, message = self._validate_spot_symbol(hook, field_name="PAIRHOOK")
                if not ok:
                    await self._send(update, f"{message}\nReinserisci simbolo hook.", reply_markup=self._cancel_keyboard())
                    return True
                draft["hook"] = hook
                self._set_ui_state(context, "simple_tf", draft)
                await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                return True
            if state == "simple_tf":
                tf = self._parse_tf_choice(text)
                draft["tf"] = tf
                if draft.get("side") == "buy":
                    self._set_ui_state(context, "simple_clean_entry_choice", draft)
                    await self._send(update, "Attivare acquistopulito per questo BUY?", reply_markup=self._yes_no_keyboard())
                else:
                    draft["post_fill_action"] = None
                    draft["acquistopulito"] = False
                    self._set_ui_state(context, "simple_confirm", draft)
                    await self._send(
                        update,
                        f"Confermi ordine {draft['side']} su {draft['symbol']}?",
                        reply_markup=self._confirm_keyboard(),
                    )
                return True
            if state == "simple_clean_entry_choice":
                if normalized == "si":
                    draft["acquistopulito"] = True
                    self._set_ui_state(context, "simple_post_fill_choice", draft)
                    await self._send(update, "Vuoi configurare Auto OCO post-fill?", reply_markup=self._yes_no_keyboard())
                    return True
                if normalized == "no":
                    draft["acquistopulito"] = False
                    self._set_ui_state(context, "simple_post_fill_choice", draft)
                    await self._send(update, "Vuoi configurare Auto OCO post-fill?", reply_markup=self._yes_no_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "simple_post_fill_choice":
                if normalized == "si":
                    self._set_ui_state(context, "simple_post_fill_tp_mode", draft)
                    await self._send(update, "Seleziona tipo TP", reply_markup=self._post_fill_mode_keyboard())
                    return True
                if normalized == "no":
                    draft["post_fill_action"] = None
                    self._set_ui_state(context, "simple_confirm", draft)
                    await self._send(update, f"Confermi ordine {draft['side']} su {draft['symbol']}?", reply_markup=self._confirm_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "simple_post_fill_tp_mode":
                mode = self._parse_post_fill_mode_choice(normalized)
                if mode is None:
                    await self._send(update, "Selezione non valida: scegli tipo TP", reply_markup=self._post_fill_mode_keyboard())
                    return True
                draft["post_fill_tp_mode"] = mode
                self._set_ui_state(context, "simple_post_fill_tp_value", draft)
                if mode == "percent":
                    await self._send(update, "Inserisci TP percentuale (es: 3 oppure 3%)", reply_markup=self._cancel_keyboard())
                elif mode == "trailing":
                    await self._send(update, "Inserisci TP trailing percent (es: 1.5)", reply_markup=self._cancel_keyboard())
                else:
                    await self._send(update, "Inserisci TP fisso (es: 72000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "simple_post_fill_tp_value":
                mode = draft.get("post_fill_tp_mode")
                draft["post_fill_tp"] = self._format_post_fill_value(str(mode), text)
                self._set_ui_state(context, "simple_post_fill_sl_mode", draft)
                await self._send(update, "Seleziona tipo SL", reply_markup=self._post_fill_mode_keyboard())
                return True
            if state == "simple_post_fill_sl_mode":
                mode = self._parse_post_fill_mode_choice(normalized)
                if mode is None:
                    await self._send(update, "Selezione non valida: scegli tipo SL", reply_markup=self._post_fill_mode_keyboard())
                    return True
                draft["post_fill_sl_mode"] = mode
                self._set_ui_state(context, "simple_post_fill_sl_value", draft)
                if mode == "percent":
                    await self._send(update, "Inserisci SL percentuale (es: 1.5 oppure 1.5%)", reply_markup=self._cancel_keyboard())
                elif mode == "trailing":
                    await self._send(update, "Inserisci SL trailing percent (es: 1.5)", reply_markup=self._cancel_keyboard())
                else:
                    await self._send(update, "Inserisci SL fisso (es: 65000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "simple_post_fill_sl_value":
                mode = draft.get("post_fill_sl_mode")
                sl_text = self._format_post_fill_value(str(mode), text)
                draft["post_fill_action"] = self._build_post_fill_action_from_guided(draft["post_fill_tp"], sl_text)
                self._set_ui_state(context, "simple_confirm", draft)
                oco_token = self._post_fill_action_to_token(draft["post_fill_action"])
                await self._send(
                    update,
                    f"Confermi ordine {draft['side']} su {draft['symbol']} con Auto OCO?\n"
                    f"Dettagli: {oco_token}",
                    reply_markup=self._confirm_keyboard(),
                )
                return True
            if state == "simple_confirm":
                if normalized != "conferma":
                    await self._send(update, "Premi Conferma per creare l'ordine", reply_markup=self._confirm_keyboard())
                    return True
                parts = [
                    "/s" if draft["side"] == "sell" else "/b",
                    draft["symbol"],
                    draft["op"],
                    str(draft["trigger"]),
                    str(draft["qty"]),
                ]
                if draft.get("hook"):
                    parts.append(f"@{draft['hook']}")
                parts.append(f"tf={draft['tf']}")
                if draft.get("acquistopulito"):
                    parts.append("acquistopulito")
                if draft.get("post_fill_action"):
                    parts.append(self._post_fill_action_to_token(draft["post_fill_action"]))
                await self._cmd_simple(update, parts, side=draft["side"])
                self._clear_ui_state(context)
                await self._show_orders_menu(update)
                return True

            if state == "function_symbol":
                symbol = text.upper()
                ok, message = self._validate_spot_symbol(symbol)
                if not ok:
                    await self._send(update, f"{message}\nReinserisci SYMBOL.", reply_markup=self._cancel_keyboard())
                    return True
                draft["symbol"] = symbol
                self._set_ui_state(context, "function_op", draft)
                await self._send(update, "Scegli operatore trigger", reply_markup=self._operator_keyboard())
                return True
            if state == "function_op":
                op_input = text.strip()
                mapped = None
                if op_input in ("<", "◀️", "◀", "←"):
                    mapped = "<"
                elif op_input in (">", "▶️", "▶", "→"):
                    mapped = ">"
                if mapped is None:
                    await self._send(update, "Operatore non valido: usa i bottoni < o >", reply_markup=self._operator_keyboard())
                    return True
                draft["op"] = mapped
                self._set_ui_state(context, "function_trigger", draft)
                await self._send(update, "Inserisci trigger", reply_markup=self._cancel_keyboard())
                return True
            if state == "function_trigger":
                draft["trigger"] = float(text)
                self._set_ui_state(context, "function_qty", draft)
                await self._send(update, "Inserisci quantity", reply_markup=self._cancel_keyboard())
                return True
            if state == "function_qty":
                draft["qty"] = float(text)
                self._set_ui_state(context, "function_percent", draft)
                await self._send(update, "Inserisci percent trailing (es. 1.5)", reply_markup=self._cancel_keyboard())
                return True
            if state == "function_percent":
                draft["percent"] = float(text)
                self._set_ui_state(context, "function_hook_choice", draft)
                await self._send(update, "Vuoi usare un pairhook?", reply_markup=self._yes_no_keyboard())
                return True
            if state == "function_hook_choice":
                if normalized == "si":
                    self._set_ui_state(context, "function_hook_symbol", draft)
                    await self._send(update, "Inserisci simbolo hook", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "no":
                    draft["hook"] = None
                    self._set_ui_state(context, "function_tf", draft)
                    await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "function_hook_symbol":
                hook = text.upper()
                ok, message = self._validate_spot_symbol(hook, field_name="PAIRHOOK")
                if not ok:
                    await self._send(update, f"{message}\nReinserisci simbolo hook.", reply_markup=self._cancel_keyboard())
                    return True
                draft["hook"] = hook
                self._set_ui_state(context, "function_tf", draft)
                await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                return True
            if state == "function_tf":
                draft["tf"] = self._parse_tf_choice(text)
                self._set_ui_state(context, "function_clean_entry_choice", draft)
                await self._send(update, "Attivare acquistopulito per questo FUNCTION buy?", reply_markup=self._yes_no_keyboard())
                return True
            if state == "function_clean_entry_choice":
                if normalized == "si":
                    draft["acquistopulito"] = True
                    self._set_ui_state(context, "function_post_fill_choice", draft)
                    await self._send(update, "Vuoi configurare Auto OCO post-fill?", reply_markup=self._yes_no_keyboard())
                    return True
                if normalized == "no":
                    draft["acquistopulito"] = False
                    self._set_ui_state(context, "function_post_fill_choice", draft)
                    await self._send(update, "Vuoi configurare Auto OCO post-fill?", reply_markup=self._yes_no_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "function_post_fill_choice":
                if normalized == "si":
                    self._set_ui_state(context, "function_post_fill_tp_mode", draft)
                    await self._send(update, "Seleziona tipo TP", reply_markup=self._post_fill_mode_keyboard())
                    return True
                if normalized == "no":
                    draft["post_fill_action"] = None
                    self._set_ui_state(context, "function_confirm", draft)
                    await self._send(update, f"Confermi FUNCTION su {draft['symbol']}?", reply_markup=self._confirm_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "function_post_fill_tp_mode":
                mode = self._parse_post_fill_mode_choice(normalized)
                if mode is None:
                    await self._send(update, "Selezione non valida: scegli tipo TP", reply_markup=self._post_fill_mode_keyboard())
                    return True
                draft["post_fill_tp_mode"] = mode
                self._set_ui_state(context, "function_post_fill_tp_value", draft)
                if mode == "percent":
                    await self._send(update, "Inserisci TP percentuale (es: 3 oppure 3%)", reply_markup=self._cancel_keyboard())
                elif mode == "trailing":
                    await self._send(update, "Inserisci TP trailing percent (es: 1.5)", reply_markup=self._cancel_keyboard())
                else:
                    await self._send(update, "Inserisci TP fisso (es: 72000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "function_post_fill_tp_value":
                mode = draft.get("post_fill_tp_mode")
                draft["post_fill_tp"] = self._format_post_fill_value(str(mode), text)
                self._set_ui_state(context, "function_post_fill_sl_mode", draft)
                await self._send(update, "Seleziona tipo SL", reply_markup=self._post_fill_mode_keyboard())
                return True
            if state == "function_post_fill_sl_mode":
                mode = self._parse_post_fill_mode_choice(normalized)
                if mode is None:
                    await self._send(update, "Selezione non valida: scegli tipo SL", reply_markup=self._post_fill_mode_keyboard())
                    return True
                draft["post_fill_sl_mode"] = mode
                self._set_ui_state(context, "function_post_fill_sl_value", draft)
                if mode == "percent":
                    await self._send(update, "Inserisci SL percentuale (es: 1.5 oppure 1.5%)", reply_markup=self._cancel_keyboard())
                elif mode == "trailing":
                    await self._send(update, "Inserisci SL trailing percent (es: 1.5)", reply_markup=self._cancel_keyboard())
                else:
                    await self._send(update, "Inserisci SL fisso (es: 65000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "function_post_fill_sl_value":
                mode = draft.get("post_fill_sl_mode")
                sl_text = self._format_post_fill_value(str(mode), text)
                draft["post_fill_action"] = self._build_post_fill_action_from_guided(draft["post_fill_tp"], sl_text)
                self._set_ui_state(context, "function_confirm", draft)
                oco_token = self._post_fill_action_to_token(draft["post_fill_action"])
                await self._send(
                    update,
                    f"Confermi FUNCTION su {draft['symbol']} con Auto OCO?\n"
                    f"Dettagli: {oco_token}",
                    reply_markup=self._confirm_keyboard(),
                )
                return True
            if state == "function_confirm":
                if normalized != "conferma":
                    await self._send(update, "Premi Conferma per creare l'ordine", reply_markup=self._confirm_keyboard())
                    return True
                parts = [
                    "/f",
                    draft["symbol"],
                    draft["op"],
                    str(draft["trigger"]),
                    str(draft["qty"]),
                    str(draft["percent"]),
                ]
                if draft.get("hook"):
                    parts.append(f"@{draft['hook']}")
                parts.append(f"tf={draft['tf']}")
                if draft.get("acquistopulito"):
                    parts.append("acquistopulito")
                if draft.get("post_fill_action"):
                    parts.append(self._post_fill_action_to_token(draft["post_fill_action"]))
                await self._cmd_f(update, parts)
                self._clear_ui_state(context)
                await self._show_orders_menu(update)
                return True

            if state == "ts_symbol":
                symbol = text.upper()
                ok, message = self._validate_spot_symbol(symbol)
                if not ok:
                    await self._send(update, f"{message}\nReinserisci SYMBOL.", reply_markup=self._cancel_keyboard())
                    return True
                draft["symbol"] = symbol
                self._set_ui_state(context, "ts_percent", draft)
                await self._send(update, "Inserisci percent trailing", reply_markup=self._cancel_keyboard())
                return True
            if state == "ts_percent":
                draft["percent"] = float(text)
                self._set_ui_state(context, "ts_qty", draft)
                await self._send(update, "Inserisci quantity", reply_markup=self._cancel_keyboard())
                return True
            if state == "ts_qty":
                draft["qty"] = float(text)
                self._set_ui_state(context, "ts_limit_choice", draft)
                await self._send(update, "Vuoi impostare LIMIT?", reply_markup=self._yes_no_keyboard())
                return True
            if state == "ts_limit_choice":
                if normalized == "si":
                    self._set_ui_state(context, "ts_limit", draft)
                    await self._send(update, "Inserisci limit (es. 59000)", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "no":
                    draft["limit"] = None
                    self._set_ui_state(context, "ts_hook_choice", draft)
                    await self._send(update, "Vuoi usare pairhook?", reply_markup=self._yes_no_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "ts_limit":
                draft["limit"] = float(text)
                self._set_ui_state(context, "ts_hook_choice", draft)
                await self._send(update, "Vuoi usare pairhook?", reply_markup=self._yes_no_keyboard())
                return True
            if state == "ts_hook_choice":
                if normalized == "si":
                    self._set_ui_state(context, "ts_hook_symbol", draft)
                    await self._send(update, "Inserisci simbolo hook", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "no":
                    draft["hook"] = None
                    self._set_ui_state(context, "ts_tf", draft)
                    await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "ts_hook_symbol":
                hook = text.upper()
                ok, message = self._validate_spot_symbol(hook, field_name="PAIRHOOK")
                if not ok:
                    await self._send(update, f"{message}\nReinserisci simbolo hook.", reply_markup=self._cancel_keyboard())
                    return True
                draft["hook"] = hook
                self._set_ui_state(context, "ts_tf", draft)
                await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                return True
            if state == "ts_tf":
                draft["tf"] = self._parse_tf_choice(text)
                self._set_ui_state(context, "ts_confirm", draft)
                await self._send(update, f"Confermi TRAILING SELL su {draft['symbol']}?", reply_markup=self._confirm_keyboard())
                return True
            if state == "ts_confirm":
                if normalized != "conferma":
                    await self._send(update, "Premi Conferma per creare l'ordine", reply_markup=self._confirm_keyboard())
                    return True
                parts = ["/S", draft["symbol"], str(draft["percent"]), str(draft["qty"])]
                if draft.get("limit") is not None:
                    parts.append(str(draft["limit"]))
                if draft.get("hook"):
                    parts.append(f"@{draft['hook']}")
                parts.append(f"tf={draft['tf']}")
                await self._cmd_S(update, parts)
                self._clear_ui_state(context)
                await self._show_orders_menu(update)
                return True

            if state == "tb_symbol":
                symbol = text.upper()
                ok, message = self._validate_spot_symbol(symbol)
                if not ok:
                    await self._send(update, f"{message}\nReinserisci SYMBOL.", reply_markup=self._cancel_keyboard())
                    return True
                draft["symbol"] = symbol
                self._set_ui_state(context, "tb_percent", draft)
                await self._send(update, "Inserisci percent trailing", reply_markup=self._cancel_keyboard())
                return True
            if state == "tb_percent":
                draft["percent"] = float(text)
                self._set_ui_state(context, "tb_qty", draft)
                await self._send(update, "Inserisci quantity", reply_markup=self._cancel_keyboard())
                return True
            if state == "tb_qty":
                draft["qty"] = float(text)
                self._set_ui_state(context, "tb_limit", draft)
                await self._send(update, "Inserisci LIMIT", reply_markup=self._cancel_keyboard())
                return True
            if state == "tb_limit":
                draft["limit"] = float(text)
                self._set_ui_state(context, "tb_tf", draft)
                await self._send(update, "Seleziona timeframe", reply_markup=self._tf_keyboard())
                return True
            if state == "tb_tf":
                draft["tf"] = self._parse_tf_choice(text)
                self._set_ui_state(context, "tb_clean_entry_choice", draft)
                await self._send(update, "Attivare acquistopulito per questo TRAILING BUY?", reply_markup=self._yes_no_keyboard())
                return True
            if state == "tb_clean_entry_choice":
                if normalized == "si":
                    draft["acquistopulito"] = True
                    self._set_ui_state(context, "tb_post_fill_choice", draft)
                    await self._send(update, "Vuoi configurare Auto OCO post-fill?", reply_markup=self._yes_no_keyboard())
                    return True
                if normalized == "no":
                    draft["acquistopulito"] = False
                    self._set_ui_state(context, "tb_post_fill_choice", draft)
                    await self._send(update, "Vuoi configurare Auto OCO post-fill?", reply_markup=self._yes_no_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "tb_post_fill_choice":
                if normalized == "si":
                    self._set_ui_state(context, "tb_post_fill_tp_mode", draft)
                    await self._send(update, "Seleziona tipo TP", reply_markup=self._post_fill_mode_keyboard())
                    return True
                if normalized == "no":
                    draft["post_fill_action"] = None
                    self._set_ui_state(context, "tb_confirm", draft)
                    await self._send(update, f"Confermi TRAILING BUY su {draft['symbol']}?", reply_markup=self._confirm_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "tb_post_fill_tp_mode":
                mode = self._parse_post_fill_mode_choice(normalized)
                if mode is None:
                    await self._send(update, "Selezione non valida: scegli tipo TP", reply_markup=self._post_fill_mode_keyboard())
                    return True
                draft["post_fill_tp_mode"] = mode
                self._set_ui_state(context, "tb_post_fill_tp_value", draft)
                if mode == "percent":
                    await self._send(update, "Inserisci TP percentuale (es: 3 oppure 3%)", reply_markup=self._cancel_keyboard())
                elif mode == "trailing":
                    await self._send(update, "Inserisci TP trailing percent (es: 1.5)", reply_markup=self._cancel_keyboard())
                else:
                    await self._send(update, "Inserisci TP fisso (es: 72000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "tb_post_fill_tp_value":
                mode = draft.get("post_fill_tp_mode")
                draft["post_fill_tp"] = self._format_post_fill_value(str(mode), text)
                self._set_ui_state(context, "tb_post_fill_sl_mode", draft)
                await self._send(update, "Seleziona tipo SL", reply_markup=self._post_fill_mode_keyboard())
                return True
            if state == "tb_post_fill_sl_mode":
                mode = self._parse_post_fill_mode_choice(normalized)
                if mode is None:
                    await self._send(update, "Selezione non valida: scegli tipo SL", reply_markup=self._post_fill_mode_keyboard())
                    return True
                draft["post_fill_sl_mode"] = mode
                self._set_ui_state(context, "tb_post_fill_sl_value", draft)
                if mode == "percent":
                    await self._send(update, "Inserisci SL percentuale (es: 1.5 oppure 1.5%)", reply_markup=self._cancel_keyboard())
                elif mode == "trailing":
                    await self._send(update, "Inserisci SL trailing percent (es: 1.5)", reply_markup=self._cancel_keyboard())
                else:
                    await self._send(update, "Inserisci SL fisso (es: 65000)", reply_markup=self._cancel_keyboard())
                return True
            if state == "tb_post_fill_sl_value":
                mode = draft.get("post_fill_sl_mode")
                sl_text = self._format_post_fill_value(str(mode), text)
                draft["post_fill_action"] = self._build_post_fill_action_from_guided(draft["post_fill_tp"], sl_text)
                self._set_ui_state(context, "tb_confirm", draft)
                oco_token = self._post_fill_action_to_token(draft["post_fill_action"])
                await self._send(
                    update,
                    f"Confermi TRAILING BUY su {draft['symbol']} con Auto OCO?\n"
                    f"Dettagli: {oco_token}",
                    reply_markup=self._confirm_keyboard(),
                )
                return True
            if state == "tb_confirm":
                if normalized != "conferma":
                    await self._send(update, "Premi Conferma per creare l'ordine", reply_markup=self._confirm_keyboard())
                    return True
                parts = ["/B", draft["symbol"], str(draft["percent"]), str(draft["qty"]), str(draft["limit"]), f"tf={draft['tf']}"]
                if draft.get("acquistopulito"):
                    parts.append("acquistopulito")
                if draft.get("post_fill_action"):
                    parts.append(self._post_fill_action_to_token(draft["post_fill_action"]))
                await self._cmd_B(update, parts)
                self._clear_ui_state(context)
                await self._show_orders_menu(update)
                return True

            # OCO guided flow
            if state == "oco_symbol":
                symbol = text.upper()
                ok, message = self._validate_spot_symbol(symbol)
                if not ok:
                    await self._send(update, f"{message}\nReinserisci SYMBOL.", reply_markup=self._cancel_keyboard())
                    return True
                draft["symbol"] = symbol
                self._set_ui_state(context, "oco_side", draft)
                await self._send(update, "Seleziona side per OCO (buy/sell)", reply_markup=self._side_keyboard())
                return True
            if state == "oco_side":
                if normalized not in {"buy", "sell"}:
                    await self._send(update, "Scegli buy o sell", reply_markup=self._side_keyboard())
                    return True
                draft["side"] = normalized
                draft["legs"] = []
                if normalized == "buy":
                    self._set_ui_state(context, "oco_clean_entry_choice", draft)
                    await self._send(update, "Attivare acquistopulito per questo OCO buy?", reply_markup=self._yes_no_keyboard())
                    return True
                draft["acquistopulito"] = False
                self._set_ui_state(context, "oco_leg1_type", draft)
                await self._send(update, "Leg 1: scegli tipo (limit/stop_limit/market)", reply_markup=self._oco_type_keyboard())
                return True
            if state == "oco_clean_entry_choice":
                if normalized == "si":
                    draft["acquistopulito"] = True
                    self._set_ui_state(context, "oco_leg1_type", draft)
                    await self._send(update, "Leg 1: scegli tipo (limit/stop_limit/market)", reply_markup=self._oco_type_keyboard())
                    return True
                if normalized == "no":
                    draft["acquistopulito"] = False
                    self._set_ui_state(context, "oco_leg1_type", draft)
                    await self._send(update, "Leg 1: scegli tipo (limit/stop_limit/market)", reply_markup=self._oco_type_keyboard())
                    return True
                await self._send(update, "Risposta non valida: scegli Si o No", reply_markup=self._yes_no_keyboard())
                return True
            if state == "oco_leg1_type":
                if normalized not in {"limit", "stop_limit", "market"}:
                    await self._send(update, "Scegli tipo leg valido", reply_markup=self._oco_type_keyboard())
                    return True
                draft["current_leg"] = {"leg_index": 1, "ordertype": normalized}
                if normalized == "limit":
                    self._set_ui_state(context, "oco_leg1_price", draft)
                    await self._send(update, "Inserisci prezzo limit per leg 1", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "stop_limit":
                    self._set_ui_state(context, "oco_leg1_stop", draft)
                    await self._send(update, "Inserisci stop price per leg 1", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "market":
                    self._set_ui_state(context, "oco_leg1_qty", draft)
                    await self._send(update, "Inserisci quantity per leg 1", reply_markup=self._cancel_keyboard())
                    return True
            if state == "oco_leg1_price":
                draft["current_leg"]["price"] = float(text)
                self._set_ui_state(context, "oco_leg1_qty", draft)
                await self._send(update, "Inserisci quantity per leg 1", reply_markup=self._cancel_keyboard())
                return True
            if state == "oco_leg1_stop":
                draft["current_leg"]["stop_price"] = float(text)
                self._set_ui_state(context, "oco_leg1_limit", draft)
                await self._send(update, "Inserisci limit price per leg 1", reply_markup=self._cancel_keyboard())
                return True
            if state == "oco_leg1_limit":
                draft["current_leg"]["limit_price"] = float(text)
                self._set_ui_state(context, "oco_leg1_qty", draft)
                await self._send(update, "Inserisci quantity per leg 1", reply_markup=self._cancel_keyboard())
                return True
            if state == "oco_leg1_qty":
                draft["current_leg"]["qty"] = float(text)
                # finalize leg1
                leg = draft.pop("current_leg")
                leg["side"] = draft["side"]
                draft["legs"].append(leg)
                # start leg2
                self._set_ui_state(context, "oco_leg2_type", draft)
                await self._send(update, "Leg 2: scegli tipo (limit/stop_limit/market)", reply_markup=self._oco_type_keyboard())
                return True
            if state == "oco_leg2_type":
                if normalized not in {"limit", "stop_limit", "market"}:
                    await self._send(update, "Scegli tipo leg valido", reply_markup=self._oco_type_keyboard())
                    return True
                draft["current_leg"] = {"leg_index": 2, "ordertype": normalized}
                if normalized == "limit":
                    self._set_ui_state(context, "oco_leg2_price", draft)
                    await self._send(update, "Inserisci prezzo limit per leg 2", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "stop_limit":
                    self._set_ui_state(context, "oco_leg2_stop", draft)
                    await self._send(update, "Inserisci stop price per leg 2", reply_markup=self._cancel_keyboard())
                    return True
                if normalized == "market":
                    self._set_ui_state(context, "oco_leg2_qty", draft)
                    await self._send(update, "Inserisci quantity per leg 2", reply_markup=self._cancel_keyboard())
                    return True
            if state == "oco_leg2_price":
                draft["current_leg"]["price"] = float(text)
                self._set_ui_state(context, "oco_leg2_qty", draft)
                await self._send(update, "Inserisci quantity per leg 2", reply_markup=self._cancel_keyboard())
                return True
            if state == "oco_leg2_stop":
                draft["current_leg"]["stop_price"] = float(text)
                self._set_ui_state(context, "oco_leg2_limit", draft)
                await self._send(update, "Inserisci limit price per leg 2", reply_markup=self._cancel_keyboard())
                return True
            if state == "oco_leg2_limit":
                draft["current_leg"]["limit_price"] = float(text)
                self._set_ui_state(context, "oco_leg2_qty", draft)
                await self._send(update, "Inserisci quantity per leg 2", reply_markup=self._cancel_keyboard())
                return True
            if state == "oco_leg2_qty":
                draft["current_leg"]["qty"] = float(text)
                leg = draft.pop("current_leg")
                leg["side"] = draft["side"]
                draft["legs"].append(leg)
                # optional tf
                self._set_ui_state(context, "oco_tf", draft)
                await self._send(update, "Seleziona timeframe opzionale (Default/1/5/15/30/60/120/240/1440)", reply_markup=self._tf_keyboard())
                return True
            if state == "oco_tf":
                tf = self._parse_tf_choice(text)
                draft["tf"] = tf
                self._set_ui_state(context, "oco_confirm", draft)
                legs_text = []
                for l in draft["legs"]:
                    legs_text.append(str(l))
                await self._send(update, f"Riepilogo OCO: symbol={draft['symbol']} side={draft['side']} tf={tf}\nLegs:\n" + "\n".join(legs_text), reply_markup=self._confirm_keyboard())
                return True
            if state == "oco_confirm":
                if normalized != "conferma":
                    await self._send(update, "Premi Conferma per creare l'OCO (verrà salvato come preview)", reply_markup=self._confirm_keyboard())
                    return True
                # persist OCO and attach to engine
                order_id = self._new_order_id()
                chat_id = update.effective_chat.id if update.effective_chat else None
                legs = draft.get("legs", [])
                tf = draft.get("tf", self._default_tf_minutes)
                self._storage.save_oco_order(
                    order_id=order_id,
                    chat_id=chat_id,
                    symbol=draft["symbol"],
                    side=draft["side"],
                    legs=legs,
                    hook_symbol=None,
                    tf_minutes=tf,
                    next_eval_at=self._next_boundary_epoch(tf),
                    last_eval_at=None,
                    acquistopulito=bool(draft.get("acquistopulito", False)),
                    status="active",
                )
                oco_spec = OcoSpec(
                    order_id=order_id,
                    symbol=draft["symbol"],
                    side=draft["side"],
                    legs=legs,
                    chat_id=chat_id,
                    parent_order_id=None,
                    tf_minutes=tf,
                    acquistopulito=bool(draft.get("acquistopulito", False)),
                )
                # keep in-memory record for UI and lifecycle operations
                if not hasattr(self, "_oco_orders"):
                    self._oco_orders = []
                self._oco_orders.append(oco_spec)
                self._attach_oco_to_engine(oco_spec)
                self._storage.append_event("oco_created", order_id, draft)
                await self._send(update, f"OCO {order_id} creato e attivato.")
                self._clear_ui_state(context)
                await self._show_orders_menu(update)
                return True

            if state == "set_pulito_mode":
                if "manual" in normalized:
                    draft = dict(self._clean_entry_config)
                    self._set_ui_state(context, "set_pulito_manual_field", draft)
                    await self._send(
                        update,
                        f"setPulito Manuale. {self._clean_entry_summary(draft)}",
                        reply_markup=self._set_pulito_manual_fields_keyboard(),
                    )
                    return True
                if "automatic" in normalized:
                    self._set_ui_state(context, "set_pulito_preset", {})
                    await self._send(
                        update,
                        "setPulito Automatico: scegli preset.",
                        reply_markup=self._set_pulito_preset_keyboard(),
                    )
                    return True
                if "stato" in normalized:
                    await self._send(
                        update,
                        self._clean_entry_summary(),
                        reply_markup=self._set_pulito_mode_keyboard(),
                    )
                    return True
                await self._send(update, "Scegli Manuale, Automatico o Stato", reply_markup=self._set_pulito_mode_keyboard())
                return True

            if state == "set_pulito_preset":
                if normalized == "indietro":
                    self._set_ui_state(context, "set_pulito_mode", {})
                    await self._send(update, "Config setPulito: scegli modalita.", reply_markup=self._set_pulito_mode_keyboard())
                    return True
                preset = self._parse_set_pulito_preset_choice(normalized)
                if preset is None:
                    await self._send(
                        update,
                        "Preset non valido: scegli Conservativo, Bilanciato o Aggressivo",
                        reply_markup=self._set_pulito_preset_keyboard(),
                    )
                    return True
                self._apply_clean_entry_preset(preset)
                self._persist_clean_entry_settings()
                await self._send(update, f"setPulito aggiornato: {self._clean_entry_summary()}")
                self._clear_ui_state(context)
                await self._show_settings_menu(update)
                return True

            if state == "set_pulito_manual_field":
                if normalized in {"salva", "fine"}:
                    self._clean_entry_preset = "manuale"
                    self._clean_entry_config = self._normalize_clean_entry_config(draft)
                    self._persist_clean_entry_settings()
                    await self._send(update, f"setPulito salvato: {self._clean_entry_summary()}")
                    self._clear_ui_state(context)
                    await self._show_settings_menu(update)
                    return True
                if normalized == "indietro":
                    self._set_ui_state(context, "set_pulito_mode", {})
                    await self._send(update, "Config setPulito: scegli modalita.", reply_markup=self._set_pulito_mode_keyboard())
                    return True
                if "stato" in normalized:
                    await self._send(
                        update,
                        self._clean_entry_summary(draft),
                        reply_markup=self._set_pulito_manual_fields_keyboard(),
                    )
                    return True
                field = self._parse_set_pulito_manual_field_choice(normalized)
                if field is None:
                    await self._send(
                        update,
                        "Campo non valido: scegli uno dei bottoni manuali",
                        reply_markup=self._set_pulito_manual_fields_keyboard(),
                    )
                    return True
                draft["edit_field"] = field
                self._set_ui_state(context, "set_pulito_manual_value", draft)
                hints = {
                    "rsi_min": "Inserisci RSI minimo (es. 50)",
                    "adx_min": "Inserisci ADX minimo (es. 18)",
                    "required_checks": "Inserisci check minimi (1-5)",
                    "require_trend": "Inserisci 1/0 (oppure si/no) per trend",
                    "require_volume": "Inserisci 1/0 (oppure si/no) per volume",
                    "require_price_above_ema": "Inserisci 1/0 (oppure si/no) per price>=EMA",
                }
                await self._send(update, hints[field], reply_markup=self._cancel_keyboard())
                return True

            if state == "set_pulito_manual_value":
                field = str(draft.get("edit_field") or "")
                if field not in {
                    "rsi_min",
                    "adx_min",
                    "required_checks",
                    "require_trend",
                    "require_volume",
                    "require_price_above_ema",
                }:
                    self._set_ui_state(context, "set_pulito_manual_field", draft)
                    await self._send(
                        update,
                        "Campo manuale non valido, riprova.",
                        reply_markup=self._set_pulito_manual_fields_keyboard(),
                    )
                    return True

                if field in {"rsi_min", "adx_min"}:
                    draft[field] = float(text)
                elif field == "required_checks":
                    draft[field] = int(float(text))
                else:
                    draft[field] = self._parse_bool_like(text)

                draft.pop("edit_field", None)
                draft = self._normalize_clean_entry_config(draft)
                self._set_ui_state(context, "set_pulito_manual_field", draft)
                await self._send(
                    update,
                    f"Valore aggiornato. {self._clean_entry_summary(draft)}",
                    reply_markup=self._set_pulito_manual_fields_keyboard(),
                )
                return True

            if state == "set_timeframe":
                tf = self._parse_tf_choice(text)
                await self._cmd_t(update, ["/t", str(tf)])
                self._clear_ui_state(context)
                await self._show_settings_menu(update)
                return True
            if state == "set_echo":
                if normalized not in {"abilita", "disabilita"}:
                    await self._send(update, "Scegli Abilita o Disabilita", reply_markup=self._echo_alert_keyboard())
                    return True
                await self._cmd_e(update, ["/e", "1" if normalized == "abilita" else "0"])
                self._clear_ui_state(context)
                await self._show_settings_menu(update)
                return True
            if state == "set_alert_mode":
                if normalized == "disabilita":
                    await self._cmd_a(update, ["/a", "0"])
                    self._clear_ui_state(context)
                    await self._show_settings_menu(update)
                    return True
                if normalized == "abilita":
                    self._set_ui_state(context, "set_alert_percent", draft)
                    await self._send(update, "Inserisci percentuale alert (es. 2.0)", reply_markup=self._cancel_keyboard())
                    return True
                await self._send(update, "Scegli Abilita o Disabilita", reply_markup=self._echo_alert_keyboard())
                return True
            if state == "set_alert_percent":
                pct = float(text)
                await self._cmd_a(update, ["/a", "1", str(pct)])
                self._clear_ui_state(context)
                await self._show_settings_menu(update)
                return True
            if state == "cancel_order":
                if normalized == "tutti":
                    await self._cmd_c(update, ["/c", "a"])
                    self._clear_ui_state(context)
                    await self._show_settings_menu(update)
                    return True
                target = self._extract_order_id_from_cancel_input(text)
                await self._cmd_c(update, ["/c", target])
                self._clear_ui_state(context)
                await self._show_settings_menu(update)
                return True
        except ValueError as exc:
            await self._send(update, f"Valore non valido: {exc}")
            return True
        except Exception as exc:
            await self._send(update, f"Errore: {exc}")
            self._clear_ui_state(context)
            await self._show_main_menu(update)
            return True

        return False

    def _parse_tf_choice(self, text: str) -> int:
        lowered = text.strip().lower()
        if lowered == "default":
            return self._default_tf_minutes
        tf = int(lowered)
        if tf not in VALID_TF_MINUTES:
            raise ValueError("Timeframe valido: 1,5,15,30,60,120,240,1440")
        return tf

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
            elif cmd == "/setpulito":
                await self._cmd_setpulito(update, parts)
            elif cmd == "/o":
                await self._cmd_o(update)
            elif cmd == "/account":
                await self._cmd_account(update, context)
            elif cmd == "/c":
                await self._cmd_c(update, parts)
            elif cmd in {"/start", "/info"}:
                return
            else:
                await self._send(update, "Comando non riconosciuto. Usa /info")
        except Exception as exc:
            await self._send(update, f"Errore comando: {exc}")

    async def _cmd_account(self, update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None):
        if not self._is_authorized(update):
            return

        if self._exchange_client is None:
            await self._send(
                update,
                "Account non disponibile: configura BINANCE_API_KEY e BINANCE_SECRET_KEY con permessi read.",
            )
            return

        try:
            account = self._exchange_client.get_account()
            open_orders = self._exchange_client.get_open_orders()
        except (self._binance_api_error_cls, self._binance_request_error_cls, self._binance_order_error_cls) as exc:
            self._storage.append_event(
                "account_snapshot_failed",
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            await self._send(update, f"Errore lettura account Binance: {exc}")
            return
        except Exception as exc:
            self._storage.append_event(
                "account_snapshot_failed",
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            await self._send(update, "Errore interno durante la lettura account Binance.")
            return

        balances = account.get("balances") or []
        assets_rows = []
        estimable_total_usdt = 0.0
        not_estimable = 0

        for row in balances:
            asset = str(row.get("asset") or "").upper()
            free = self._to_float(row.get("free"))
            locked = self._to_float(row.get("locked"))
            total = free + locked
            if total <= 0:
                continue

            usdt_estimate = self._estimate_asset_usdt(asset, total)
            if usdt_estimate is None:
                not_estimable += 1
            else:
                estimable_total_usdt += usdt_estimate

            assets_rows.append((asset, free, locked, total, usdt_estimate))

        assets_rows.sort(key=lambda x: x[3], reverse=True)

        update_ms = account.get("updateTime")
        try:
            account_ts = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(update_ms) / 1000.0)) if update_ms else "-"
            )
        except Exception:
            account_ts = str(update_ms)

        lines = ["Account Binance Spot", f"Aggiornamento: {account_ts}"]

        permissions = account.get("permissions") or []
        if permissions:
            lines.append(f"Permessi: {', '.join(str(p) for p in permissions)}")

        lines.append("")
        lines.append("Asset posseduti:")
        if not assets_rows:
            lines.append("- Nessun asset con saldo > 0")
        else:
            for asset, free, locked, total, usdt_estimate in assets_rows:
                usdt_label = "n/d" if usdt_estimate is None else f"{usdt_estimate:.2f}"
                lines.append(
                    f"- {asset}: free={self._fmt_amount(free)} locked={self._fmt_amount(locked)} "
                    f"tot={self._fmt_amount(total)} ~USDT={usdt_label}"
                )

        lines.append("")
        lines.append(f"Totale stimato ~USDT: {estimable_total_usdt:.2f} (asset non stimabili: {not_estimable})")

        lines.append("")
        lines.append("Ordini aperti (max 20):")
        if not open_orders:
            lines.append("- Nessun ordine aperto")
        else:
            for order in list(open_orders)[:20]:
                symbol = order.get("symbol")
                side = order.get("side")
                order_type = order.get("type")
                qty = order.get("origQty")
                price = order.get("price")
                stop_price = order.get("stopPrice")
                status = order.get("status")
                lines.append(
                    f"- {symbol} {side} {order_type} qty={qty} price={price} stop={stop_price} status={status}"
                )
        lines.append(f"Totale ordini aperti: {len(open_orders)}")

        self._storage.append_event(
            "account_snapshot_ok",
            payload={
                "assets_non_zero": len(assets_rows),
                "open_orders": len(open_orders),
                "estimable_total_usdt": round(estimable_total_usdt, 8),
                "not_estimable_assets": not_estimable,
            },
        )
        await self._send_chunked(update, lines)

    async def _cmd_simple(self, update: Update, parts: List[str], side: str):
        parts, tf_minutes = self._extract_tf(parts)
        parts, post_fill_action = self._extract_post_fill_action(parts)
        parts, acquistopulito = self._extract_acquistopulito(parts)
        symbol, op, trigger_val, qty, hook = self._parse_simple_order(parts)
        ok, message = self._validate_spot_symbol(symbol)
        if not ok:
            raise ValueError(message)
        if hook:
            ok, message = self._validate_spot_symbol(hook, field_name="PAIRHOOK")
            if not ok:
                raise ValueError(message)
        if side != "buy" and post_fill_action is not None:
            raise ValueError("post_fill_action supportata solo su ordini buy")
        if side != "buy" and acquistopulito:
            raise ValueError("acquistopulito supportato solo su ordini buy")
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
            post_fill_action=post_fill_action,
            acquistopulito=acquistopulito,
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
            post_fill_action=spec.post_fill_action,
            acquistopulito=spec.acquistopulito,
            status=spec.status,
        )
        self._storage.append_event(
            "simple_created",
            spec.order_id,
            {"side": side, "symbol": symbol, "tf": tf_minutes, "acquistopulito": spec.acquistopulito},
        )

        if side == "sell":
            self._sell_orders.append(spec)
        else:
            self._buy_orders.append(spec)
        exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
        await self._send(update, f"Ordine {side} inserito: order_id={spec.order_id} watch={spec.symbol} exec={exec_symbol}")

    async def _cmd_f(self, update: Update, parts: List[str]):
        parts, tf_minutes = self._extract_tf(parts)
        parts, post_fill_action = self._extract_post_fill_action(parts)
        parts, acquistopulito = self._extract_acquistopulito(parts)
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
        ok, message = self._validate_spot_symbol(symbol)
        if not ok:
            raise ValueError(message)
        if hook:
            ok, message = self._validate_spot_symbol(hook, field_name="PAIRHOOK")
            if not ok:
                raise ValueError(message)

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
            post_fill_action,
            acquistopulito,
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
            post_fill_action=spec.post_fill_action,
            acquistopulito=spec.acquistopulito,
            status="active",
        )
        self._storage.append_event(
            "function_created",
            order_id,
            {"symbol": symbol, "tf": tf_minutes, "acquistopulito": spec.acquistopulito},
        )
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
        ok, message = self._validate_spot_symbol(symbol)
        if not ok:
            raise ValueError(message)
        if hook:
            ok, message = self._validate_spot_symbol(hook, field_name="PAIRHOOK")
            if not ok:
                raise ValueError(message)

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
        parts, post_fill_action = self._extract_post_fill_action(parts)
        parts, acquistopulito = self._extract_acquistopulito(parts)
        if len(parts) < 5:
            raise ValueError("Formato: /B SYMBOL PERCENT QTY LIMIT")

        symbol = parts[1].upper()
        percent = float(parts[2])
        qty = float(parts[3])
        limit = float(parts[4])
        ok, message = self._validate_spot_symbol(symbol)
        if not ok:
            raise ValueError(message)

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
            post_fill_action,
            acquistopulito,
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
            post_fill_action=spec.post_fill_action,
            acquistopulito=spec.acquistopulito,
            status=spec.status,
        )
        self._storage.append_event(
            "trailing_buy_created",
            order_id,
            {"symbol": symbol, "tf": tf_minutes, "acquistopulito": spec.acquistopulito},
        )
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
            self._alert_reference_price = self._feed.get_price("BTCUSDT", self._default_tf_minutes)
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

    async def _cmd_setpulito(self, update: Update, parts: List[str]):
        usage = (
            "Formato: /setpulito [preset NOME|manuale key=value...|reset]\n"
            "Preset disponibili: conservativo, bilanciato, aggressivo\n"
            "Chiavi manuale: rsi, adx, checks, trend, volume, priceema"
        )
        if len(parts) == 1:
            await self._send(update, f"{self._clean_entry_summary()}\n{usage}")
            return

        raw_mode = parts[1].strip().lower()
        mode = raw_mode.replace("_", "")

        if mode in {"reset", "default"}:
            self._apply_clean_entry_preset("bilanciato")
            self._persist_clean_entry_settings()
            await self._send(update, f"setPulito resettato: {self._clean_entry_summary()}")
            return

        if mode in CLEAN_ENTRY_PRESETS:
            self._apply_clean_entry_preset(mode)
            self._persist_clean_entry_settings()
            await self._send(update, f"setPulito aggiornato: {self._clean_entry_summary()}")
            return

        if mode in {"preset", "auto", "automatico"}:
            if len(parts) < 3:
                raise ValueError("Preset mancante. Usa: /setpulito preset conservativo|bilanciato|aggressivo")
            self._apply_clean_entry_preset(parts[2])
            self._persist_clean_entry_settings()
            await self._send(update, f"setPulito aggiornato: {self._clean_entry_summary()}")
            return

        tokens = parts[2:] if mode == "manuale" else parts[1:]
        if not tokens:
            raise ValueError(usage)

        aliases = {
            "rsi": "rsi_min",
            "rsimin": "rsi_min",
            "rsi_min": "rsi_min",
            "adx": "adx_min",
            "adxmin": "adx_min",
            "adx_min": "adx_min",
            "checks": "required_checks",
            "check": "required_checks",
            "required_checks": "required_checks",
            "minchecks": "required_checks",
            "trend": "require_trend",
            "volume": "require_volume",
            "price": "require_price_above_ema",
            "priceema": "require_price_above_ema",
            "price_above_ema": "require_price_above_ema",
            "require_price_above_ema": "require_price_above_ema",
        }
        updates: Dict[str, Any] = {}
        for token in tokens:
            if "=" not in token:
                raise ValueError(f"Token non valido: {token}. Usa key=value")
            raw_key, raw_value = token.split("=", 1)
            key = aliases.get(raw_key.strip().lower().replace("-", "").replace(" ", ""))
            if key is None:
                raise ValueError(f"Chiave non supportata: {raw_key}")
            value = raw_value.strip()
            if key in {"rsi_min", "adx_min"}:
                updates[key] = float(value)
            elif key == "required_checks":
                updates[key] = int(float(value))
            else:
                updates[key] = self._parse_bool_like(value)

        self._clean_entry_preset = "manuale"
        manual_cfg = dict(self._clean_entry_config)
        manual_cfg.update(updates)
        self._clean_entry_config = self._normalize_clean_entry_config(manual_cfg)
        self._persist_clean_entry_settings()
        await self._send(update, f"setPulito aggiornato: {self._clean_entry_summary()}")

    async def _cmd_o(self, update: Update):
        def _post_fill_label(spec: Optional[Dict[str, Any]]) -> str:
            if not spec:
                return "none"
            if spec.get("type") != "oco":
                return str(spec.get("type"))
            tp = spec.get("tp") or {}
            sl = spec.get("sl") or {}
            return f"oco(tp={tp.get('mode')}:{tp.get('value')},sl={sl.get('mode')}:{sl.get('value')})"

        def _human_time(ts: Optional[int]) -> str:
            if ts is None:
                return "-"
            try:
                return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))
            except Exception:
                return str(ts)

        lines = ["Ordini attivi (order_id):"]
        lines.append("SELL:")
        for s in self._sell_orders:
            if s.status != "active":
                continue
            lines.append(f"{s.order_id} watch={s.symbol} exec={self._exec_symbol(s.symbol, s.hook_symbol)} {s.op} {s.trigger} qty={s.qty} tf={s.tf_minutes}m next={_human_time(s.next_eval_at)} post_fill={_post_fill_label(s.post_fill_action)} status={s.status}")
        lines.append("BUY:")
        for b in self._buy_orders:
            if b.status != "active":
                continue
            lines.append(f"{b.order_id} watch={b.symbol} exec={self._exec_symbol(b.symbol, b.hook_symbol)} {b.op} {b.trigger} qty={b.qty} tf={b.tf_minutes}m next={_human_time(b.next_eval_at)} post_fill={_post_fill_label(b.post_fill_action)} clean={b.acquistopulito} status={b.status}")
        lines.append("FUNCTION:")
        for f in self._function_orders:
            if f.status != "active":
                continue
            lines.append(f"{f.order_id} watch={f.symbol} exec={self._exec_symbol(f.symbol, f.hook_symbol)} {f.op} {f.trigger} qty={f.qty} pct={f.percent} tf={f.tf_minutes}m next={_human_time(f.next_eval_at)} post_fill={_post_fill_label(f.post_fill_action)} clean={f.acquistopulito} status={f.status}")
        lines.append("TRAILING SELL:")
        for t in self._trailing_sell_orders:
            if t.status != "active":
                continue
            linked = ""
            if t.oco_parent_order_id is not None and t.oco_leg_index is not None:
                linked = f" linked_oco={t.oco_parent_order_id}/leg{t.oco_leg_index}"
            lines.append(f"{t.order_id} watch={t.symbol} exec={self._exec_symbol(t.symbol, t.hook_symbol)} pct={t.percent} qty={t.qty} limit={t.limit} tf={t.tf_minutes}m next={_human_time(t.next_eval_at)} post_fill={_post_fill_label(t.post_fill_action)}{linked} status={t.status}")
        lines.append("TRAILING BUY:")
        for t in self._trailing_buy_orders:
            if t.status != "active":
                continue
            lines.append(f"{t.order_id} {t.symbol} pct={t.percent} qty={t.qty} limit={t.limit} tf={t.tf_minutes}m next={_human_time(t.next_eval_at)} post_fill={_post_fill_label(t.post_fill_action)} clean={t.acquistopulito} status={t.status}")
        # OCO orders
        lines.append("OCO:")
        for o in getattr(self, "_oco_orders", []):
            if o.status != "active":
                continue
            try:
                legs_text = []
                for l in o.legs:
                    parts = [f"leg{l.get('leg_index')}", l.get('ordertype')]
                    if l.get('price') is not None:
                        parts.append(f"price={l.get('price')}")
                    if l.get('stop_price') is not None:
                        parts.append(f"stop={l.get('stop_price')}")
                    if l.get('trail_percent') is not None:
                        parts.append(f"trail={l.get('trail_percent')}%")
                    parts.append(f"qty={l.get('qty')}")
                    if l.get('core_order_id') is not None:
                        parts.append(f"core={l.get('core_order_id')}")
                    legs_text.append("(" + ", ".join(parts) + ")")
                legs_joined = " ".join(legs_text)
                lines.append(f"{o.order_id} watch={o.symbol} side={o.side} parent={o.parent_order_id} legs={legs_joined} tf={o.tf_minutes}m next={_human_time(o.next_eval_at)} clean={o.acquistopulito} status={o.status}")
            except Exception:
                lines.append(str(o))
        lines.append(f"Timeframe={self._timeframe_seconds}s echo={self._echo_enabled} alert={self._alert_enabled}")
        await self._send(update, "\n".join(lines))

    async def _cmd_c(self, update: Update, parts: List[str]):
        if len(parts) < 2:
            raise ValueError("Formato: /c ORDER_ID oppure /c a")

        target = parts[1]
        if target == "a":
            ids = [s.order_id for s in self._sell_orders + self._buy_orders]
            ids += [s.order_id for s in self._function_orders + self._trailing_sell_orders + self._trailing_buy_orders]
            ids += [s.order_id for s in getattr(self, "_oco_orders", [])]
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

        # OCO orders
        for spec in getattr(self, "_oco_orders", []):
            if spec.order_id == order_id and spec.status == "active":
                spec.status = "cancelled"
                # cancel engine core orders for legs
                for leg in spec.legs:
                    core_id = leg.get("core_order_id")
                    if core_id:
                        try:
                            if leg.get("ordertype") == "trailing":
                                self._cancel_linked_trailing_order(int(core_id))
                            else:
                                self._manager.cancel_order(int(core_id))
                        except Exception:
                            pass
                    try:
                        self._storage.update_oco_leg_status(order_id, leg.get("leg_index"), "cancelled")
                    except Exception:
                        pass
                self._storage.update_order_status(order_id, "cancelled")
                self._storage.append_event("oco_cancelled", order_id)
                return

        raise ValueError("order_id non trovato")

    def _init_trailing_sell(self, spec: TrailingSellSpec):
        price = self._feed.get_price(spec.symbol, spec.tf_minutes)
        spec.max_price = price
        if spec.limit is None:
            spec.armed = True
            spec.arm_op = None
        else:
            spec.arm_op = "<" if price >= spec.limit else ">"

    def _init_trailing_buy(self, spec: TrailingBuySpec):
        price = self._feed.get_price(spec.symbol, spec.tf_minutes)
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

            price = self._feed.get_price(spec.symbol, spec.tf_minutes)
            self._mark_evaluated(spec, now_ts)
            if spec.prev_price is None:
                spec.prev_price = price
                self._storage.update_function_runtime(spec.order_id, spec.bought, spec.prev_price)
                continue

            trigger_hit = (spec.op == "<" and spec.prev_price > spec.trigger and price < spec.trigger)
            trigger_hit = trigger_hit or (spec.op == ">" and spec.prev_price < spec.trigger and price > spec.trigger)
            if spec.acquistopulito and not spec.bought:
                in_trigger_zone = (spec.op == "<" and price < spec.trigger) or (spec.op == ">" and price > spec.trigger)
                trigger_hit = trigger_hit or in_trigger_zone

            if trigger_hit and not spec.bought:
                exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
                if not self._should_execute_clean_entry(
                    order_id=spec.order_id,
                    symbol=spec.symbol,
                    tf_minutes=spec.tf_minutes,
                    side="buy",
                    price=price,
                    acquistopulito=spec.acquistopulito,
                    context="function_buy_trigger",
                ):
                    self._storage.append_event(
                        "clean_entry_blocked",
                        spec.order_id,
                        {"context": "function_buy_trigger", "side": "buy", "price": price},
                    )
                    spec.prev_price = price
                    self._storage.update_function_runtime(spec.order_id, spec.bought, spec.prev_price)
                    continue
                try:
                    exchange_resp = self._execute_market_order_on_exchange("buy", exec_symbol, spec.qty)
                    spec.bought = True
                    spec.status = "filled"
                    self._storage.update_function_runtime(spec.order_id, spec.bought, price)
                    self._storage.update_order_status(spec.order_id, "filled")
                    self._storage.append_event(
                        "function_filled",
                        spec.order_id,
                        {
                            "price": price,
                            "exchange_symbol": exec_symbol,
                            **self._exchange_fields(exchange_resp),
                        },
                    )
                    self._queue_message(
                        spec.chat_id,
                        f"Function BUY scattato su watch={spec.symbol} exec={exec_symbol} qty={spec.qty} a {price} (exchange orderId={exchange_resp.get('orderId')})",
                    )
                    if spec.post_fill_action:
                        self._dispatch_post_fill_action(
                            parent_order_id=spec.order_id,
                            chat_id=spec.chat_id,
                            symbol=spec.symbol,
                            hook_symbol=spec.hook_symbol,
                            side="buy",
                            qty=spec.qty,
                            tf_minutes=spec.tf_minutes,
                            fill_price=price,
                            post_fill_action=spec.post_fill_action,
                        )
                    else:
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
                            post_fill_action=None,
                            status=sell_spec.status,
                        )
                        self._storage.append_event("trailing_sell_created_from_function", sell_spec.order_id)
                except Exception as exc:
                    spec.status = "error"
                    self._handle_exchange_error(
                        order_id=spec.order_id,
                        chat_id=spec.chat_id,
                        event_type="function_exchange_error",
                        user_msg_prefix=f"function buy {exec_symbol}",
                        payload={"price": price, "exchange_symbol": exec_symbol, "qty": spec.qty, "side": "buy"},
                        exc=exc,
                    )

            spec.prev_price = price
            self._storage.update_function_runtime(spec.order_id, spec.bought, spec.prev_price)

    def _eval_trailing_sell(self, now_ts: int):
        to_close: List[TrailingSellSpec] = []
        for spec in self._trailing_sell_orders:
            if spec.status != "active":
                continue
            if not self._is_due(spec, now_ts):
                continue
            price = self._feed.get_price(spec.symbol, spec.tf_minutes)
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
                    exec_symbol = self._exec_symbol(spec.symbol, spec.hook_symbol)
                    try:
                        exchange_resp = self._execute_market_order_on_exchange("sell", exec_symbol, spec.qty)
                        spec.status = "filled"
                        to_close.append(spec)
                        self._queue_message(
                            spec.chat_id,
                            f"Trailing SELL eseguito su watch={spec.symbol} exec={exec_symbol} qty={spec.qty} a {price} (exchange orderId={exchange_resp.get('orderId')})",
                        )
                        self._storage.update_order_status(spec.order_id, "filled")
                        self._storage.append_event(
                            "trailing_sell_filled",
                            spec.order_id,
                            {
                                "price": price,
                                "exchange_symbol": exec_symbol,
                                **self._exchange_fields(exchange_resp),
                            },
                        )
                        if spec.oco_parent_order_id is not None and spec.oco_leg_index is not None:
                            self._storage.append_event(
                                "oco_trailing_leg_fired",
                                int(spec.oco_parent_order_id),
                                {
                                    "leg_index": int(spec.oco_leg_index),
                                    "trailing_order_id": spec.order_id,
                                    "price": price,
                                    "exchange_symbol": exec_symbol,
                                    **self._exchange_fields(exchange_resp),
                                },
                            )
                            linked_oco = None
                            for oco in getattr(self, "_oco_orders", []):
                                if oco.order_id == spec.oco_parent_order_id:
                                    linked_oco = oco
                                    break
                            if linked_oco and linked_oco.status == "active":
                                self._finalize_oco_leg_filled(
                                    linked_oco,
                                    int(spec.oco_leg_index),
                                    price,
                                    exec_symbol,
                                    exchange_resp,
                                )
                    except Exception as exc:
                        spec.status = "error"
                        to_close.append(spec)
                        self._handle_exchange_error(
                            order_id=spec.order_id,
                            chat_id=spec.chat_id,
                            event_type="trailing_sell_exchange_error",
                            user_msg_prefix=f"trailing sell {exec_symbol}",
                            payload={"price": price, "exchange_symbol": exec_symbol, "qty": spec.qty, "side": "sell"},
                            exc=exc,
                        )

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
            price = self._feed.get_price(spec.symbol, spec.tf_minutes)
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
                    if not self._should_execute_clean_entry(
                        order_id=spec.order_id,
                        symbol=spec.symbol,
                        tf_minutes=spec.tf_minutes,
                        side="buy",
                        price=price,
                        acquistopulito=spec.acquistopulito,
                        context="trailing_buy_trigger",
                    ):
                        self._storage.append_event(
                            "clean_entry_blocked",
                            spec.order_id,
                            {"context": "trailing_buy_trigger", "side": "buy", "price": price},
                        )
                        self._storage.update_trailing_runtime(spec.order_id, spec.armed, None, spec.min_price, spec.arm_op)
                        continue
                    try:
                        exchange_resp = self._execute_market_order_on_exchange("buy", spec.symbol, spec.qty)
                        spec.status = "filled"
                        to_close.append(spec)
                        self._queue_message(
                            spec.chat_id,
                            f"Trailing BUY eseguito su {spec.symbol} qty={spec.qty} a {price} (exchange orderId={exchange_resp.get('orderId')})",
                        )
                        self._storage.update_order_status(spec.order_id, "filled")
                        self._storage.append_event(
                            "trailing_buy_filled",
                            spec.order_id,
                            {
                                "price": price,
                                "exchange_symbol": spec.symbol,
                                **self._exchange_fields(exchange_resp),
                            },
                        )
                        self._dispatch_post_fill_action(
                            parent_order_id=spec.order_id,
                            chat_id=spec.chat_id,
                            symbol=spec.symbol,
                            hook_symbol=None,
                            side="buy",
                            qty=spec.qty,
                            tf_minutes=spec.tf_minutes,
                            fill_price=price,
                            post_fill_action=spec.post_fill_action,
                        )
                    except Exception as exc:
                        spec.status = "error"
                        to_close.append(spec)
                        self._handle_exchange_error(
                            order_id=spec.order_id,
                            chat_id=spec.chat_id,
                            event_type="trailing_buy_exchange_error",
                            user_msg_prefix=f"trailing buy {spec.symbol}",
                            payload={"price": price, "exchange_symbol": spec.symbol, "qty": spec.qty, "side": "buy"},
                            exc=exc,
                        )

            self._storage.update_trailing_runtime(spec.order_id, spec.armed, None, spec.min_price, spec.arm_op)

        for spec in to_close:
            self._trailing_buy_orders.remove(spec)

    def _eval_alert(self, chat_id: Optional[int], now: float):
        if not self._alert_enabled or now - self._last_alert_tick < 60:
            return
        self._last_alert_tick = now
        price = self._feed.get_price("BTCUSDT", self._default_tf_minutes)
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
                lines.append(f"{symbol}: {self._feed.get_price(symbol, self._default_tf_minutes)}")
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
        if update.effective_chat and self._is_authorized(update):
            context.application.bot_data["last_chat_id"] = update.effective_chat.id

    def build_application(self) -> Application:
        app = ApplicationBuilder().token(self._token).build()
        app.add_handler(CommandHandler("start", self._start))
        app.add_handler(CommandHandler("info", self._info))
        app.add_handler(CommandHandler("account", self._cmd_account))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/"), self._on_slash_text))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex(r"^/"), self._on_menu_text))
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
    if not raw_chat_id:
        raise RuntimeError("AUTHORIZED_CHAT_ID non impostato: configura il tuo chat id per limitare l'accesso al bot")
    chat_id = int(raw_chat_id)
    db_path = os.getenv("BOT_DB_PATH", "data/bot.sqlite3")
    return TelegramTradingBot(token=token, authorized_chat_id=chat_id, db_path=db_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    build_bot_from_env().run()


