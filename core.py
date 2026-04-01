"""
Trading Engine - Core
"""

import threading
import time
import queue
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict
from enum import Enum
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

POLLING_INTERVAL = 0.1  # secondi


# ── ENUMS ─────────────────────────────────────

class OrderStatus(Enum):
    ACTIVE    = "active"
    STOPPED   = "stopped"
    CANCELLED = "cancelled"

class OrderBehavior(Enum):
    CANCEL_ON_FIRE = "cancel"
    STOP_ON_FIRE   = "stop"
    REPEAT         = "repeat"


# ── PRICE FEED ────────────────────────────────

class PriceFeed(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> float:
        pass


# ── TRIGGER ───────────────────────────────────

@dataclass
class Trigger:
    id: int
    condition: Callable[[float], bool]
    description: str = ""

    def evaluate(self, price: float) -> bool:
        try:
            return self.condition(price)
        except Exception as e:
            log.error(f"Trigger {self.id} errore: {e}")
            return False


# ── ACTION ────────────────────────────────────

@dataclass
class Action:
    id: int
    execute: Callable[[float], None]
    description: str = ""

    def run(self, price: float):
        try:
            self.execute(price)
            log.info(f"Action {self.id} '{self.description}' eseguita a {price}")
        except Exception as e:
            log.error(f"Action {self.id} errore: {e}")


# ── ORDER ─────────────────────────────────────

@dataclass
class Order:
    id: int
    symbol: str
    triggers: List[Trigger]
    action: Action
    behavior: OrderBehavior = OrderBehavior.CANCEL_ON_FIRE
    tf_minutes: int = 15
    next_eval_at: Optional[float] = None
    last_eval_at: Optional[float] = None
    status: OrderStatus = OrderStatus.ACTIVE
    fired_trigger_id: Optional[int] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset(self):  #repeat
        self.fired_trigger_id = None
        self.status = OrderStatus.ACTIVE

    def schedule_next_boundary(self, now_ts: Optional[float] = None):
        now = now_ts if now_ts is not None else time.time()
        tf_seconds = max(60, int(self.tf_minutes) * 60)
        # Boundary UTC strict: ordine valutato solo alla chiusura candela successiva.
        self.next_eval_at = float((int(now) // tf_seconds + 1) * tf_seconds)

    def is_due(self, now_ts: Optional[float] = None) -> bool:
        now = now_ts if now_ts is not None else time.time()
        if self.next_eval_at is None:
            self.schedule_next_boundary(now)
            return False
        return now >= self.next_eval_at

    def stop(self):
        with self._lock:
            self.status = OrderStatus.STOPPED

    def cancel(self):  #stop+cancel
        with self._lock:
            self.status = OrderStatus.CANCELLED

    def resume(self):
        with self._lock:
            if self.status == OrderStatus.STOPPED:
                self.status = OrderStatus.ACTIVE


# ── EXECUTION QUEUE ───────────────────────────

class ExecutionQueue:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def push(self, order: Order, price: float):
        self._queue.put((order, price))

    def _worker(self):
        while True:
            order, price = self._queue.get()
            order.action.run(price)
            self._queue.task_done()


# ── EVENT BUS ─────────────────────────────────

class EventBus:
    def __init__(self):
        self._subscribers: Dict[int, Order] = {}
        self._lock = threading.Lock()

    def subscribe(self, order: Order):
        with self._lock:
            self._subscribers[order.id] = order

    def unsubscribe(self, order_id: int):
        with self._lock:
            self._subscribers.pop(order_id, None)

    def get_active(self, symbol: str) -> List[Order]:
        with self._lock:
            return [
                o for o in self._subscribers.values()
                if o.symbol == symbol and o.status == OrderStatus.ACTIVE
            ]


# ── ORDER MANAGER ─────────────────────────────

class OrderManager:
    def __init__(self, exec_queue: ExecutionQueue, event_bus: EventBus):
        self._exec_queue = exec_queue
        self._event_bus  = event_bus
        self._orders: Dict[int, Order] = {}
        self._lock = threading.Lock()

    # -- registro centrale --

    def add_order(self, order: Order) -> int:
        with self._lock:
            if order.next_eval_at is None:
                order.schedule_next_boundary()
            self._orders[order.id] = order
        self._event_bus.subscribe(order)
        log.info(f"Ordine {order.id} '{order.action.description}' aggiunto [{order.symbol}]")
        return order.id

    def remove_order(self, order_id: int):
        with self._lock:
            self._orders.pop(order_id, None)
        self._event_bus.unsubscribe(order_id)

    def get_order(self, order_id: int) -> Optional[Order]:
        return self._orders.get(order_id)

    def list_orders(self) -> List[Order]:
        """Registro completo di tutti gli ordini (attivi, fermi, cancellati)."""
        with self._lock:
            return list(self._orders.values())

    def list_active(self) -> List[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.status == OrderStatus.ACTIVE]

    # -- comandi manuali --

    def stop_order(self, order_id: int):
        if o := self.get_order(order_id): o.stop()

    def cancel_order(self, order_id: int):
        if o := self.get_order(order_id):
            o.cancel()
            self._event_bus.unsubscribe(order_id)

    def resume_order(self, order_id: int):
        if o := self.get_order(order_id):
            o.resume()
            self._event_bus.subscribe(o)

    # -- valutazione trigger --

    def process_price(self, symbol: str, price: float):
        for order in self._event_bus.get_active(symbol):
            self._evaluate_order(order, price)

    def _evaluate_order(self, order: Order, price: float):
        fired_trigger = None
        now_ts = time.time()
        with order._lock:
            if order.status != OrderStatus.ACTIVE:
                return
            if not order.is_due(now_ts):
                return
            order.last_eval_at = now_ts
            order.schedule_next_boundary(now_ts)
            for trigger in order.triggers:
                if trigger.evaluate(price):
                    order.fired_trigger_id = trigger.id
                    fired_trigger = trigger
                    self._exec_queue.push(order, price)
                    self._apply_behavior(order)
                    break

        if fired_trigger:
            log.info(f"Ordine {order.id} — Trigger {fired_trigger.id} '{fired_trigger.description}' scattato a {price}")
            if order.status == OrderStatus.CANCELLED:
                self._event_bus.unsubscribe(order.id)

    def _apply_behavior(self, order: Order):
        """Chiamato dentro order._lock."""
        if order.behavior == OrderBehavior.CANCEL_ON_FIRE:
            order.status = OrderStatus.CANCELLED
        elif order.behavior == OrderBehavior.STOP_ON_FIRE:
            order.status = OrderStatus.STOPPED
        elif order.behavior == OrderBehavior.REPEAT:
            order.reset()


# ── PRICE POLLER ──────────────────────────────

class PricePoller:
    """Thread unico centralizzato — polling su tutti i simboli."""

    def __init__(self, price_feed: PriceFeed, order_manager: OrderManager, symbols: List[str]):
        self._feed    = price_feed
        self._om      = order_manager
        self._symbols = list(symbols)
        self._symbols_lock = threading.Lock()
        self._running = False
        self._thread  = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._running = True
        self._thread.start()
        log.info("PricePoller avviato")

    def stop(self):
        self._running = False
        log.info("PricePoller fermato")

    def add_symbol(self, symbol: str):
        """Registra un nuovo simbolo da includere nel polling centralizzato."""
        normalized = symbol.upper()
        with self._symbols_lock:
            if normalized not in self._symbols:
                self._symbols.append(normalized)

    def _loop(self):
        while self._running:
            with self._symbols_lock:
                symbols_snapshot = list(self._symbols)
            for symbol in symbols_snapshot:
                try:
                    price = self._feed.get_price(symbol)
                    self._om.process_price(symbol, price)
                except Exception as e:
                    log.error(f"Errore price feed {symbol}: {e}")
            time.sleep(POLLING_INTERVAL)


# ── FACTORY ───────────────────────────────────

def build_engine(symbols: List[str], price_feed: PriceFeed):
    exec_queue = ExecutionQueue()
    event_bus  = EventBus()
    order_mgr  = OrderManager(exec_queue, event_bus)
    poller     = PricePoller(price_feed, order_mgr, symbols)
    return order_mgr, poller
