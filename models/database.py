import aiosqlite
import os

DB_PATH = "supercrm.db"

async def get_db():
    return await aiosqlite.connect(DB_PATH)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
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
            payment_template TEXT DEFAULT 'Оплата за замовленням №{order_number}'
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

        INSERT OR IGNORE INTO fop_settings (id) VALUES (1);
        """)
        await db.commit()
    print("✅ Database initialized")
