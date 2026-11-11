"""Persistent local order exclusions that survive source-sheet synchronization."""
import re
from datetime import datetime, timezone


ORDER_TABLES = (
    'deliveries', 'activity', 'sales_activity_orders', 'tracking_related_orders',
    'routine_live_overrides', 'routine_live_bookings', 'aliases', 'entries',
)


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS excluded_orders (
        order_id TEXT PRIMARY KEY, excluded_at TEXT NOT NULL)''')
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in ORDER_TABLES:
        if table not in tables:
            continue
        for operation in ('INSERT', 'UPDATE'):
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS exclude_order_{table}_{operation.lower()}
                BEFORE {operation} ON {table}
                WHEN EXISTS (SELECT 1 FROM excluded_orders WHERE order_id=NEW.order_id)
                BEGIN SELECT RAISE(IGNORE); END''')


def exclude(db, orders):
    orders = tuple(dict.fromkeys(str(order).strip() for order in orders))
    if not orders or any(not re.fullmatch(r'\d{1,20}', order) for order in orders):
        raise ValueError('Use exact numeric order IDs.')
    install(db)
    now = datetime.now(timezone.utc).isoformat()
    db.executemany('INSERT OR IGNORE INTO excluded_orders VALUES (?, ?)', [(order, now) for order in orders])
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    deleted = {}
    for table in ORDER_TABLES:
        if table in tables:
            deleted[table] = sum(db.execute(f'DELETE FROM {table} WHERE order_id=?', (order,)).rowcount for order in orders)
    # The next app refresh should rebuild summary counts from the remaining records.
    if 'sync_metadata' in tables:
        db.execute("DELETE FROM sync_metadata WHERE key='latest'")
    return deleted
