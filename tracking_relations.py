"""Sales Activity links for Tracking's exact-order search, including non-delivery credits."""
import json
import re


def field(row, name):
    key = re.sub(r'[^a-z0-9]', '', name.lower())
    return next((str(value or '').strip() for header, value in row.items()
                 if re.sub(r'[^a-z0-9]', '', header.lower()) == key), '')


def order_number(value):
    value = str(value or '').strip()
    return value[:-2] if re.fullmatch(r'\d+\.0', value) else value


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS tracking_related_orders (
        order_id TEXT PRIMARY KEY, original_order TEXT NOT NULL,
        category TEXT NOT NULL, payload TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS tracking_related_original ON tracking_related_orders(original_order)')


def archive(db, rows):
    from delivery_data import row_to_delivery
    from sales_activity import product_items
    initialize(db)
    grouped = {}
    for row in rows:
        order = order_number(field(row, 'Order no'))
        if order:
            grouped.setdefault(order, []).append(row)
    for order, items in grouped.items():
        originals = {order_number(field(row, 'Original order Number')) for row in items}
        categories = {field(row, 'Order Category').casefold() for row in items}
        db.execute('DELETE FROM tracking_related_orders WHERE order_id=?', (order,))
        if len(originals) != 1 or len(categories) != 1:
            continue
        original, category = next(iter(originals)), next(iter(categories))
        if not re.fullmatch(r'\d+', original) or original == order or category not in {'order', 'credit/refund'}:
            continue
        source = items[0]
        delivery = row_to_delivery({**source, 'Order no': order,
                                   'Delivery method': source.get('Delivery method') or 'Unassigned'})
        if not str(source.get('Delivery method') or '').strip():
            delivery.update(carrier='', deliveryMethodRaw='', st='', statusSource='')
        delivery['items'] = product_items(items)
        delivery['skuItems'] = ', '.join(dict.fromkeys(item['sku'] for item in delivery['items']))
        delivery['grossAmount'] = field(source, 'Gross (base)')
        delivery['relatedKind'] = 'Replacement' if category == 'order' else 'Credit/Refund'
        delivery['originalOrder'] = original
        db.execute('INSERT INTO tracking_related_orders VALUES (?,?,?,?)',
                   (order, original, category, json.dumps(delivery)))


def order_flow(db, order):
    """Return the same complete, directed component for every order in a family."""
    edges = [dict(row) for row in db.execute("""
        WITH RECURSIVE links(parent, child, kind) AS (
            SELECT r.original_order, r.order_id,
                   CASE WHEN r.category='order' THEN 'Replacement' ELSE 'Credit/Refund' END
            FROM tracking_related_orders r
            WHERE EXISTS (SELECT 1 FROM deliveries d WHERE d.order_id=r.original_order)
               OR EXISTS (SELECT 1 FROM tracking_related_orders p WHERE p.order_id=r.original_order)
        ), connected(id) AS (
            SELECT ?
            UNION
            SELECT CASE WHEN links.parent=connected.id THEN links.child ELSE links.parent END
            FROM links JOIN connected ON links.parent=connected.id OR links.child=connected.id
        )
        SELECT parent AS "from", child AS "to", kind FROM links
        WHERE parent IN (SELECT id FROM connected)
        ORDER BY parent, child, kind
    """, (order,))]
    ids = sorted({edge[key] for edge in edges for key in ('from', 'to')})
    fields = ('st', 'carrier', 'statusSource', 'rawStatus', 'palletwaysSheetStatus',
              'palletwaysStatusLabel', 'xdpStatus', 'stopstartStatus',
              'amazonSheetStatus', 'amazonStatus')
    nodes = []
    for row in db.execute("""SELECT n.value AS id, coalesce(d.payload, r.payload) AS payload,
                                  r.category AS category, d.order_id IS NOT NULL AS can_open
        FROM json_each(?) n
        LEFT JOIN deliveries d ON d.order_id=n.value
        LEFT JOIN tracking_related_orders r ON r.order_id=n.value
        ORDER BY n.value""", (json.dumps(ids),)):
        payload = json.loads(row['payload']) if row['payload'] else {}
        nodes.append({'id': row['id'], 'category': row['category'] or 'order',
                      'canOpenDetails': bool(row['can_open']),
                      **{field: payload.get(field, '') for field in fields}})
    return {'nodes': nodes, 'edges': edges}


def lookup(order):
    from delivery_data import connect
    order = str(order or '').strip()
    if not re.fullmatch(r'\d{1,20}', order):
        return None
    with connect() as db:
        initialize(db)
        original = db.execute('SELECT payload FROM deliveries WHERE order_id=?', (order,)).fetchone()
        searched = json.loads(original['payload']) if original else None
        link = db.execute('SELECT original_order, payload FROM tracking_related_orders WHERE order_id=?',
                          (order,)).fetchone()
        if not searched and link:
            searched = json.loads(link['payload'])
            searched['canOpenDetails'] = False
        rows = db.execute('''SELECT r.payload AS source, d.payload AS delivery
            FROM tracking_related_orders r LEFT JOIN deliveries d ON d.order_id=r.order_id
            WHERE r.original_order=? ORDER BY r.order_id''', (order,)).fetchall()
        related = []
        ancestor_link = link
        child_id = order
        visited = {order}
        depth = 0
        while ancestor_link:
            parent_id = ancestor_link['original_order']
            if parent_id in visited:
                break
            visited.add(parent_id)
            parent = db.execute('SELECT payload FROM deliveries WHERE order_id=?', (parent_id,)).fetchone()
            source_parent = None if parent else db.execute(
                'SELECT payload FROM tracking_related_orders WHERE order_id=?', (parent_id,)).fetchone()
            if not parent and not source_parent:
                break
            depth += 1
            delivery = json.loads((parent or source_parent)['payload'])
            kind = 'Original' if depth == 1 else 'Earlier Original'
            delivery.update(relatedKind=kind, canOpenDetails=bool(parent),
                            linkedToOrder=child_id, ancestorDepth=depth)
            related.append(delivery)
            child_id = parent_id
            ancestor_link = db.execute(
                'SELECT original_order FROM tracking_related_orders WHERE order_id=?', (parent_id,)).fetchone()
        # Follow replacement edges breadth first, retaining each direct parent.
        # Ancestors and the searched order cannot reappear through a cycle.
        seen = set(visited)
        pending = [(order, rows, 1)]
        position = 0
        while position < len(pending):
            parent_id, children, replacement_depth = pending[position]
            position += 1
            for row in children:
                source = json.loads(row['source'])
                child_id = source['order']
                if child_id in seen:
                    continue
                seen.add(child_id)
                delivery = json.loads(row['delivery']) if row['delivery'] else source.copy()
                delivery.update({key: source.get(key, '') for key in
                                 ('relatedKind', 'originalOrder', 'grossAmount')})
                delivery.update(canOpenDetails=bool(row['delivery']), linkedToOrder=parent_id)
                if source['relatedKind'] == 'Replacement':
                    delivery.update(relatedKind='Replacement' if replacement_depth == 1 else 'Later Replacement',
                                    replacementDepth=replacement_depth)
                    children = db.execute("""SELECT r.payload AS source, d.payload AS delivery
                        FROM tracking_related_orders r LEFT JOIN deliveries d ON d.order_id=r.order_id
                        WHERE r.original_order=? AND r.category='order' ORDER BY r.order_id""", (child_id,)).fetchall()
                    pending.append((child_id, children, replacement_depth + 1))
                related.append(delivery)
        flow = order_flow(db, order)
        db.commit()
    return {'order': order, 'original': searched, 'parentOrder': link['original_order'] if link else '',
            'related': related, 'flow': flow}


def flow_lookup(order):
    """Dashboard utility: saved family graph only, without provider requests."""
    order = str(order or '').strip()
    if not re.fullmatch(r'\d{1,20}', order):
        raise ValueError('Enter an exact numeric order ID.')
    from delivery_data import connect
    with connect() as db:
        initialize(db)
        found = bool(db.execute("""SELECT 1 FROM deliveries WHERE order_id=?
            UNION ALL SELECT 1 FROM tracking_related_orders WHERE order_id=? LIMIT 1""",
            (order, order)).fetchone())
        flow = order_flow(db, order) if found else {'nodes': [], 'edges': []}
    return {'found': found, 'order': order, 'flow': flow}

