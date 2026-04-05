import os, time, sqlite3
from price_feeds import MockPriceFeed
from telegram_bot import TelegramTradingBot, SimpleOrderSpec
from tests.test_oco_integration import FakeExchangeClient
from core import build_engine


def run():
    tmp = os.getcwd()
    db_path = os.path.join(tmp, 'debug_bot.sqlite3')
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass
    bot = TelegramTradingBot(token='x', authorized_chat_id=None, db_path=db_path)
    bot._exchange_client = FakeExchangeClient()
    mock_feed = MockPriceFeed(initial_price=100.0)
    bot._feed = mock_feed
    bot._manager, bot._poller = build_engine(symbols=['BTCUSDT'], price_feed=mock_feed)

    spec = SimpleOrderSpec(
        order_id=901,
        side='buy',
        symbol='BTCUSDT',
        op='<',
        trigger=100.0,
        qty=1.0,
        chat_id=999,
        tf_minutes=1,
        post_fill_action={
            'type': 'oco',
            'tp': {'mode': 'trailing', 'value': 2.0},
            'sl': {'mode': 'percent', 'value': 1.0},
        }
    )

    bot._on_simple_fired(spec, 100.0)
    time.sleep(0.3)
    print('OCO orders len', len(bot._oco_orders))
    oco = bot._oco_orders[0]
    print('OCO legs:', oco.legs)
    tp_leg = next((l for l in oco.legs if int(l.get('leg_index')) == 1), None)
    sl_leg = next((l for l in oco.legs if int(l.get('leg_index')) == 2), None)
    print('tp_leg core', tp_leg.get('core_order_id'))
    print('sl_leg core', sl_leg.get('core_order_id'))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT core_order_id FROM order_oco_leg WHERE order_id = ? AND leg_index = 2', (oco.order_id,))
    print('DB sl core', cur.fetchone())

    sl_core_id = int(sl_leg.get('core_order_id'))
    core_order = bot._manager.get_order(sl_core_id)
    print('core_order exists', core_order is not None)
    core_order.next_eval_at = 0
    mock_feed.set_price(98.5)
    bot._manager.process_price('BTCUSDT', 98.5, tf_minutes=1)
    time.sleep(0.5)
    linked_trailing_id = int(tp_leg.get('core_order_id'))
    trailing_spec = next((t for t in bot._trailing_sell_orders if t.order_id == linked_trailing_id), None)
    print('linked_trailing_id', linked_trailing_id)
    print('trailing_spec', trailing_spec)
    if trailing_spec:
        print('trailing status', trailing_spec.status)

if __name__ == '__main__':
    run()
