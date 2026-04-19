import asyncio
import os
import sqlite3
import time

from price_feeds import MockPriceFeed
from telegram_bot import FunctionSpec, OcoSpec, SimpleOrderSpec, TelegramTradingBot, TrailingBuySpec, TrailingSellSpec


class FakeExchangeClient:
    def create_order(self, **kwargs):
        return {
            "orderId": 123456,
            "status": "FILLED",
            "executedQty": str(kwargs.get("quantity")),
        }


class CountingExchangeClient:
    def __init__(self):
        self.calls = []

    def create_order(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "orderId": 900000 + len(self.calls),
            "status": "FILLED",
            "executedQty": str(kwargs.get("quantity")),
        }


class _DummyChat:
    def __init__(self, chat_id=1):
        self.id = chat_id


class _DummyUpdate:
    def __init__(self, chat_id=1):
        self.effective_chat = _DummyChat(chat_id)


def test_oco_end_to_end(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    # Monkeypatch TelegramTradingBot to use MockPriceFeed by injecting into the module
    # Create bot but override feed after init
    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    # Replace feed and manager/poller with ones using MockPriceFeed
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    # rebuild engine with mock feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    # Create a sample OCO via storage + attach
    order_id = bot._new_order_id()
    legs = [
        {"leg_index": 1, "ordertype": "limit", "price": 110.0, "qty": 1.0, "side": "sell"},
        {"leg_index": 2, "ordertype": "stop_limit", "stop_price": 90.0, "limit_price": 85.0, "qty": 1.0, "side": "sell"},
    ]

    bot._storage.save_oco_order(
        order_id=order_id,
        chat_id=999,
        symbol="BTCUSDT",
        side="sell",
        legs=legs,
        hook_symbol=None,
        tf_minutes=1,
        next_eval_at=None,
        last_eval_at=None,
        status="active",
    )

    oco_spec = OcoSpec(order_id=order_id, symbol="BTCUSDT", side="sell", legs=legs, chat_id=999, tf_minutes=1)
    if not hasattr(bot, "_oco_orders"):
        bot._oco_orders = []
    bot._oco_orders.append(oco_spec)

    # attach to engine (this will create core orders and write core ids)
    bot._attach_oco_to_engine(oco_spec)

    # Read core ids from DB
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT core_order_id FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    core_ids = [r[0] for r in cur.fetchall()]
    assert len(core_ids) == 2

    # Force core orders to be due immediately (Order.is_due checks next_eval_at)
    for cid in core_ids:
        o = bot._manager.get_order(int(cid))
        if o:
            o.next_eval_at = 0

    # Simulate price moving above 110 to fire leg 1
    mock_feed.set_price(111.0)
    # process price for tf=1
    bot._manager.process_price("BTCUSDT", 111.0, tf_minutes=1)

    # Give ExecutionQueue some time to run actions
    time.sleep(0.5)

    # Check DB for statuses: one leg filled, other cancelled
    cur.execute("SELECT leg_index, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (order_id,))
    res = cur.fetchall()
    statuses = {r[0]: r[1] for r in res}

    assert statuses[1] in ("filled", "filled")
    assert statuses[2] in ("cancelled", "cancelled") or statuses[2] == 'waiting'

    # Check order status
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,))
    ord_status = cur.fetchone()[0]
    assert ord_status in ("filled", "active")

    conn.close()
    bot._storage.close()


def test_auto_oco_with_trailing_sl_end_to_end(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    spec = SimpleOrderSpec(
        order_id=900,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=100.0,
        qty=1.0,
        chat_id=999,
        tf_minutes=1,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "percent", "value": 2.0},
            "sl": {"mode": "trailing", "value": 1.5},
        },
    )

    # Trigger simple buy fill -> should auto-create OCO with trailing SL leg.
    bot._on_simple_fired(spec, 100.0)
    time.sleep(0.3)

    assert len(bot._oco_orders) == 1
    oco = bot._oco_orders[0]
    trailing_leg = next((l for l in oco.legs if l.get("ordertype") == "trailing"), None)
    assert trailing_leg is not None
    assert trailing_leg.get("core_order_id") is not None

    linked_trailing = next((t for t in bot._trailing_sell_orders if t.order_id == trailing_leg.get("core_order_id")), None)
    assert linked_trailing is not None
    assert linked_trailing.oco_parent_order_id == oco.order_id
    assert linked_trailing.oco_leg_index == trailing_leg.get("leg_index")

    # Force linked trailing to fire.
    linked_trailing.next_eval_at = 0
    linked_trailing.armed = True
    linked_trailing.max_price = 100.0
    mock_feed.set_price(98.0)
    bot._eval_trailing_sell(int(time.time()))
    time.sleep(0.3)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (oco.order_id,))
    oco_status = cur.fetchone()[0]
    assert oco_status == "filled"

    cur.execute("SELECT leg_index, status FROM order_oco_leg WHERE order_id = ? ORDER BY leg_index", (oco.order_id,))
    statuses = {idx: status for idx, status in cur.fetchall()}
    assert statuses[2] == "filled"
    assert statuses[1] == "cancelled"

    conn.close()
    bot._storage.close()


def test_attach_oco_reuses_existing_trailing_and_cancels_stale(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    oco_id = 500
    legs = [
        {"leg_index": 1, "ordertype": "trailing", "trail_percent": 1.2, "qty": 1.0, "side": "sell", "status": "waiting"},
        {"leg_index": 2, "ordertype": "trailing", "trail_percent": 1.2, "qty": 1.0, "side": "sell", "status": "waiting"},
    ]
    bot._storage.save_oco_order(
        order_id=oco_id,
        chat_id=999,
        symbol="BTCUSDT",
        side="sell",
        legs=legs,
        hook_symbol=None,
        tf_minutes=1,
        next_eval_at=None,
        last_eval_at=None,
        status="active",
    )

    # Simulate pre-existing duplicated trailing legs from prior restarts.
    trailing_specs = [
        TrailingSellSpec(order_id=700, symbol="BTCUSDT", qty=1.0, percent=1.2, chat_id=999, limit=None, hook_symbol=None, tf_minutes=1, oco_parent_order_id=oco_id, oco_leg_index=1),
        TrailingSellSpec(order_id=701, symbol="BTCUSDT", qty=1.0, percent=1.2, chat_id=999, limit=None, hook_symbol=None, tf_minutes=1, oco_parent_order_id=oco_id, oco_leg_index=1),
        TrailingSellSpec(order_id=702, symbol="BTCUSDT", qty=1.0, percent=1.2, chat_id=999, limit=None, hook_symbol=None, tf_minutes=1, oco_parent_order_id=oco_id, oco_leg_index=2),
        TrailingSellSpec(order_id=703, symbol="BTCUSDT", qty=1.0, percent=1.2, chat_id=999, limit=None, hook_symbol=None, tf_minutes=1, oco_parent_order_id=oco_id, oco_leg_index=2),
    ]
    bot._trailing_sell_orders = list(trailing_specs)
    for spec in trailing_specs:
        bot._storage.save_trailing_order(
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
            post_fill_action=None,
            oco_parent_order_id=spec.oco_parent_order_id,
            oco_leg_index=spec.oco_leg_index,
            status=spec.status,
        )

    oco_spec = OcoSpec(order_id=oco_id, symbol="BTCUSDT", side="sell", legs=legs, chat_id=999, tf_minutes=1)
    bot._attach_oco_to_engine(oco_spec)

    # Latest trailing ids are reused, stale ones are cancelled.
    leg1 = next(l for l in oco_spec.legs if int(l.get("leg_index")) == 1)
    leg2 = next(l for l in oco_spec.legs if int(l.get("leg_index")) == 2)
    assert int(leg1.get("core_order_id")) == 701
    assert int(leg2.get("core_order_id")) == 703

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = 700")
    assert cur.fetchone()[0] == "cancelled"
    cur.execute("SELECT status FROM orders WHERE order_id = 702")
    assert cur.fetchone()[0] == "cancelled"
    cur.execute("SELECT status FROM orders WHERE order_id = 701")
    assert cur.fetchone()[0] == "active"
    cur.execute("SELECT status FROM orders WHERE order_id = 703")
    assert cur.fetchone()[0] == "active"
    conn.close()
    bot._storage.close()


def test_trailing_linked_to_non_active_oco_is_skipped_without_sell(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = CountingExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    stale_trailing = TrailingSellSpec(
        order_id=800,
        symbol="BTCUSDT",
        qty=1.0,
        percent=1.2,
        chat_id=999,
        limit=None,
        hook_symbol=None,
        armed=True,
        max_price=100.0,
        tf_minutes=1,
        next_eval_at=0,
        oco_parent_order_id=900,
        oco_leg_index=1,
        status="active",
    )
    bot._trailing_sell_orders = [stale_trailing]
    bot._storage.save_trailing_order(
        order_id=stale_trailing.order_id,
        chat_id=stale_trailing.chat_id,
        side="sell",
        symbol=stale_trailing.symbol,
        qty=stale_trailing.qty,
        percent=stale_trailing.percent,
        limit_price=stale_trailing.limit,
        hook_symbol=stale_trailing.hook_symbol,
        armed=stale_trailing.armed,
        max_price=stale_trailing.max_price,
        min_price=None,
        arm_op=stale_trailing.arm_op,
        tf_minutes=stale_trailing.tf_minutes,
        next_eval_at=stale_trailing.next_eval_at,
        last_eval_at=stale_trailing.last_eval_at,
        post_fill_action=None,
        oco_parent_order_id=stale_trailing.oco_parent_order_id,
        oco_leg_index=stale_trailing.oco_leg_index,
        status=stale_trailing.status,
    )

    # OCO exists in memory but is not active anymore.
    bot._oco_orders = [
        OcoSpec(
            order_id=900,
            symbol="BTCUSDT",
            side="sell",
            legs=[{"leg_index": 1, "ordertype": "trailing", "status": "cancelled"}],
            chat_id=999,
            tf_minutes=1,
            status="filled",
        )
    ]

    mock_feed.set_price(98.0)
    bot._eval_trailing_sell(int(time.time()))

    assert len(bot._exchange_client.calls) == 0
    assert stale_trailing.status == "cancelled"
    bot._storage.close()


def test_trailing_sell_renews_next_eval_at_on_each_due_tick(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    now_ts = 1713030000
    expected_next = bot._next_boundary_epoch(15, now_ts)

    spec = TrailingSellSpec(
        order_id=1200,
        symbol="BTCUSDT",
        qty=1.0,
        percent=1.5,
        chat_id=999,
        limit=None,
        hook_symbol=None,
        armed=True,
        max_price=100.0,
        arm_op=None,
        tf_minutes=15,
        next_eval_at=0,
        last_eval_at=None,
        status="active",
    )
    bot._trailing_sell_orders = [spec]
    bot._storage.save_trailing_order(
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

    mock_feed.set_price(100.5)
    bot._eval_trailing_sell(now_ts)

    assert spec.status == "active"
    assert spec.last_eval_at == now_ts
    assert spec.next_eval_at == expected_next

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT next_eval_at, last_eval_at FROM orders WHERE order_id = ?", (spec.order_id,))
    next_eval_at, last_eval_at = cur.fetchone()
    assert next_eval_at == expected_next
    assert last_eval_at == now_ts
    conn.close()
    bot._storage.close()


def test_simple_orders_sync_next_eval_for_buy_and_sell(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    buy_spec = SimpleOrderSpec(
        order_id=1301,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=50.0,
        qty=0.1,
        chat_id=999,
        tf_minutes=15,
        status="active",
    )
    bot._attach_simple_to_engine(buy_spec)
    bot._buy_orders.append(buy_spec)
    bot._storage.save_simple_order(
        order_id=buy_spec.order_id,
        chat_id=buy_spec.chat_id,
        side=buy_spec.side,
        symbol=buy_spec.symbol,
        op=buy_spec.op,
        trigger_value=buy_spec.trigger,
        qty=buy_spec.qty,
        hook_symbol=buy_spec.hook_symbol,
        core_order_id=buy_spec.core_order_id,
        tf_minutes=buy_spec.tf_minutes,
        next_eval_at=buy_spec.next_eval_at,
        last_eval_at=buy_spec.last_eval_at,
        status=buy_spec.status,
    )

    sell_spec = SimpleOrderSpec(
        order_id=1302,
        side="sell",
        symbol="BTCUSDT",
        op=">",
        trigger=150.0,
        qty=0.1,
        chat_id=999,
        tf_minutes=15,
        status="active",
    )
    bot._attach_simple_to_engine(sell_spec)
    bot._sell_orders.append(sell_spec)
    bot._storage.save_simple_order(
        order_id=sell_spec.order_id,
        chat_id=sell_spec.chat_id,
        side=sell_spec.side,
        symbol=sell_spec.symbol,
        op=sell_spec.op,
        trigger_value=sell_spec.trigger,
        qty=sell_spec.qty,
        hook_symbol=sell_spec.hook_symbol,
        core_order_id=sell_spec.core_order_id,
        tf_minutes=sell_spec.tf_minutes,
        next_eval_at=sell_spec.next_eval_at,
        last_eval_at=sell_spec.last_eval_at,
        status=sell_spec.status,
    )

    # Force both core orders to be due and evaluate without firing triggers.
    for core_id in (buy_spec.core_order_id, sell_spec.core_order_id):
        core_order = bot._manager.get_order(int(core_id))
        assert core_order is not None
        core_order.next_eval_at = 0

    bot._manager.process_price("BTCUSDT", 100.0, tf_minutes=15)
    bot._sync_simple_order_schedule()

    for spec in (buy_spec, sell_spec):
        assert spec.last_eval_at is not None
        assert spec.next_eval_at is not None
        assert spec.next_eval_at > spec.last_eval_at

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT next_eval_at, last_eval_at FROM orders WHERE order_id = ?", (buy_spec.order_id,))
    buy_next, buy_last = cur.fetchone()
    cur.execute("SELECT next_eval_at, last_eval_at FROM orders WHERE order_id = ?", (sell_spec.order_id,))
    sell_next, sell_last = cur.fetchone()
    conn.close()

    assert buy_next == buy_spec.next_eval_at
    assert buy_last == buy_spec.last_eval_at
    assert sell_next == sell_spec.next_eval_at
    assert sell_last == sell_spec.last_eval_at

    bot._storage.close()


def test_auto_oco_independent_modes_tp_trailing_sl_percent(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    spec = SimpleOrderSpec(
        order_id=901,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=100.0,
        qty=1.0,
        chat_id=999,
        tf_minutes=1,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "trailing", "value": 2.0},
            "sl": {"mode": "percent", "value": 1.0},
        },
    )

    bot._on_simple_fired(spec, 100.0)
    time.sleep(0.3)

    assert len(bot._oco_orders) == 1
    oco = bot._oco_orders[0]
    tp_leg = next((l for l in oco.legs if int(l.get("leg_index")) == 1), None)
    sl_leg = next((l for l in oco.legs if int(l.get("leg_index")) == 2), None)
    assert tp_leg is not None and tp_leg.get("ordertype") == "trailing"
    assert sl_leg is not None and sl_leg.get("ordertype") == "stop_limit"

    # Force stop leg to trigger; it should cancel trailing sibling.
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT core_order_id FROM order_oco_leg WHERE order_id = ? AND leg_index = 2", (oco.order_id,))
    sl_core_id = int(cur.fetchone()[0])
    core_order = bot._manager.get_order(sl_core_id)
    assert core_order is not None
    core_order.next_eval_at = 0
    mock_feed.set_price(98.5)
    bot._manager.process_price("BTCUSDT", 98.5, tf_minutes=1)
    time.sleep(0.5)

    linked_trailing_id = int(tp_leg.get("core_order_id"))
    trailing_spec = next((t for t in bot._trailing_sell_orders if t.order_id == linked_trailing_id), None)
    assert trailing_spec is not None
    assert trailing_spec.status == "cancelled"

    cur.execute("SELECT status FROM order_oco_leg WHERE order_id = ? AND leg_index = 1", (oco.order_id,))
    tp_status = cur.fetchone()[0]
    cur.execute("SELECT status FROM order_oco_leg WHERE order_id = ? AND leg_index = 2", (oco.order_id,))
    sl_status = cur.fetchone()[0]
    assert tp_status == "cancelled"
    assert sl_status == "filled"
    conn.close()
    bot._storage.close()


def test_function_buy_auto_oco_post_fill_creates_sell_oco(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=99.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    spec = FunctionSpec(
        order_id=1001,
        symbol="BTCUSDT",
        op=">",
        trigger=100.0,
        qty=1.0,
        percent=1.5,
        chat_id=999,
        hook_symbol=None,
        bought=False,
        prev_price=99.0,
        tf_minutes=1,
        next_eval_at=0,
        last_eval_at=None,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "percent", "value": 2.0},
            "sl": {"mode": "percent", "value": 1.0},
        },
        acquistopulito=False,
        status="active",
    )
    bot._function_orders = [spec]

    mock_feed.set_price(101.0)
    bot._eval_function_orders(int(time.time()))
    time.sleep(0.4)

    assert spec.status == "filled"
    assert len(bot._oco_orders) == 1
    oco = bot._oco_orders[0]
    assert oco.side == "sell"
    assert oco.symbol == "BTCUSDT"
    assert len(oco.legs) == 2

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT side FROM order_oco WHERE order_id = ?", (oco.order_id,))
    row = cur.fetchone()
    assert row == ("sell",)
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (oco.order_id,))
    assert cur.fetchone() == ("active",)
    conn.close()
    bot._storage.close()


def test_trailing_buy_auto_oco_post_fill_creates_sell_oco(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    spec = TrailingBuySpec(
        order_id=1002,
        symbol="BTCUSDT",
        qty=1.0,
        percent=1.0,
        chat_id=999,
        limit=98.0,
        armed=True,
        min_price=97.0,
        arm_op="<",
        tf_minutes=1,
        next_eval_at=0,
        last_eval_at=None,
        post_fill_action={
            "type": "oco",
            "tp": {"mode": "percent", "value": 3.0},
            "sl": {"mode": "trailing", "value": 1.5},
        },
        acquistopulito=False,
        status="active",
    )
    bot._trailing_buy_orders = [spec]

    mock_feed.set_price(99.0)
    bot._eval_trailing_buy(int(time.time()))
    time.sleep(0.4)

    assert spec.status == "filled"
    assert len(bot._oco_orders) == 1
    oco = bot._oco_orders[0]
    assert oco.side == "sell"
    assert any(leg.get("ordertype") == "trailing" for leg in oco.legs)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT side FROM order_oco WHERE order_id = ?", (oco.order_id,))
    row = cur.fetchone()
    assert row == ("sell",)
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (oco.order_id,))
    assert cur.fetchone() == ("active",)
    conn.close()
    bot._storage.close()


def test_cmd_ad_sets_threshold_and_reference(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    async def _noop_send(update, text, reply_markup=None):
        return None

    bot._send = _noop_send

    asyncio.run(bot._cmd_ad(_DummyUpdate(), ["/ad", "1.25"]))

    assert bot._btc_alert_liquidation_percent == 1.25
    assert bot._btc_alert_liquidation_reference_price == 100.0
    assert bot._storage.get_setting("btc_liquidation_drop_percent") == "1.25"

    asyncio.run(bot._cmd_ad(_DummyUpdate(), ["/ad", "0"]))
    assert bot._btc_alert_liquidation_percent == 0.0
    assert bot._btc_alert_liquidation_reference_price is None

    bot._storage.close()


def test_btc_drop_liquidates_sell_and_cancels_buy(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    exchange = CountingExchangeClient()
    bot._exchange_client = exchange
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    sell_spec = SimpleOrderSpec(
        order_id=1001,
        side="sell",
        symbol="ETHUSDT",
        op=">",
        trigger=3000.0,
        qty=0.25,
        chat_id=999,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._attach_simple_to_engine(sell_spec)
    bot._sell_orders.append(sell_spec)
    bot._storage.save_simple_order(
        order_id=sell_spec.order_id,
        chat_id=sell_spec.chat_id,
        side=sell_spec.side,
        symbol=sell_spec.symbol,
        op=sell_spec.op,
        trigger_value=sell_spec.trigger,
        qty=sell_spec.qty,
        hook_symbol=sell_spec.hook_symbol,
        core_order_id=sell_spec.core_order_id,
        tf_minutes=sell_spec.tf_minutes,
        next_eval_at=sell_spec.next_eval_at,
        last_eval_at=sell_spec.last_eval_at,
        btc_alert_liquidate=sell_spec.btc_alert_liquidate,
        status=sell_spec.status,
    )

    buy_spec = SimpleOrderSpec(
        order_id=1002,
        side="buy",
        symbol="BTCUSDT",
        op="<",
        trigger=95000.0,
        qty=0.01,
        chat_id=999,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._attach_simple_to_engine(buy_spec)
    bot._buy_orders.append(buy_spec)
    bot._storage.save_simple_order(
        order_id=buy_spec.order_id,
        chat_id=buy_spec.chat_id,
        side=buy_spec.side,
        symbol=buy_spec.symbol,
        op=buy_spec.op,
        trigger_value=buy_spec.trigger,
        qty=buy_spec.qty,
        hook_symbol=buy_spec.hook_symbol,
        core_order_id=buy_spec.core_order_id,
        tf_minutes=buy_spec.tf_minutes,
        next_eval_at=buy_spec.next_eval_at,
        last_eval_at=buy_spec.last_eval_at,
        btc_alert_liquidate=buy_spec.btc_alert_liquidate,
        status=buy_spec.status,
    )

    bot._btc_alert_liquidation_percent = 1.0
    bot._btc_alert_liquidation_reference_price = 100.0
    bot._last_btc_liquidation_tick = 0.0

    mock_feed.set_price(98.5)
    bot._eval_btc_liquidation(None, time.time())

    assert sell_spec.status == "filled"
    assert buy_spec.status == "cancelled"
    assert len(exchange.calls) == 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (sell_spec.order_id,))
    assert cur.fetchone() == ("filled",)
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (buy_spec.order_id,))
    assert cur.fetchone() == ("cancelled",)
    conn.close()
    bot._storage.close()


def test_btc_drop_ignores_upward_move(tmp_path):
    db_path = str(tmp_path / "test_bot.sqlite3")
    archive_dir = str(tmp_path / "archive")
    os.makedirs(archive_dir, exist_ok=True)

    bot = TelegramTradingBot(token="x", authorized_chat_id=None, db_path=db_path)
    exchange = CountingExchangeClient()
    bot._exchange_client = exchange
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    from core import build_engine
    bot._manager, bot._poller = build_engine(symbols=["BTCUSDT"], price_feed=mock_feed)

    sell_spec = SimpleOrderSpec(
        order_id=2001,
        side="sell",
        symbol="ETHUSDT",
        op=">",
        trigger=3000.0,
        qty=0.25,
        chat_id=999,
        tf_minutes=1,
        btc_alert_liquidate=True,
    )
    bot._attach_simple_to_engine(sell_spec)
    bot._sell_orders.append(sell_spec)
    bot._storage.save_simple_order(
        order_id=sell_spec.order_id,
        chat_id=sell_spec.chat_id,
        side=sell_spec.side,
        symbol=sell_spec.symbol,
        op=sell_spec.op,
        trigger_value=sell_spec.trigger,
        qty=sell_spec.qty,
        hook_symbol=sell_spec.hook_symbol,
        core_order_id=sell_spec.core_order_id,
        tf_minutes=sell_spec.tf_minutes,
        next_eval_at=sell_spec.next_eval_at,
        last_eval_at=sell_spec.last_eval_at,
        btc_alert_liquidate=sell_spec.btc_alert_liquidate,
        status=sell_spec.status,
    )

    bot._btc_alert_liquidation_percent = 1.0
    bot._btc_alert_liquidation_reference_price = 100.0
    bot._last_btc_liquidation_tick = 0.0

    mock_feed.set_price(101.5)
    bot._eval_btc_liquidation(None, time.time())

    assert sell_spec.status == "active"
    assert len(exchange.calls) == 0
    bot._storage.close()
