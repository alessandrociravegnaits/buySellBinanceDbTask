"""
Main — bootstrap + definizione ordini
"""

import time
from core import Order, Trigger, Action, OrderBehavior, build_engine
from price_feeds import MockPriceFeed


if __name__ == "__main__":

    feed = MockPriceFeed(initial_price=100.0)
    manager, poller = build_engine(symbols=["BTCUSD"], price_feed=feed)

    # Ordine: vendi se scende sotto 90 OPPURE sale sopra 115
    manager.add_order(Order(
        id=1,
        symbol="BTCUSD",
        triggers=[
            Trigger(id=0, condition=lambda p: p < 90,  description="scende sotto 90"),
            Trigger(id=1, condition=lambda p: p > 115, description="sale sopra 115"),
        ],
        action=Action(
            id=0,
            execute=lambda p: print(f">>> VENDITA eseguita a {p}"),
            description="Vendi BTCUSD"
        ),
        behavior=OrderBehavior.CANCEL_ON_FIRE
    ))

    poller.start()

    # Stato ordini attivi
    print("Ordini attivi:", [o.id for o in manager.list_active()])

    # Simula discesa prezzo
    time.sleep(0.5)
    print("--- Prezzo -> 85 ---")
    feed.set_price(89)
    time.sleep(0.5)

    # Stato finale
    print("Tutti gli ordini:", [(o.id, o.status) for o in manager.list_orders()])

    poller.stop()
