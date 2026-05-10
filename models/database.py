import os
import asyncio
from contextlib import asynccontextmanager

TURSO_URL = os.getenv("TURSO_DB_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
LOCAL_DB = os.getenv("DB_PATH", "supercrm.db")

_use_turso = bool(TURSO_URL and TURSO_TOKEN)


def _make_connection():
    if _use_turso:
        import libsql_experimental as libsql
        return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    else:
        import sqlite3
        return sqlite3.connect(LOCAL_DB)


class Row(dict):
    """dict-підклас що підтримує row["key"] і row.key"""
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


class AsyncCursor:
    def __init__(self, cursor):
        self._cur = cursor

    def _to_rows(self, raw_rows):
        if self._cur.description is None:
            return raw_rows or []
        cols = [d[0] for d in self._cur.description]
        return [Row(zip(cols, r)) for r in (raw_rows or [])]

    async def fetchall(self):
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, self._cur.fetchall)
        return self._to_rows(rows)

    async def fetchone(self):
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(None, self._cur.fetchone)
        if row is None:
            return None
        if self._cur.description is None:
            return row
        cols = [d[0] for d in self._cur.description]
        return Row(zip(cols, row))

    @property
    def lastrowid(self):
        return self._cur.lastrowid


class AsyncDB:
    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None  # сумісність зі старим кодом (ігнорується)

    async def execute(self, sql, params=()):
        loop = asyncio.get_event_loop()
        cur = await loop.run_in_executor(
            None, lambda: self._conn.execute(sql, tuple(params))
        )
        return AsyncCursor(cur)

    async def executemany(self, sql, params_list):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._conn.executemany(sql, params_list)
        )

    async def commit(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._conn.commit)

    async def close(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._conn.close)


@asynccontextmanager
async def get_db():
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, _make_connection)
    db = AsyncDB(conn)
    try:
        yield db
    except Exception:
        raise
    finally:
        await db.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    role TEXT DEFAULT 'client',
    is_approved INTEGER DEFAULT 0,
    accepted_terms INTEGER DEFAULT 0,
    np_city TEXT,
    np_branch TEXT,
    np_recipient TEXT,
    company_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT,
    iban TEXT,
    display_name TEXT,
    edrpou TEXT,
    legal_address TEXT,
    director TEXT,
    phone TEXT,
    description TEXT,
    postal_address TEXT,
    region TEXT,
    postal_code TEXT
);
CREATE TABLE IF NOT EXISTS fop_settings (
    id INTEGER PRIMARY KEY,
    fop_name TEXT,
    iban TEXT,
    edrpou TEXT,
    bank_name TEXT,
    legal_address TEXT,
    phone TEXT,
    payment_template TEXT DEFAULT 'Оплата за замовленням'
);
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    logo_file_id TEXT
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    photo_file_id TEXT,
    description TEXT,
    ingredients TEXT,
    volume TEXT,
    client_price REAL NOT NULL,
    purchase_price REAL,
    stock_qty INTEGER DEFAULT 0,
    comment TEXT,
    brand_id INTEGER,
    category_id INTEGER,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT DEFAULT 'new',
    total_amount REAL DEFAULT 0,
    comment TEXT,
    np_city TEXT,
    np_branch TEXT,
    np_recipient TEXT,
    invoice_requested INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    order_id INTEGER NOT NULL,
    invoice_date TEXT,
    due_date TEXT,
    total_amount REAL,
    status TEXT DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db():
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, _make_connection)
    try:
        stmts = [s.strip() for s in _SCHEMA.split(";") if s.strip()]
        for stmt in stmts:
            await loop.run_in_executor(None, lambda s=stmt: conn.execute(s))
        # INSERT OR IGNORE для fop_settings
        await loop.run_in_executor(
            None, lambda: conn.execute("INSERT OR IGNORE INTO fop_settings (id) VALUES (1)")
        )
        await loop.run_in_executor(None, conn.commit)
    finally:
        await loop.run_in_executor(None, conn.close)
    print("✅ Database initialized")
