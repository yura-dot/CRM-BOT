import os
import libsql_experimental as libsql
from contextlib import asynccontextmanager
import asyncio

TURSO_URL = os.getenv("TURSO_DB_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
LOCAL_DB = os.getenv("DB_PATH", "supercrm.db")

def _get_connection():
    """Створює з'єднання — Turso якщо є змінні, інакше локальний SQLite"""
    if TURSO_URL and TURSO_TOKEN:
        return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    return libsql.connect(LOCAL_DB)

class AsyncDBWrapper:
    """Обгортка для синхронного libsql щоб працювати як async context manager"""
    def __init__(self):
        self.conn = None
        self.row_factory = None

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        self.conn = await loop.run_in_executor(None, _get_connection)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.conn.close)
            except Exception:
                pass

    async def execute(self, sql, params=()):
        loop = asyncio.get_event_loop()
        cursor = await loop.run_in_executor(None, lambda: self.conn.execute(sql, params))
        return AsyncCursorWrapper(cursor, self.row_factory)

    async def executescript(self, sql):
        loop = asyncio.get_event_loop()
        # Розбиваємо на окремі statements
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            await loop.run_in_executor(None, lambda s=stmt: self.conn.execute(s))
        await loop.run_in_executor(None, self.conn.commit)

    async def commit(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.conn.commit)


class AsyncCursorWrapper:
    def __init__(self, cursor, row_factory=None):
        self.cursor = cursor
        self.row_factory = row_factory
        self._rows = None

    def _load_rows(self):
        if self._rows is None:
            try:
                self._rows = self.cursor.fetchall()
            except Exception:
                self._rows = []

    async def fetchall(self):
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, lambda: self.cursor.fetchall())
        if self.row_factory == "dict":
            cols = [d[0] for d in self.cursor.description] if self.cursor.description else []
            return [dict(zip(cols, row)) for row in rows]
        return rows

    async def fetchone(self):
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(None, lambda: self.cursor.fetchone())
        if row is None:
            return None
        if self.row_factory == "dict":
            cols = [d[0] for d in self.cursor.description] if self.cursor.description else []
            return dict(zip(cols, row))
        return row

    @property
    def lastrowid(self):
        return self.cursor.lastrowid


@asynccontextmanager
async def get_db():
    db = AsyncDBWrapper()
    async with db as conn:
        yield conn


async def init_db():
    import aiosqlite
    # Для ініціалізації використовуємо aiosqlite локально або через libsql
    if TURSO_URL and TURSO_TOKEN:
        conn = _get_connection()
        schema = _get_schema()
        statements = [s.strip() for s in schema.split(";") if s.strip()]
        for stmt in statements:
            try:
                conn.execute(stmt)
            except Exception as e:
                pass
        conn.commit()
        conn.close()
    else:
        async with aiosqlite.connect(LOCAL_DB) as db:
            await db.executescript(_get_schema())
            await db.commit()
    print("✅ Database initialized")


def _get_schema():
    return """
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
        id INTEGER PRIMARY KEY DEFAULT 1,
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
    INSERT OR IGNORE INTO fop_settings (id) VALUES (1)
    """
