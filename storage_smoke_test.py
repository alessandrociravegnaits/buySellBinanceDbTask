"""Smoke test rapido per storage SQLite."""

import os
from storage import SQLiteStorage


def main():
    db_path = "data/test_bot.sqlite3"
    archive_dir = "data/archive"

    if os.path.exists(db_path):
        os.remove(db_path)

    storage = SQLiteStorage(db_path=db_path, archive_dir=archive_dir)

    order_id = storage.next_order_id()
    storage.save_simple_order(
        order_id=order_id,
        chat_id=1,
        side="sell",
        symbol="BTCUSDT",
        op="<",
        trigger_value=30000.0,
        qty=0.01,
        hook_symbol=None,
        core_order_id=order_id,
        tf_minutes=15,
        next_eval_at=0,
        last_eval_at=None,
    )
    storage.append_event("simple_created", order_id, {"symbol": "BTCUSDT"})

    active = storage.load_active_orders()
    assert len(active["simple"]) == 1

    storage.update_order_status(order_id, "filled")
    storage.append_event("simple_filled", order_id, {"price": 29999.5})
    storage.archive_closed_orders_by_month()

    storage.close()
    print("storage smoke test: OK")


if __name__ == "__main__":
    main()

