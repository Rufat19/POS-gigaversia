"""POS simple Flask application: products listing, cart checkout and basic DB setup.

This module provides endpoints to render a product kiosk-style frontend and to
process an in-memory cart via /checkout. It supports SQLite (local) and
PostgreSQL (via DATABASE_URL).
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any

import psycopg2
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
database_url = os.getenv("DATABASE_URL")
secret_key = os.getenv("SECRET_KEY")
seller_pin = os.getenv("SELLER_PIN")
manager_pin = os.getenv("MANAGER_PIN")
admin_pin = os.getenv("ADMIN_PIN", "414541")
is_production = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_PROJECT_ID")
    or os.getenv("FLASK_ENV") == "production"
)

if is_production and not all((secret_key, seller_pin, manager_pin)):
    raise RuntimeError(
        "SECRET_KEY, SELLER_PIN and MANAGER_PIN must be configured in production."
    )

app.config["SECRET_KEY"] = secret_key or "local-development-only-secret"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = is_production

PIN_USERS = {
    seller_pin or "1111": "seller",
    manager_pin or "1991": "manager",
    admin_pin: "admin",
}

FEATURE_DEFAULTS = {
    "products": True,
    "tables": True,
    "open_orders": True,
    "operations": True,
    "reports": True,
}

DEFAULT_PRODUCTS = [
    ("Cola 0.5", "Drinks", 2.00, 50, None),
    ("Cola banka", "Drinks", 2.50, 50, None),
    ("Pepsi banka", "Drinks", 2.50, 50, None),
    ("Ice Coffee", "Drinks", 2.50, 50, None),
    ("Fuse Tea 0.5", "Drinks", 2.00, 50, None),
    ("Red bul", "Drinks", 5.00, 50, None),
    ("Moxito", "Drinks", 2.00, 50, None),
    ("Bizon Hell", "Drinks", 1.40, 50, None),
    ("Sirab 0.5", "Drinks", 1.00, 50, None),
    ("Sirab 1 lt", "Drinks", 1.50, 50, None),
    ("Sirab Qazlı 0.5", "Drinks", 1.00, 50, None),
    ("SARIKIZ", "Drinks", 1.00, 50, None),
    ("Natura təbii şirə", "Drinks", 1.40, 50, None),
    ("Lovita Peçenye", "Snacks", 5.00, 50, None),
    ("Crax Böyük", "Snacks", 2.00, 50, None),
    ("TUC", "Snacks", 3.50, 50, None),
    ("7 Days", "Snacks", 2.00, 50, None),
    ("OZMO fun", "Snacks", 2.20, 50, None),
    ("OZMO Cornet", "Snacks", 1.60, 50, None),
    ("OZMO yumurta", "Snacks", 3.00, 50, None),
    ("Snickers, Mars, Twix", "Snacks", 2.40, 50, None),
    ("Albeni şokolad", "Snacks", 2.40, 50, None),
    ("Hoşbeş", "Snacks", 1.20, 50, None),
    ("Ozmo ogopogo", "Snacks", 1.20, 50, None),
    ("POP cake", "Snacks", 1.20, 50, None),
    ("Barni", "Snacks", 2.00, 50, None),
    ("LAYS", "Snacks", 5.00, 50, None),
    ("Chetos", "Snacks", 4.00, 50, None),
    ("Yummy gummy", "Snacks", 2.50, 50, None),
    ("Biskolata mood", "Snacks", 4.00, 50, None),
    ("Biskolata  Stick", "Snacks", 2.50, 50, None),
    ("Chupa Chups", "Snacks", 1.50, 50, None),
    ("Chupa Chups Vata", "Snacks", 2.50, 50, None),
    ("Nut GO", "Snacks", 2.00, 50, None),
    ("Marshmallow rainbow", "Snacks", 3.00, 50, None),
    ("Morsok", "Snacks", 3.50, 50, None),
    ("Kinder Surprise", "Snacks", 4.00, 50, None),
    ("Rainbow", "Snacks", 1.00, 50, None),
    ("Dirol", "Snacks", 1.00, 50, None),
    ("ŞOKOLAD", "Snacks", 1.50, 50, None),
    ("ŞOKOLAD balaca", "Snacks", 1.00, 50, None),
    ("Xrusteam", "Snacks", 2.00, 50, None),
    ("BALMİTO", "Snacks", 2.00, 50, None),
    ("KİT-KAT", "Snacks", 4.00, 50, None),
    ("MİLKA", "Snacks", 5.00, 50, None),
    ("ƏTİR", "Other", 6.00, 50, None),
    ("OREO", "Snacks", 3.50, 50, None),
    ("Yubileynoe peçenye şokolad", "Snacks", 2.70, 50, None),
    ("Yubileynoe peçenye sadə", "Snacks", 2.20, 50, None),
    ("Lovita balaca", "Snacks", 3.00, 50, None),
    ("Balık kreker", "Snacks", 2.00, 50, None),
    ("Biskolata starz", "Snacks", 3.00, 50, None),
    ("İkram", "Snacks", 2.00, 50, None),
    ("Mentos duo", "Snacks", 2.50, 50, None),
    ("Bambbar shok  50 gr", "Protein", 5.00, 50, None),
    ("Snaqfabrique 55 gr", "Protein", 4.50, 50, None),
    ("Snager 50 gr", "Protein", 4.00, 50, None),
    ("Pritein delice 60 gr", "Protein", 4.00, 50, None),
    ("Bombbar wafer 45 gr", "Protein", 4.00, 50, None),
    ("Fitness shock 50 gr", "Protein", 4.00, 50, None),
    ("Bombbar l-carnitine", "Protein", 5.00, 50, None),
    ("Bambbar protein chips", "Protein", 4.00, 50, None),
    ("Boul", "Salads", 8.00, 50, None),
    ("Sezar Salat", "Salads", 8.00, 50, None),
    ("Club Sendvich", "Fastfood", 7.00, 50, None),
    ("Burger", "Fastfood", 6.00, 50, None),
    ("Sezar Roll", "Fastfood", 7.00, 50, None),
    ("Bulka", "Fastfood", 2.50, 50, None),
    ("Bulka 3₼", "Fastfood", 3.00, 50, None),
    ("Sirab 1.5", "Drinks", 2.00, 50, None),
]


def get_db_config():
    """Return database configuration tuple (DATABASE_URL, SQLITE_DB_PATH).

    DATABASE_URL takes precedence; SQLITE_DB_PATH is used when DATABASE_URL
    is not set (local development).
    """
    database_url = os.getenv("DATABASE_URL")
    sqlite_db_path = os.getenv("SQLITE_DB_PATH", str(Path(__file__).parent / "app.db"))
    return database_url, sqlite_db_path


def get_db():
    """Get a DB connection for the current Flask request context (g).

    Connects to PostgreSQL when DATABASE_URL is set; otherwise uses SQLite.
    The connection is stored on ``g.db`` for reuse during the request.
    """
    if "db" not in g:
        database_url, sqlite_db_path = get_db_config()
        if database_url:
            conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            conn.autocommit = False
        else:
            conn = sqlite3.connect(sqlite_db_path)
            conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    """Close the database connection stored on the Flask g object.

    The teardown handler accepts an optional exception argument per Flask's
    contract but does not need to use it directly.
    """
    # mark exc as intentionally unused to satisfy linters
    if exc is not None:
        pass

    db = g.pop("db", None)
    if db is not None:
        db.close()


def _get_permissions(conn, database_url):
    cur = conn.cursor()
    try:
        cur.execute("SELECT products, tables, open_orders, operations, reports FROM feature_permissions WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            return FEATURE_DEFAULTS.copy()
        return {
            "products": bool(_row_value(row, "products")),
            "tables": bool(_row_value(row, "tables")),
            "open_orders": bool(_row_value(row, "open_orders")),
            "operations": bool(_row_value(row, "operations")),
            "reports": bool(_row_value(row, "reports")),
        }
    finally:
        cur.close()


def _feature_for_endpoint(endpoint):
    if endpoint in {"products_page", "checkout"} or endpoint in {
        "add_product", "update_product", "delete_product"
    }:
        return "products"
    if endpoint in {"tables_page", "tables_api", "table_products_api", "add_table_items", "close_table"}:
        return "tables"
    if endpoint in {"open_orders_page", "credit_orders_api", "add_credit_order_items", "pay_credit_order"}:
        return "open_orders"
    if endpoint in {"operations_page", "add_movement", "add_category", "rename_category", "delete_category",
                    "add_table_category", "manage_table_category", "add_dining_table", "manage_dining_table"}:
        return "operations"
    if endpoint in {"reports_page", "api_reports"}:
        return "reports"
    return None


@app.context_processor
def inject_feature_permissions():
    role = session.get("role")
    if role == "admin":
        return {"feature_enabled": lambda feature: True}
    if "db" not in g:
        return {"feature_enabled": lambda feature: True}
    database_url, _ = get_db_config()
    permissions = _get_permissions(g.db, database_url)
    return {"feature_enabled": lambda feature: permissions.get(feature, True)}


@app.before_request
def enforce_access():
    """Restrict pages based on the logged-in user role."""
    if request.endpoint in {None, 'static', 'login_page', 'logout'}:
        return None
    if not session.get('role'):
        return redirect(url_for('login_page'))

    role = session.get('role')
    feature = _feature_for_endpoint(request.endpoint)
    if role != "admin" and feature:
        init_db()
        database_url, _ = get_db_config()
        if not _get_permissions(get_db(), database_url).get(feature, True):
            if request.path.startswith("/api/") or request.method != "GET":
                return jsonify({"success": False, "message": "Bu bölmə admin tərəfindən bloklanıb."}), 403
            return abort(403)
    if role == "admin":
        return None
    protected_pages = {'operations_page', 'reports_page'}
    protected_actions = {
        'add_movement',
        'api_reports',
        'add_product',
        'update_product',
        'delete_product',
        'add_category',
        'rename_category',
        'delete_category',
        'add_table_category',
        'manage_table_category',
        'add_dining_table',
        'manage_dining_table',
    }

    if request.endpoint in protected_pages and role != 'manager':
        return abort(403)
    if request.endpoint in protected_actions and role != 'manager':
        return jsonify({'success': False, 'message': 'Bu əməliyyat üçün icazə yoxdur.'}), 403


def _audit_event(conn, database_url, action, entity_type, entity_id=None, details=None):
    """Record the current role's action for accountability."""
    actor_role = session.get("role", "system")
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO audit_log
                    (actor_role, action, entity_type, entity_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (actor_role, action, entity_type, entity_id, details),
            )
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO audit_log
                    (actor_role, action, entity_type, entity_id, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (actor_role, action, entity_type, entity_id, details),
            )
        finally:
            cur.close()


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Authenticate a seller, manager or administrator using a PIN."""
    if session.get('role'):
        return redirect(url_for('products_page'))

    error = None
    if request.method == 'POST':
        pin = str(request.form.get('pin', '')).strip()
        init_db()
        conn = get_db()
        database_url, _ = get_db_config()
        now = time.time()
        security_key = "admin" if len(pin) >= 6 else None
        if security_key:
            blocked_until = _login_blocked_until(conn, database_url, security_key)
            if blocked_until > now:
                error = f'Admin PIN-i müvəqqəti bloklanıb. {int(blocked_until - now) + 1} saniyə sonra yenidən cəhd edin.'
                return render_template('login.html', error=error)
        role = PIN_USERS.get(pin)
        if role:
            if role == "admin" and security_key:
                _reset_login_security(conn, database_url, security_key)
            session.clear()
            session['role'] = role
            _audit_event(conn, database_url, "login", "session", details=role)
            conn.commit()
            return redirect(url_for('products_page'))
        if security_key:
            lock_seconds = _record_failed_login(conn, database_url, security_key)
            conn.commit()
            if lock_seconds:
                error = f'Yanlış admin PIN-i. Çoxsaylı səhvdən sonra {lock_seconds} saniyəlik blok tətbiq edildi.'
            else:
                error = 'Yanlış PIN kodu.'
        else:
            error = 'Yanlış PIN kodu.'

    return render_template('login.html', error=error)


def _login_blocked_until(conn, database_url, login_key):
    cur = conn.cursor()
    try:
        placeholder = "%s" if database_url else "?"
        cur.execute(
            f"SELECT blocked_until FROM login_security WHERE login_key = {placeholder}",
            (login_key,),
        )
        row = cur.fetchone()
        return float(_row_value(row, "blocked_until") or 0) if row else 0
    finally:
        cur.close()


def _record_failed_login(conn, database_url, login_key):
    cur = conn.cursor()
    try:
        placeholder = "%s" if database_url else "?"
        cur.execute(
            f"SELECT failed_attempts FROM login_security WHERE login_key = {placeholder}",
            (login_key,),
        )
        row = cur.fetchone()
        attempts = int(_row_value(row, "failed_attempts") or 0) + 1 if row else 1
        lock_seconds = 0
        if attempts % 3 == 0:
            lock_seconds = min(3600, 30 * (2 ** (attempts // 3 - 1)))
        if database_url:
            cur.execute(
                """
                INSERT INTO login_security (login_key, failed_attempts, blocked_until)
                VALUES (%s, %s, %s)
                ON CONFLICT (login_key) DO UPDATE SET
                    failed_attempts = EXCLUDED.failed_attempts,
                    blocked_until = EXCLUDED.blocked_until
                """,
                (login_key, attempts, time.time() + lock_seconds),
            )
        else:
            cur.execute(
                """
                INSERT INTO login_security (login_key, failed_attempts, blocked_until)
                VALUES (?, ?, ?)
                ON CONFLICT(login_key) DO UPDATE SET
                    failed_attempts = excluded.failed_attempts,
                    blocked_until = excluded.blocked_until
                """,
                (login_key, attempts, time.time() + lock_seconds),
            )
        return lock_seconds
    finally:
        cur.close()


def _reset_login_security(conn, database_url, login_key):
    cur = conn.cursor()
    try:
        placeholder = "%s" if database_url else "?"
        cur.execute(
            f"DELETE FROM login_security WHERE login_key = {placeholder}",
            (login_key,),
        )
    finally:
        cur.close()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


def _create_tables_postgres(conn):
    """Create tables and seed initial products for PostgreSQL.

    Separated from init_db to reduce function complexity and keep DB-specific
    logic isolated.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                category VARCHAR(50) DEFAULT 'Other',
                price NUMERIC(10,2) NOT NULL,
                stock INT NOT NULL DEFAULT 0,
                image_url TEXT
            )
            """
        )
        # Ensure category and image_url columns exist (for older DBs)
        try:
            alter_sql = (
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS category "
                "VARCHAR(50) DEFAULT 'Other'"
            )
            cur.execute(alter_sql)
        except (psycopg2.Error, sqlite3.Error):
            # If ALTER fails (older Postgres/permissions), ignore and continue
            pass
        try:
            cur.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT"
            )
        except (psycopg2.Error, sqlite3.Error):
            pass

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount NUMERIC(10,2) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'completed',
                cancelled_at TIMESTAMP
            )
            """
        )
        cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'completed'")
        cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_items (
                id SERIAL PRIMARY KEY,
                sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                quantity INT NOT NULL,
                unit_price NUMERIC(10,2) NOT NULL
            )
            """
        )
        # stock_movements table: records stock ins/outs (daxilolma/itki)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_movements (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                type VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                actor_role VARCHAR(30) NOT NULL,
                action VARCHAR(80) NOT NULL,
                entity_type VARCHAR(40) NOT NULL,
                entity_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_orders (
                id SERIAL PRIMARY KEY,
                customer_name VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                total_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                paid_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP
            )
            """
        )
        cur.execute(
            "ALTER TABLE credit_orders ADD COLUMN IF NOT EXISTS paid_amount NUMERIC(10,2) NOT NULL DEFAULT 0"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_order_items (
                id SERIAL PRIMARY KEY,
                credit_order_id INTEGER NOT NULL REFERENCES credit_orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                quantity INT NOT NULL,
                unit_price NUMERIC(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS table_orders (
                id SERIAL PRIMARY KEY,
                table_number INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS table_order_items (
                id SERIAL PRIMARY KEY,
                table_order_id INTEGER NOT NULL REFERENCES table_orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                quantity INTEGER NOT NULL,
                unit_price NUMERIC(10,2) NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dining_tables (
                table_number INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                category VARCHAR(100) NOT NULL DEFAULT 'Standart'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS table_categories (
                name VARCHAR(100) PRIMARY KEY
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_permissions (
                id INTEGER PRIMARY KEY,
                products BOOLEAN NOT NULL DEFAULT TRUE,
                tables BOOLEAN NOT NULL DEFAULT TRUE,
                open_orders BOOLEAN NOT NULL DEFAULT TRUE,
                operations BOOLEAN NOT NULL DEFAULT TRUE,
                reports BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        cur.execute(
            """
            INSERT INTO feature_permissions (id) VALUES (1)
            ON CONFLICT (id) DO NOTHING
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_security (
                login_key VARCHAR(50) PRIMARY KEY,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                blocked_until DOUBLE PRECISION NOT NULL DEFAULT 0
            )
            """
        )

        cur.execute("SELECT name FROM products")
        existing_names = set()
        for row in cur.fetchall():
            if not isinstance(row, tuple) and hasattr(row, "get"):
                existing_names.add(str(row.get("name", "")))
            else:
                existing_names.add(str(row[0]))

        insert_sql = (
            "INSERT INTO products (name, category, price, stock, image_url) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        for product in DEFAULT_PRODUCTS:
            if product[0] not in existing_names:
                cur.execute(insert_sql, product)
        conn.commit()
    finally:
        cur.close()


def _create_tables_sqlite(conn):
    """Create tables and seed initial products for SQLite.

    Separated from init_db to reduce function complexity and keep DB-specific
    logic isolated.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                image_url TEXT
            )
            """
        )
        # Add category/image_url column if missing (SQLite)
        cur.execute("PRAGMA table_info('products')")
        cols = [row[1] for row in cur.fetchall()]
        if 'category' not in cols:
            try:
                alter_sql = ("ALTER TABLE products ADD COLUMN category TEXT "
                             "DEFAULT 'Other'")
                cur.execute(alter_sql)
            except sqlite3.Error:
                pass
        if 'image_url' not in cols:
            try:
                cur.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
            except sqlite3.Error:
                pass

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                cancelled_at TEXT
            )
            """
        )
        cur.execute("PRAGMA table_info('sales')")
        sales_columns = {row[1] for row in cur.fetchall()}
        if "status" not in sales_columns:
            cur.execute("ALTER TABLE sales ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'")
        if "cancelled_at" not in sales_columns:
            cur.execute("ALTER TABLE sales ADD COLUMN cancelled_at TEXT")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """
        )
        # stock_movements table for SQLite
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_role TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                total_amount REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                paid_at TEXT
            )
            """
        )
        cur.execute("PRAGMA table_info('credit_orders')")
        credit_order_columns = {row[1] for row in cur.fetchall()}
        if "paid_amount" not in credit_order_columns:
            cur.execute(
                "ALTER TABLE credit_orders ADD COLUMN paid_amount REAL NOT NULL DEFAULT 0"
            )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (credit_order_id) REFERENCES credit_orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS table_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS table_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (table_order_id) REFERENCES table_orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dining_tables (
                table_number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Standart'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS table_categories (
                name TEXT PRIMARY KEY
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_permissions (
                id INTEGER PRIMARY KEY,
                products INTEGER NOT NULL DEFAULT 1,
                tables INTEGER NOT NULL DEFAULT 1,
                open_orders INTEGER NOT NULL DEFAULT 1,
                operations INTEGER NOT NULL DEFAULT 1,
                reports INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute("INSERT OR IGNORE INTO feature_permissions (id) VALUES (1)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_security (
                login_key TEXT PRIMARY KEY,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                blocked_until REAL NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute("SELECT name FROM products")
        existing_names = set()
        for row in cur.fetchall():
            if isinstance(row, sqlite3.Row):
                existing_names.add(str(row["name"]))
            elif not isinstance(row, tuple) and hasattr(row, "get"):
                existing_names.add(str(row.get("name", "")))
            else:
                existing_names.add(str(row[0]))

        insert_sql = (
            "INSERT INTO products (name, category, price, stock, image_url) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        for product in DEFAULT_PRODUCTS:
            if product[0] not in existing_names:
                cur.execute(insert_sql, product)
        conn.commit()
    finally:
        cur.close()


def _sync_categories(conn, database_url):
    """Ensure category metadata stays aligned with product data."""
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE
                )
                """
            )
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
            existing = {
                row["category"] for row in cur.fetchall()
                if row and row["category"]
            }
            for name in sorted(existing):
                cur.execute(
                    "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )
            cur.execute(
                "SELECT name FROM categories WHERE name NOT IN (SELECT DISTINCT category FROM products WHERE category IS NOT NULL)"
            )
            orphan_names = [row["name"] for row in cur.fetchall()]
            for name in orphan_names:
                cur.execute("DELETE FROM categories WHERE name = %s", (name,))
            conn.commit()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
            existing = {row[0] for row in cur.fetchall() if row and row[0]}
            for name in sorted(existing):
                cur.execute(
                    "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (name,),
                )
            cur.execute(
                "SELECT name FROM categories WHERE name NOT IN (SELECT DISTINCT category FROM products WHERE category IS NOT NULL)"
            )
            orphan_names = [row[0] for row in cur.fetchall()]
            for name in orphan_names:
                cur.execute("DELETE FROM categories WHERE name = ?", (name,))
            conn.commit()
        finally:
            cur.close()


def _ensure_category(conn, database_url, category_name):
    """Create a category record if it does not already exist."""
    if category_name is None:
        return
    name = str(category_name).strip() or 'Other'
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (name,),
            )
            conn.commit()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
            conn.commit()
        finally:
            cur.close()


def _get_categories(conn, database_url):
    """Return sorted category names from the category table or derived product data."""
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute("SELECT name FROM categories ORDER BY name")
            categories = [
                row["name"] for row in cur.fetchall()
                if row and row["name"]
            ]
            if categories:
                return categories
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category")
            return [
                row["category"] for row in cur.fetchall()
                if row and row["category"]
            ]
        finally:
            cur.close()

    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM categories ORDER BY name")
        categories = [row[0] for row in cur.fetchall() if row and row[0]]
        if categories:
            return categories
        cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category")
        return [row[0] for row in cur.fetchall() if row and row[0]]
    finally:
        cur.close()


def init_db():
    """Initialize database tables for products, sales and sale_items.

    Creates tables if they do not exist. Works for both PostgreSQL and SQLite.
    """
    conn = get_db()
    database_url, _ = get_db_config()

    if database_url:
        _create_tables_postgres(conn)
    else:
        _create_tables_sqlite(conn)
    _sync_categories(conn, database_url)
    _sync_table_definitions(conn, database_url)


def _sync_table_definitions(conn, database_url):
    """Seed the initial six tables and default table category."""
    cur = conn.cursor()
    try:
        if database_url:
            cur.execute(
                "INSERT INTO table_categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                ("Standart",),
            )
            for number in range(1, 7):
                cur.execute(
                    """
                    INSERT INTO dining_tables (table_number, name, category)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (table_number) DO NOTHING
                    """,
                    (number, f"Masa {number}", "Standart"),
                )
        else:
            cur.execute("INSERT OR IGNORE INTO table_categories (name) VALUES (?)", ("Standart",))
            for number in range(1, 7):
                cur.execute(
                    "INSERT OR IGNORE INTO dining_tables (table_number, name, category) VALUES (?, ?, ?)",
                    (number, f"Masa {number}", "Standart"),
                )
        conn.commit()
    finally:
        cur.close()


@app.route("/")
def products_page():
    """Render the products page (kiosk UI).

    Ensures DB is initialized, loads products and distinct categories and passes
    them to the products.html template.
    """
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, name, category, price, stock, image_url FROM products ORDER BY id")
            products = cur.fetchall()
        finally:
            cur.close()
    else:
        products_sql = (
            "SELECT id, name, category, price, stock, image_url "
            "FROM products ORDER BY id"
        )
        cur = conn.cursor()
        try:
            cur.execute(products_sql)
            products = cur.fetchall()
        finally:
            cur.close()

    categories = _get_categories(conn, database_url)
    return render_template("products.html", products=products, categories=categories)


@app.route('/operations')
def operations_page():
    """Render operations page: add stock movements and show combined history."""
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    end = datetime.utcnow().date()
    start = end - timedelta(days=6)

    # load products for dropdown
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, category, price, stock, image_url "
                "FROM products ORDER BY name"
            )
            products = cur.fetchall()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, category, price, stock, image_url "
                "FROM products ORDER BY name"
            )
            products = cur.fetchall()
        finally:
            cur.close()

    # fetch combined history (sales items + stock_movements)
    history = []
    if database_url:
        cur = conn.cursor()
        try:
            # sales items
            cur.execute(
                """
                SELECT s.created_at AS created_at,
                       p.name AS product_name,
                       'sale' AS kind,
                       si.quantity AS quantity,
                       (si.unit_price * si.quantity) AS amount
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN products p ON si.product_id = p.id
                WHERE s.status = 'completed'
                UNION ALL
                SELECT sm.created_at AS created_at,
                       p.name AS product_name,
                       sm.type AS kind,
                       sm.quantity AS quantity,
                       NULL AS amount
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                ORDER BY created_at DESC
                """
            )
            history = cur.fetchall()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT s.created_at AS created_at,
                       p.name AS product_name,
                       'sale' AS kind,
                       si.quantity AS quantity,
                       (si.unit_price * si.quantity) AS amount
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN products p ON si.product_id = p.id
                WHERE s.status = 'completed'
                UNION ALL
                SELECT sm.created_at AS created_at,
                       p.name AS product_name,
                       sm.type AS kind,
                       sm.quantity AS quantity,
                       NULL AS amount
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                ORDER BY created_at DESC
                """
            )
            history = cur.fetchall()
        finally:
            cur.close()

    categories = _get_categories(conn, database_url)
    cur = conn.cursor()
    try:
        cur.execute("SELECT table_number, name, category FROM dining_tables ORDER BY table_number")
        dining_tables = cur.fetchall()
        cur.execute("SELECT name FROM table_categories ORDER BY name")
        table_categories = [_row_value(row, "name") for row in cur.fetchall()]
    finally:
        cur.close()
    return render_template(
        'operations.html',
        products=products,
        history=history,
        categories=categories,
        dining_tables=dining_tables,
        table_categories=table_categories,
        default_start=start.isoformat(),
        default_end=end.isoformat(),
    )


def _query_reports_postgres(conn, start_date, end_date):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT p.id,
                   p.name,
                   SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND s.created_at::date BETWEEN %s AND %s
            GROUP BY p.id, p.name
            ORDER BY total_qty DESC
            """,
            (start_date, end_date),
        )
        prod_totals = cur.fetchall()

        cur.execute(
            """
            SELECT p.category,
                   SUM(si.quantity * si.unit_price) AS total_amount
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND s.created_at::date BETWEEN %s AND %s
            GROUP BY p.category
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        )
        cat_break = cur.fetchall()

        cur.execute(
            """
            SELECT DATE_TRUNC('day', s.created_at) AS day,
                   SUM(si.quantity * si.unit_price) AS total
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.status = 'completed' AND s.created_at::date BETWEEN %s AND %s
            GROUP BY day
            ORDER BY day ASC
            """,
            (start_date, end_date),
        )
        daily = cur.fetchall()

        cur.execute(
            """
            SELECT p.name, SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND s.created_at::date BETWEEN %s AND %s
            GROUP BY p.name
            ORDER BY total_qty DESC
            LIMIT 5
            """,
            (start_date, end_date),
        )
        top5 = cur.fetchall()

        return prod_totals, cat_break, daily, top5
    finally:
        cur.close()


def _query_reports_sqlite(conn, start_date, end_date):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT p.id, p.name, SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND DATE(s.created_at) BETWEEN ? AND ?
            GROUP BY p.id, p.name
            ORDER BY total_qty DESC
            """,
            (start_date, end_date),
        )
        prod_totals = cur.fetchall()

        cur.execute(
            """
            SELECT p.category, SUM(si.quantity * si.unit_price) AS total_amount
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        )
        cat_break = cur.fetchall()

        cur.execute(
            """
            SELECT DATE(s.created_at) AS day,
                   SUM(si.quantity * si.unit_price) AS total
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day ASC
            """,
            (start_date, end_date),
        )
        daily = cur.fetchall()

        cur.execute(
            """
            SELECT p.name, SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
            GROUP BY p.name
            ORDER BY total_qty DESC
            LIMIT 5
            """,
            (start_date, end_date),
        )
        top5 = cur.fetchall()

        return prod_totals, cat_break, daily, top5
    finally:
        cur.close()


def _format_report_data(prod_totals, cat_break, daily, top5):
    most = prod_totals[0] if prod_totals else None
    least = prod_totals[-1] if prod_totals else None
    most_obj = None
    least_obj = None
    if most:
        most_obj = {
            'id': most['id'],
            'name': most['name'],
            'total_qty': int(most['total_qty']),
        }
    if least:
        least_obj = {
            'id': least['id'],
            'name': least['name'],
            'total_qty': int(least['total_qty']),
        }

    return {
        'most_sold': most_obj,
        'least_sold': least_obj,
        'category_breakdown': [
            {
                'category': row['category'] or 'Other',
                'total_amount': (
                    float(row['total_amount'])
                    if row['total_amount'] is not None
                    else 0.0
                ),
            }
            for row in cat_break
        ],
        'daily_totals': [
            {
                'date': row['day'].strftime('%Y-%m-%d')
                if hasattr(row['day'], 'strftime')
                else str(row['day']),
                'total': float(row['total']) if row['total'] is not None else 0.0,
            }
            for row in daily
        ],
        'top5_products': [
            {
                'name': row['name'],
                'total_qty': int(row['total_qty']),
            }
            for row in top5
        ],
    }


def _process_stock_movement(conn, database_url, movement):
    movement_type = movement['movement_type']
    quantity = movement['quantity']

    if movement_type not in ('daxilolma', 'itki'):
        raise ValueError('Növ səhvdir')

    if quantity <= 0:
        raise ValueError('Miqdar müsbət olmalıdır')

    if database_url:
        return _process_stock_movement_postgres(conn, movement)

    return _process_stock_movement_sqlite(conn, movement)


def _process_stock_movement_postgres(conn, movement):
    return _process_stock_movement_common(conn, '%s', movement)


def _process_stock_movement_sqlite(conn, movement):
    return _process_stock_movement_common(conn, '?', movement)


def _process_stock_movement_common(conn, placeholder, movement):
    product_id = movement['product_id']
    movement_type = movement['movement_type']
    quantity = movement['quantity']
    note = movement['note']

    select_sql = f'SELECT stock, name FROM products WHERE id = {placeholder}'
    insert_sql = (
        f'INSERT INTO stock_movements (product_id, type, quantity, note) '
        f'VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})'
    )
    update_sql = (
        f'UPDATE products SET stock = stock + {placeholder} WHERE id = {placeholder}'
        if movement_type == 'daxilolma'
        else f'UPDATE products SET stock = stock - {placeholder} WHERE id = {placeholder}'
    )

    cur = conn.cursor()
    try:
        cur.execute(select_sql, (product_id,))
        prod = cur.fetchone()
        if prod is None:
            raise ValueError('Məhsul tapılmadı')

        if isinstance(prod, dict):
            current_stock = int(prod.get('stock', 0))
        else:
            current_stock = int(prod[0])

        if movement_type == 'itki' and quantity > current_stock:
            raise ValueError('Stokda kifayət qədər məhsul yoxdur.')

        cur.execute(insert_sql, (product_id, movement_type, quantity, note))
        if placeholder == '%s':
            row = cur.fetchone()
            if row is None:
                movement_id = None
            elif isinstance(row, dict):
                movement_id = row.get('id')
            else:
                movement_id = row[0]
        else:
            movement_id = cur.lastrowid

        cur.execute(update_sql, (quantity, product_id))
        conn.commit()
        return movement_id
    finally:
        cur.close()


@app.route('/reports')
def reports_page():
    """Render the reports page with default last-30-days values."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=29)
    return render_template(
        'reports.html',
        default_start=start.isoformat(),
        default_end=end.isoformat(),
    )


@app.route('/admin')
def admin_page():
    """Render administrator-only feature access controls."""
    if session.get("role") != "admin":
        return abort(403)
    init_db()
    database_url, _ = get_db_config()
    permissions = _get_permissions(get_db(), database_url)
    return render_template("admin.html", permissions=permissions)


@app.route('/api/admin/permissions', methods=['POST'])
def update_admin_permissions():
    """Update feature access switches; this endpoint is administrator-only."""
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Yalnız admin bu ayarları dəyişə bilər."}), 403
    data = request.get_json(silent=True) or {}
    unknown = set(data) - set(FEATURE_DEFAULTS)
    if unknown:
        return jsonify({"success": False, "message": "Naməlum səlahiyyət bölməsi."}), 400
    permissions = {key: bool(data.get(key, FEATURE_DEFAULTS[key])) for key in FEATURE_DEFAULTS}
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        values = tuple(permissions[key] for key in FEATURE_DEFAULTS)
        if database_url:
            cur.execute(
                """
                UPDATE feature_permissions
                SET products = %s, tables = %s, open_orders = %s,
                    operations = %s, reports = %s
                WHERE id = 1
                """,
                values,
            )
        else:
            cur.execute(
                """
                UPDATE feature_permissions
                SET products = ?, tables = ?, open_orders = ?,
                    operations = ?, reports = ?
                WHERE id = 1
                """,
                values,
            )
        _audit_event(conn, database_url, "update_permissions", "feature_permissions", details=str(permissions))
        conn.commit()
    finally:
        cur.close()
    return jsonify({"success": True, "permissions": permissions})


@app.route('/api/reports', methods=['POST'])
def api_reports():
    """Return JSON report data for given date range (start_date, end_date).

    Expects JSON: {start_date: 'YYYY-MM-DD', end_date: 'YYYY-MM-DD'}
    """
    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': 'start_date and end_date required'}), 400

    conn = get_db()
    database_url, _ = get_db_config()

    try:
        if database_url:
            prod_totals, cat_break, daily, top5 = _query_reports_postgres(
                conn, start_date, end_date
            )
        else:
            prod_totals, cat_break, daily, top5 = _query_reports_sqlite(
                conn, start_date, end_date
            )

        report_data = _format_report_data(
            prod_totals, cat_break, daily, top5
        )
        return jsonify({'success': True, **report_data})
    except (sqlite3.Error, psycopg2.Error) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route('/operations/add', methods=['POST'])
def add_movement():
    """API to add a stock movement (daxilolma/itki).

    Expects JSON: {product_id, type, quantity, note}
    """
    data = request.get_json(silent=True) or {}
    try:
        product_id_raw = data.get('product_id')
        quantity_raw = data.get('quantity')
        if product_id_raw is None or quantity_raw is None:
            raise ValueError('missing')
        product_id = int(product_id_raw)
        movement_type = data.get('type')
        quantity = int(quantity_raw)
        note = data.get('note')
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Yanlış input'}), 400

    if movement_type not in ('daxilolma', 'itki'):
        return jsonify({'success': False, 'message': 'Növ səhvdir'}), 400
    if quantity <= 0:
        return jsonify({'success': False, 'message': 'Miqdar müsbət olmalıdır'}), 400

    conn = get_db()
    database_url, _ = get_db_config()
    try:
        movement_id = _process_stock_movement(
            conn,
            database_url,
            {
                'product_id': product_id,
                'movement_type': movement_type,
                'quantity': quantity,
                'note': note,
            },
        )
        return jsonify({'success': True, 'id': movement_id})
    except ValueError as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 400
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route("/checkout", methods=["POST"])
def checkout():
    """Process a cart checkout request.

    This function delegates DB-specific processing to helper functions to keep
    the top-level flow simple and easier to lint/maintain.
    """
    data = request.get_json(silent=True) or {}
    cart = data.get("cart", [])

    if not isinstance(cart, list) or not cart:
        return jsonify({"success": False, "message": "Səbət boşdur."}), 400

    conn = get_db()
    database_url, _ = get_db_config()

    try:
        if database_url:
            sale_id, total = _checkout_postgres(conn, cart)
        else:
            sale_id, total = _checkout_sqlite(conn, cart)

        _audit_event(
            conn,
            database_url,
            "sale_completed",
            "sale",
            sale_id,
            f"total={total:.2f}",
        )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "Satış tamamlandı!",
                "sale_id": sale_id,
                "total": total,
            }
        )
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except (sqlite3.Error, psycopg2.Error) as exc:
        # Top-level database error handler: rollback and return 500.
        conn.rollback()
        return jsonify(
            {
                "success": False,
                "message": f"Satış yazılarkən xəta: {exc}",
            }
        ), 500


def _checkout_postgres(conn, cart):
    """Process checkout using a PostgreSQL connection.

    Validates cart items, creates a sales row, inserts sale_items and updates
    product stock. Raises ValueError for client errors (bad payload or stock
    shortage) so the caller can return 400.
    """
    cur = conn.cursor()
    try:
        total_amount = 0.0
        # validate and compute total
        for item in cart:
            product_id = item.get("id")
            quantity = item.get("quantity", 0)
            if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Yanlış məhsul məlumatı")

            cur.execute(
                "SELECT id, name, price, stock FROM products WHERE id = %s",
                (product_id,),
            )
            product = cur.fetchone()
            if product is None:
                raise ValueError("Məhsul tapılmadı")
            if quantity > product["stock"]:
                raise ValueError(f"{product['name']} üçün kifayət qədər stok yoxdur.")

            line_total = float(product["price"]) * quantity
            total_amount += line_total

        # create sale
        insert_sale_sql = "INSERT INTO sales (total_amount) VALUES (%s) RETURNING id"
        cur.execute(insert_sale_sql, (round(total_amount, 2),))
        sale = cur.fetchone()
        sale_id = sale["id"]

        # insert items and update stock
        select_price_sql = "SELECT id, price FROM products WHERE id = %s"
        insert_item_sql = (
            "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) "
            "VALUES (%s, %s, %s, %s)"
        )
        update_stock_sql = "UPDATE products SET stock = stock - %s WHERE id = %s"

        for item in cart:
            product_id = item["id"]
            quantity = item["quantity"]
            cur.execute(select_price_sql, (product_id,))
            product = cur.fetchone()
            cur.execute(insert_item_sql, (sale_id, product_id, quantity, product["price"]))
            cur.execute(update_stock_sql, (quantity, product_id))

        conn.commit()
        return sale_id, round(total_amount, 2)
    finally:
        cur.close()


def _checkout_sqlite(conn, cart):
    """Process checkout using a SQLite connection.

    Mirrors the Postgres helper but uses SQLite paramstyle and cursor APIs.
    """
    total_amount = 0.0
    # validate and compute total
    for item in cart:
        product_id = item.get("id")
        quantity = item.get("quantity", 0)
        if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
            raise ValueError("Yanlış məhsul məlumatı")

        select_sql = (
            "SELECT id, name, price, stock FROM products "
            "WHERE id = ?"
        )
        product = conn.execute(select_sql, (product_id,)).fetchone()
        if product is None:
            raise ValueError("Məhsul tapılmadı")
        if quantity > product["stock"]:
            raise ValueError(f"{product['name']} üçün kifayət qədər stok yoxdur.")

        line_total = float(product["price"]) * quantity
        total_amount += line_total

    cursor = conn.cursor()
    insert_sale_sql = "INSERT INTO sales (total_amount) VALUES (?)"
    cursor.execute(insert_sale_sql, (round(total_amount, 2),))
    sale_id = cursor.lastrowid

    select_price_sql = "SELECT id, price FROM products WHERE id = ?"
    insert_item_sql = (
        "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) "
        "VALUES (?, ?, ?, ?)"
    )

    for item in cart:
        product_id = item["id"]
        quantity = item["quantity"]
        product = conn.execute(select_price_sql, (product_id,)).fetchone()
        cursor.execute(insert_item_sql, (sale_id, product_id, quantity, product["price"]))
        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))

    conn.commit()
    return sale_id, round(total_amount, 2)


@app.route("/api/sales/<int:sale_id>/cancel", methods=["POST"])
def cancel_sale(sale_id):
    """Cancel a sale only after manager PIN confirmation and restore stock."""
    data = request.get_json(silent=True) or {}
    manager_pin = str(data.get("manager_pin", "")).strip()
    if PIN_USERS.get(manager_pin) != "manager":
        return jsonify({"success": False, "message": "Rəhbər PIN-i yanlışdır."}), 403

    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        if database_url:
            cur.execute(
                "SELECT id, status FROM sales WHERE id = %s FOR UPDATE",
                (sale_id,),
            )
        else:
            cur.execute("SELECT id, status FROM sales WHERE id = ?", (sale_id,))
        sale = cur.fetchone()
        if sale is None:
            raise ValueError("Satış tapılmadı.")
        if _row_value(sale, "status") == "cancelled":
            raise ValueError("Satış artıq ləğv edilib.")

        if database_url:
            cur.execute(
                "SELECT product_id, quantity FROM sale_items WHERE sale_id = %s",
                (sale_id,),
            )
            items = cur.fetchall()
            for item in items:
                cur.execute(
                    "UPDATE products SET stock = stock + %s WHERE id = %s",
                    (_row_value(item, "quantity"), _row_value(item, "product_id")),
                )
            cur.execute(
                """
                UPDATE sales
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (sale_id,),
            )
        else:
            cur.execute(
                "SELECT product_id, quantity FROM sale_items WHERE sale_id = ?",
                (sale_id,),
            )
            items = cur.fetchall()
            for item in items:
                cur.execute(
                    "UPDATE products SET stock = stock + ? WHERE id = ?",
                    (_row_value(item, "quantity"), _row_value(item, "product_id")),
                )
            cur.execute(
                """
                UPDATE sales
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (sale_id,),
            )
        _audit_event(conn, database_url, "sale_cancelled", "sale", sale_id, "manager_pin_confirmed")
        conn.commit()
        return jsonify({"success": True, "message": "Satış ləğv edildi və stok bərpa olundu."})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Satış ləğv edilərkən xəta: {exc}"}), 500
    finally:
        cur.close()


def _credit_order_items(conn, database_url, credit_order_id):
    """Return item rows for a credit order in display-ready form."""
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT coi.product_id, p.name, coi.quantity, coi.unit_price,
                       (coi.quantity * coi.unit_price) AS line_total
                FROM credit_order_items coi
                JOIN products p ON p.id = coi.product_id
                WHERE coi.credit_order_id = %s
                ORDER BY coi.id
                """,
                (credit_order_id,),
            )
            return cur.fetchall()
        finally:
            cur.close()

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT coi.product_id, p.name, coi.quantity, coi.unit_price,
                   (coi.quantity * coi.unit_price) AS line_total
            FROM credit_order_items coi
            JOIN products p ON p.id = coi.product_id
            WHERE coi.credit_order_id = ?
            ORDER BY coi.id
            """,
            (credit_order_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()


def _row_value(row: object, key: str) -> Any:
    """Read a named column from SQLite rows and PostgreSQL dict rows."""
    if isinstance(row, sqlite3.Row):
        return row[key]
    if isinstance(row, dict):
        return row[key]
    raise TypeError("Database row does not support named columns")


def _create_credit_order(conn, database_url, customer_name, cart):
    """Create an open credit order, reserving stock for every cart item."""
    total_amount = 0.0
    validated = []
    if database_url:
        cur = conn.cursor()
        try:
            for item in cart:
                product_id = item.get("id")
                quantity = item.get("quantity", 0)
                if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
                    raise ValueError("Yanlış məhsul məlumatı")
                cur.execute(
                    "SELECT id, name, price, stock FROM products WHERE id = %s FOR UPDATE",
                    (product_id,),
                )
                product = cur.fetchone()
                if product is None:
                    raise ValueError("Məhsul tapılmadı")
                if quantity > product["stock"]:
                    raise ValueError(f"{product['name']} üçün kifayət qədər stok yoxdur.")
                validated.append((product_id, quantity, product["price"]))
                total_amount += float(product["price"]) * quantity

            cur.execute(
                "INSERT INTO credit_orders (customer_name, total_amount) VALUES (%s, %s) RETURNING id",
                (customer_name, round(total_amount, 2)),
            )
            order_id = cur.fetchone()["id"]
            for product_id, quantity, unit_price in validated:
                cur.execute(
                    """
                    INSERT INTO credit_order_items
                        (credit_order_id, product_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (order_id, product_id, quantity, unit_price),
                )
                cur.execute(
                    "UPDATE products SET stock = stock - %s WHERE id = %s",
                    (quantity, product_id),
                )
            conn.commit()
            return order_id, round(total_amount, 2)
        finally:
            cur.close()

    for item in cart:
        product_id = item.get("id")
        quantity = item.get("quantity", 0)
        if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
            raise ValueError("Yanlış məhsul məlumatı")
        product = conn.execute(
            "SELECT id, name, price, stock FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if product is None:
            raise ValueError("Məhsul tapılmadı")
        if quantity > product["stock"]:
            raise ValueError(f"{product['name']} üçün kifayət qədər stok yoxdur.")
        validated.append((product_id, quantity, product["price"]))
        total_amount += float(product["price"]) * quantity

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO credit_orders (customer_name, total_amount) VALUES (?, ?)",
        (customer_name, round(total_amount, 2)),
    )
    order_id = cursor.lastrowid
    for product_id, quantity, unit_price in validated:
        cursor.execute(
            """
            INSERT INTO credit_order_items
                (credit_order_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, product_id, quantity, unit_price),
        )
        conn.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (quantity, product_id),
        )
    conn.commit()
    return order_id, round(total_amount, 2)


@app.route("/open-orders")
def open_orders_page():
    """Render open credit orders and the paid credit-order history."""
    init_db()
    return render_template("open_orders.html")


@app.route("/tables")
def tables_page():
    """Render the six-table floor view."""
    init_db()
    return render_template("tables.html")


def _table_order_items(conn, database_url, order_id):
    placeholder = "%s" if database_url else "?"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT toi.product_id, p.name, toi.quantity, toi.unit_price,
                   (toi.quantity * toi.unit_price) AS line_total
            FROM table_order_items toi
            JOIN products p ON p.id = toi.product_id
            WHERE toi.table_order_id = {placeholder}
            ORDER BY toi.id
            """,
            (order_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()


@app.route("/api/tables", methods=["GET"])
def tables_api():
    """Return the six tables and their current open bills."""
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    placeholder = "%s" if database_url else "?"
    tables = []
    cur = conn.cursor()
    try:
        cur.execute("SELECT table_number, name, category FROM dining_tables ORDER BY table_number")
        definitions = cur.fetchall()
        for definition in definitions:
            table_number = _row_value(definition, "table_number")
            cur.execute(
                f"""
                SELECT id, opened_at
                FROM table_orders
                WHERE table_number = {placeholder} AND status = 'open'
                ORDER BY id DESC
                LIMIT 1
                """,
                (table_number,),
            )
            order = cur.fetchone()
            items = _table_order_items(conn, database_url, order["id"]) if order else []
            tables.append(
                {
                    "number": table_number,
                    "name": _row_value(definition, "name"),
                    "category": _row_value(definition, "category"),
                    "occupied": order is not None,
                    "order_id": order["id"] if order else None,
                    "opened_at": str(order["opened_at"]) if order else None,
                    "items": [
                        {
                            "product_id": _row_value(item, "product_id"),
                            "name": _row_value(item, "name"),
                            "quantity": _row_value(item, "quantity"),
                            "unit_price": float(_row_value(item, "unit_price")),
                            "line_total": float(_row_value(item, "line_total")),
                        }
                        for item in items
                    ],
                }
            )
    finally:
        cur.close()
    return jsonify({"success": True, "tables": tables})


@app.route("/api/tables/products", methods=["GET"])
def table_products_api():
    """Return products for the table-order picker."""
    init_db()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, category, price, stock FROM products ORDER BY name")
        products = cur.fetchall()
        return jsonify(
            {
                "success": True,
                "products": [
                    {
                        "id": _row_value(product, "id"),
                        "name": _row_value(product, "name"),
                        "category": _row_value(product, "category"),
                        "price": float(_row_value(product, "price")),
                        "stock": _row_value(product, "stock"),
                    }
                    for product in products
                ],
            }
        )
    finally:
        cur.close()


@app.route("/api/tables/<int:table_number>/items", methods=["POST"])
def add_table_items(table_number):
    """Send products to a table and reserve their stock."""
    data = request.get_json(silent=True) or {}
    cart = data.get("cart", [])
    if not isinstance(cart, list) or not cart:
        return jsonify({"success": False, "message": "Məhsul seçilməyib."}), 400

    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    placeholder = "%s" if database_url else "?"
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT table_number FROM dining_tables WHERE table_number = {placeholder}",
            (table_number,),
        )
        if cur.fetchone() is None:
            return jsonify({"success": False, "message": "Masa tapılmadı."}), 404
        cur.execute(
            f"""
            SELECT id FROM table_orders
            WHERE table_number = {placeholder} AND status = 'open'
            ORDER BY id DESC LIMIT 1
            """,
            (table_number,),
        )
        order = cur.fetchone()
        if order:
            order_id = _row_value(order, "id")
        elif database_url:
            cur.execute(
                "INSERT INTO table_orders (table_number) VALUES (%s) RETURNING id",
                (table_number,),
            )
            order_id = cur.fetchone()["id"]
        else:
            cur.execute("INSERT INTO table_orders (table_number) VALUES (?)", (table_number,))
            order_id = cur.lastrowid

        for item in cart:
            product_id = item.get("id")
            quantity = item.get("quantity")
            if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Yanlış məhsul məlumatı.")
            cur.execute(
                f"SELECT id, price, stock FROM products WHERE id = {placeholder}",
                (product_id,),
            )
            product = cur.fetchone()
            if product is None:
                raise ValueError("Məhsul tapılmadı.")
            if quantity > _row_value(product, "stock"):
                raise ValueError("Stokda kifayət qədər məhsul yoxdur.")
            cur.execute(
                f"""
                SELECT id, quantity FROM table_order_items
                WHERE table_order_id = {placeholder} AND product_id = {placeholder}
                """,
                (order_id, product_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    f"UPDATE table_order_items SET quantity = quantity + {placeholder} WHERE id = {placeholder}",
                    (quantity, _row_value(existing, "id")),
                )
            elif database_url:
                cur.execute(
                    "INSERT INTO table_order_items (table_order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                    (order_id, product_id, quantity, _row_value(product, "price")),
                )
            else:
                cur.execute(
                    "INSERT INTO table_order_items (table_order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (order_id, product_id, quantity, _row_value(product, "price")),
                )
            cur.execute(
                f"UPDATE products SET stock = stock - {placeholder} WHERE id = {placeholder}",
                (quantity, product_id),
            )
        conn.commit()
        return jsonify({"success": True, "message": "Məhsullar masaya göndərildi."})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Masa sifarişi yazılarkən xəta: {exc}"}), 500
    finally:
        cur.close()


@app.route("/api/tables/<int:table_number>/close", methods=["POST"])
def close_table(table_number):
    """Close a table bill and record it as a completed sale."""
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    placeholder = "%s" if database_url else "?"
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT id FROM table_orders WHERE table_number = {placeholder} AND status = 'open' ORDER BY id DESC LIMIT 1",
            (table_number,),
        )
        order = cur.fetchone()
        if not order:
            return jsonify({"success": False, "message": "Bu masa boşdur."}), 400
        order_id = _row_value(order, "id")
        items = _table_order_items(conn, database_url, order_id)
        if not items:
            return jsonify({"success": False, "message": "Masada məhsul yoxdur."}), 400
        total = sum(float(_row_value(item, "line_total")) for item in items)
        if database_url:
            cur.execute("INSERT INTO sales (total_amount) VALUES (%s) RETURNING id", (total,))
            sale_id = cur.fetchone()["id"]
        else:
            cur.execute("INSERT INTO sales (total_amount) VALUES (?)", (total,))
            sale_id = cur.lastrowid
        for item in items:
            if database_url:
                cur.execute(
                    "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                    (sale_id, _row_value(item, "product_id"), _row_value(item, "quantity"), _row_value(item, "unit_price")),
                )
            else:
                cur.execute(
                    "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (sale_id, _row_value(item, "product_id"), _row_value(item, "quantity"), _row_value(item, "unit_price")),
                )
        cur.execute(
            f"UPDATE table_orders SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = {placeholder}",
            (order_id,),
        )
        conn.commit()
        return jsonify({"success": True, "sale_id": sale_id, "total": round(total, 2), "message": "Masa hesabı bağlandı."})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Hesab bağlanarkən xəta: {exc}"}), 500
    finally:
        cur.close()


@app.route("/api/table-categories", methods=["POST"])
def add_table_category():
    init_db()
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "message": "Masa kateqoriyası adı vacibdir."}), 400
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        if database_url:
            cur.execute("INSERT INTO table_categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
        else:
            cur.execute("INSERT OR IGNORE INTO table_categories (name) VALUES (?)", (name,))
        conn.commit()
        return jsonify({"success": True, "category": name})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        cur.close()


@app.route("/api/table-categories/<category_name>", methods=["PUT", "DELETE"])
def manage_table_category(category_name):
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    old_name = category_name.strip()
    data = request.get_json(silent=True) or {}
    cur = conn.cursor()
    try:
        if request.method == "PUT":
            new_name = str(data.get("new_name", "")).strip()
            if not new_name:
                return jsonify({"success": False, "message": "Yeni kateqoriya adı vacibdir."}), 400
            if database_url:
                cur.execute("UPDATE table_categories SET name = %s WHERE name = %s", (new_name, old_name))
                cur.execute("UPDATE dining_tables SET category = %s WHERE category = %s", (new_name, old_name))
            else:
                cur.execute("UPDATE table_categories SET name = ? WHERE name = ?", (new_name, old_name))
                cur.execute("UPDATE dining_tables SET category = ? WHERE category = ?", (new_name, old_name))
            conn.commit()
            return jsonify({"success": True, "category": new_name})
        if database_url:
            if old_name == "Standart":
                return jsonify({"success": False, "message": "Standart kateqoriyası silinə bilməz."}), 400
            cur.execute("SELECT COUNT(*) AS count FROM table_categories")
            if _row_value(cur.fetchone(), "count") <= 1:
                return jsonify({"success": False, "message": "Son masa kateqoriyası silinə bilməz."}), 400
            cur.execute("UPDATE dining_tables SET category = 'Standart' WHERE category = %s", (old_name,))
            cur.execute("DELETE FROM table_categories WHERE name = %s", (old_name,))
        else:
            if old_name == "Standart":
                return jsonify({"success": False, "message": "Standart kateqoriyası silinə bilməz."}), 400
            cur.execute("SELECT COUNT(*) AS count FROM table_categories")
            if _row_value(cur.fetchone(), "count") <= 1:
                return jsonify({"success": False, "message": "Son masa kateqoriyası silinə bilməz."}), 400
            cur.execute("UPDATE dining_tables SET category = 'Standart' WHERE category = ?", (old_name,))
            cur.execute("DELETE FROM table_categories WHERE name = ?", (old_name,))
        conn.commit()
        return jsonify({"success": True, "category": old_name})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        cur.close()


@app.route("/api/dining-tables", methods=["POST"])
def add_dining_table():
    init_db()
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "Standart") or "Standart").strip()
    if not name:
        return jsonify({"success": False, "message": "Masa adı vacibdir."}), 400
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(MAX(table_number), 0) + 1 AS number FROM dining_tables")
        number = int(_row_value(cur.fetchone(), "number"))
        if database_url:
            cur.execute("INSERT INTO dining_tables (table_number, name, category) VALUES (%s, %s, %s)", (number, name, category))
        else:
            cur.execute("INSERT INTO dining_tables (table_number, name, category) VALUES (?, ?, ?)", (number, name, category))
        conn.commit()
        return jsonify({"success": True, "table_number": number})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        cur.close()


@app.route("/api/dining-tables/<int:table_number>", methods=["PUT", "DELETE"])
def manage_dining_table(table_number):
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    placeholder = "%s" if database_url else "?"
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT id FROM table_orders WHERE table_number = {placeholder} AND status = 'open' LIMIT 1",
            (table_number,),
        )
        if request.method == "DELETE" and cur.fetchone():
            return jsonify({"success": False, "message": "Dolu masa silinə bilməz. Əvvəl hesabı bağlayın."}), 400
        if request.method == "PUT":
            data = request.get_json(silent=True) or {}
            name = str(data.get("name", "")).strip()
            category = str(data.get("category", "Standart") or "Standart").strip()
            if not name:
                return jsonify({"success": False, "message": "Masa adı vacibdir."}), 400
            if database_url:
                cur.execute("UPDATE dining_tables SET name = %s, category = %s WHERE table_number = %s", (name, category, table_number))
            else:
                cur.execute("UPDATE dining_tables SET name = ?, category = ? WHERE table_number = ?", (name, category, table_number))
            if cur.rowcount == 0:
                return jsonify({"success": False, "message": "Masa tapılmadı."}), 404
            conn.commit()
            return jsonify({"success": True})
        cur.execute(f"DELETE FROM dining_tables WHERE table_number = {placeholder}", (table_number,))
        if cur.rowcount == 0:
            return jsonify({"success": False, "message": "Masa tapılmadı."}), 404
        conn.commit()
        return jsonify({"success": True})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        cur.close()


@app.route("/api/credit-orders", methods=["GET", "POST"])
def credit_orders_api():
    """List credit orders or create a new open order from a cart."""
    conn = get_db()
    database_url, _ = get_db_config()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        customer_name = str(data.get("customer_name", "")).strip()
        cart = data.get("cart", [])
        if not customer_name:
            return jsonify({"success": False, "message": "Müştərinin adı vacibdir."}), 400
        if len(customer_name) > 200:
            return jsonify({"success": False, "message": "Müştəri adı çox uzundur."}), 400
        if not isinstance(cart, list) or not cart:
            return jsonify({"success": False, "message": "Səbət boşdur."}), 400
        try:
            order_id, total = _create_credit_order(conn, database_url, customer_name, cart)
            return jsonify(
                {"success": True, "id": order_id, "total": total, "message": "Açıq sifariş saxlanıldı."}
            )
        except ValueError as exc:
            conn.rollback()
            return jsonify({"success": False, "message": str(exc)}), 400
        except (sqlite3.Error, psycopg2.Error) as exc:
            conn.rollback()
            return jsonify({"success": False, "message": f"Sifariş saxlanarkən xəta: {exc}"}), 500

    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, customer_name, status, total_amount, paid_amount, created_at, paid_at
                FROM credit_orders
                ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, created_at DESC
                """
            )
            orders = cur.fetchall()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, customer_name, status, total_amount, paid_amount, created_at, paid_at
                FROM credit_orders
                ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, created_at DESC
                """
            )
            orders = cur.fetchall()
        finally:
            cur.close()

    result = []
    for order in orders:
        order_id = _row_value(order, "id")
        result.append(
            {
                "id": order_id,
                "customer_name": _row_value(order, "customer_name"),
                "status": _row_value(order, "status"),
                "total_amount": float(_row_value(order, "total_amount")),
                "paid_amount": float(_row_value(order, "paid_amount")),
                "remaining_amount": max(
                    0,
                    round(
                        float(_row_value(order, "total_amount"))
                        - float(_row_value(order, "paid_amount")),
                        2,
                    ),
                ),
                "created_at": str(_row_value(order, "created_at")),
                "paid_at": (
                    str(_row_value(order, "paid_at"))
                    if _row_value(order, "paid_at")
                    else None
                ),
                "items": [
                    {
                        "product_id": _row_value(item, "product_id"),
                        "name": _row_value(item, "name"),
                        "quantity": _row_value(item, "quantity"),
                        "unit_price": float(_row_value(item, "unit_price")),
                        "line_total": float(_row_value(item, "line_total")),
                    }
                    for item in _credit_order_items(conn, database_url, order_id)
                ],
            }
        )
    return jsonify({"success": True, "orders": result})


@app.route("/api/credit-orders/<int:order_id>/items", methods=["POST"])
def add_credit_order_items(order_id):
    """Add more products to an existing open credit order."""
    data = request.get_json(silent=True) or {}
    cart = data.get("cart", [])
    if not isinstance(cart, list) or not cart:
        return jsonify({"success": False, "message": "Səbət boşdur."}), 400

    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        if database_url:
            cur.execute("SELECT status FROM credit_orders WHERE id = %s FOR UPDATE", (order_id,))
            order = cur.fetchone()
        else:
            cur.execute("SELECT status FROM credit_orders WHERE id = ?", (order_id,))
            order = cur.fetchone()
        if order is None:
            raise ValueError("Açıq sifariş tapılmadı.")
        if _row_value(order, "status") != "open":
            raise ValueError("Ödənilmiş sifarişə məhsul əlavə etmək olmaz.")

        total = 0.0
        validated = []
        for item in cart:
            product_id = item.get("id")
            quantity = item.get("quantity", 0)
            if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Yanlış məhsul məlumatı")
            if database_url:
                cur.execute(
                    "SELECT id, name, price, stock FROM products WHERE id = %s FOR UPDATE",
                    (product_id,),
                )
                product = cur.fetchone()
            else:
                cur.execute(
                    "SELECT id, name, price, stock FROM products WHERE id = ?",
                    (product_id,),
                )
                product = cur.fetchone()
            if product is None:
                raise ValueError("Məhsul tapılmadı")
            if quantity > _row_value(product, "stock"):
                raise ValueError(
                    f"{_row_value(product, 'name')} üçün kifayət qədər stok yoxdur."
                )
            unit_price = _row_value(product, "price")
            validated.append((product_id, quantity, unit_price))
            total += float(unit_price) * quantity

        for product_id, quantity, unit_price in validated:
            if database_url:
                cur.execute(
                    """
                    INSERT INTO credit_order_items
                        (credit_order_id, product_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (order_id, product_id, quantity, unit_price),
                )
                cur.execute(
                    "UPDATE products SET stock = stock - %s WHERE id = %s",
                    (quantity, product_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO credit_order_items
                        (credit_order_id, product_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order_id, product_id, quantity, unit_price),
                )
                cur.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (quantity, product_id),
                )
        if database_url:
            cur.execute(
                "UPDATE credit_orders SET total_amount = total_amount + %s WHERE id = %s",
                (round(total, 2), order_id),
            )
        else:
            cur.execute(
                "UPDATE credit_orders SET total_amount = total_amount + ? WHERE id = ?",
                (round(total, 2), order_id),
            )
        conn.commit()
        return jsonify({"success": True, "total_added": round(total, 2)})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Sifariş yenilənərkən xəta: {exc}"}), 500
    finally:
        cur.close()


@app.route("/api/credit-orders/<int:order_id>/pay", methods=["POST"])
def pay_credit_order(order_id):
    """Apply a partial payment or close an open credit order."""
    conn = get_db()
    database_url, _ = get_db_config()
    data = request.get_json(silent=True) or {}
    amount_raw = data.get("amount")
    if amount_raw is None:
        return jsonify({"success": False, "message": "Ödəniş məbləği düzgün deyil."}), 400
    try:
        payment_amount = round(float(amount_raw), 2)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Ödəniş məbləği düzgün deyil."}), 400
    if payment_amount <= 0:
        return jsonify({"success": False, "message": "Ödəniş məbləği 0-dan böyük olmalıdır."}), 400

    cur = conn.cursor()
    try:
        if database_url:
            cur.execute(
                """
                SELECT total_amount, paid_amount
                FROM credit_orders
                WHERE id = %s AND status = 'open'
                FOR UPDATE
                """,
                (order_id,),
            )
        else:
            cur.execute(
                """
                SELECT total_amount, paid_amount
                FROM credit_orders
                WHERE id = ? AND status = 'open'
                """,
                (order_id,),
            )
        order = cur.fetchone()
        if order is None:
            raise ValueError("Açıq sifariş tapılmadı və ya artıq ödənilib.")
        total_amount = float(_row_value(order, "total_amount"))
        paid_amount = float(_row_value(order, "paid_amount"))
        remaining_amount = round(total_amount - paid_amount, 2)
        if payment_amount > remaining_amount:
            raise ValueError(f"Maksimum ödəniş {remaining_amount:.2f} AZN ola bilər.")
        new_paid_amount = round(paid_amount + payment_amount, 2)
        is_paid = new_paid_amount >= total_amount
        if database_url:
            cur.execute(
                """
                UPDATE credit_orders
                SET paid_amount = %s,
                    status = CASE WHEN %s >= total_amount THEN 'paid' ELSE 'open' END,
                    paid_at = CASE WHEN %s >= total_amount THEN CURRENT_TIMESTAMP ELSE paid_at END
                WHERE id = %s
                """,
                (new_paid_amount, new_paid_amount, new_paid_amount, order_id),
            )
        else:
            cur.execute(
                """
                UPDATE credit_orders
                SET paid_amount = ?,
                    status = CASE WHEN ? >= total_amount THEN 'paid' ELSE 'open' END,
                    paid_at = CASE WHEN ? >= total_amount THEN CURRENT_TIMESTAMP ELSE paid_at END
                WHERE id = ?
                """,
                (new_paid_amount, new_paid_amount, new_paid_amount, order_id),
            )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "Sifariş tam ödənildi." if is_paid else "Hissəli ödəniş qeydə alındı.",
                "paid_amount": new_paid_amount,
                "remaining_amount": round(total_amount - new_paid_amount, 2),
                "status": "paid" if is_paid else "open",
            }
        )
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Ödəniş bağlanarkən xəta: {exc}"}), 500
    finally:
        cur.close()


@app.route('/add_product', methods=['POST'])
def add_product():
    """API endpoint to add a new product.

    Accepts JSON: {name, category, price, stock, image_url} and inserts a new
    product row, returning the created product id.
    """
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    category = str(data.get('category', 'Other') or 'Other').strip() or 'Other'
    try:
        price = float(data.get('price', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid price'}), 400
    try:
        stock = int(data.get('stock', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid stock'}), 400
    image_url = data.get('image_url')
    if not name:
        return jsonify({'success': False, 'message': 'Məhsul adı vacibdir'}), 400

    conn = get_db()
    database_url, _ = get_db_config()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO products (name, category, price, stock, image_url) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (name, category, price, stock, image_url),
                )
                row = cur.fetchone()
                if row is None:
                    new_id = None
                elif isinstance(row, dict):
                    new_id = row.get('id')
                else:
                    new_id = row[0]
                _ensure_category(conn, database_url, category)
                _audit_event(conn, database_url, "product_created", "product", new_id, name)
                conn.commit()
                return jsonify({'success': True, 'id': new_id})
            finally:
                cur.close()
        else:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO products (name, category, price, stock, image_url) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (name, category, price, stock, image_url),
                )
                new_id = cur.lastrowid
                _ensure_category(conn, database_url, category)
                _audit_event(conn, database_url, "product_created", "product", new_id, name)
                conn.commit()
                return jsonify({'success': True, 'id': new_id})
            finally:
                cur.close()
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product record."""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    category = str(data.get('category', 'Other') or 'Other').strip() or 'Other'
    try:
        price = float(data.get('price', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid price'}), 400
    try:
        stock = int(data.get('stock', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid stock'}), 400
    image_url = data.get('image_url')
    if not name:
        return jsonify({'success': False, 'message': 'Məhsul adı vacibdir'}), 400

    conn = get_db()
    database_url, _ = get_db_config()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE products SET name = %s, category = %s, price = %s, stock = %s, image_url = %s WHERE id = %s",
                    (name, category, price, stock, image_url, product_id),
                )
                if cur.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Məhsul tapılmadı'}), 404
                _ensure_category(conn, database_url, category)
                _audit_event(conn, database_url, "product_updated", "product", product_id, name)
                conn.commit()
                return jsonify({'success': True, 'id': product_id})
            finally:
                cur.close()
        else:
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE products SET name = ?, category = ?, price = ?, stock = ?, image_url = ? WHERE id = ?",
                    (name, category, price, stock, image_url, product_id),
                )
                if cur.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Məhsul tapılmadı'}), 404
                _ensure_category(conn, database_url, category)
                _audit_event(conn, database_url, "product_updated", "product", product_id, name)
                conn.commit()
                return jsonify({'success': True, 'id': product_id})
            finally:
                cur.close()
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product and any related stock/sale records."""
    conn = get_db()
    database_url, _ = get_db_config()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM sale_items WHERE product_id = %s", (product_id,))
                cur.execute("DELETE FROM stock_movements WHERE product_id = %s", (product_id,))
                cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
                if cur.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Məhsul tapılmadı'}), 404
                _audit_event(conn, database_url, "product_deleted", "product", product_id)
                conn.commit()
                return jsonify({'success': True})
            finally:
                cur.close()
        else:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM sale_items WHERE product_id = ?", (product_id,))
                cur.execute("DELETE FROM stock_movements WHERE product_id = ?", (product_id,))
                cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
                if cur.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Məhsul tapılmadı'}), 404
                _audit_event(conn, database_url, "product_deleted", "product", product_id)
                conn.commit()
                return jsonify({'success': True})
            finally:
                cur.close()
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route("/api/audit-log")
def audit_log_api():
    """Return recent audit events for managers."""
    if session.get("role") != "manager":
        return jsonify({"success": False, "message": "Bu bölmə yalnız müdir üçündür."}), 403
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        if database_url:
            cur.execute(
                """
                SELECT id, actor_role, action, entity_type, entity_id, details, created_at
                FROM audit_log ORDER BY created_at DESC LIMIT 200
                """
            )
        else:
            cur.execute(
                """
                SELECT id, actor_role, action, entity_type, entity_id, details, created_at
                FROM audit_log ORDER BY created_at DESC LIMIT 200
                """
            )
        events = cur.fetchall()
        return jsonify(
            {
                "success": True,
                "events": [
                    {
                        "id": _row_value(event, "id"),
                        "actor_role": _row_value(event, "actor_role"),
                        "action": _row_value(event, "action"),
                        "entity_type": _row_value(event, "entity_type"),
                        "entity_id": _row_value(event, "entity_id"),
                        "details": _row_value(event, "details"),
                        "created_at": str(_row_value(event, "created_at")),
                    }
                    for event in events
                ],
            }
        )
    finally:
        cur.close()


@app.route('/api/categories', methods=['POST'])
def add_category():
    """Add a new category name."""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'success': False, 'message': 'Kateqoriya adı vacibdir'}), 400

    conn = get_db()
    database_url, _ = get_db_config()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )
                conn.commit()
            finally:
                cur.close()
        else:
            cur = conn.cursor()
            try:
                cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
                conn.commit()
            finally:
                cur.close()
        return jsonify({'success': True, 'category': name})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route('/api/categories/<category_name>', methods=['PUT'])
def rename_category(category_name):
    """Rename a category and update any products that use it."""
    data = request.get_json(silent=True) or {}
    new_name = str(data.get('new_name', '')).strip()
    old_name = category_name.strip()
    if not new_name:
        return jsonify({'success': False, 'message': 'Yeni kateqoriya adı vacibdir'}), 400

    conn = get_db()
    database_url, _ = get_db_config()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute("UPDATE products SET category = %s WHERE category = %s", (new_name, old_name))
                cur.execute("UPDATE categories SET name = %s WHERE name = %s", (new_name, old_name))
                if cur.rowcount == 0:
                    pass
                _ensure_category(conn, database_url, new_name)
                conn.commit()
            finally:
                cur.close()
        else:
            cur = conn.cursor()
            try:
                cur.execute("UPDATE products SET category = ? WHERE category = ?", (new_name, old_name))
                cur.execute("UPDATE categories SET name = ? WHERE name = ?", (new_name, old_name))
                _ensure_category(conn, database_url, new_name)
                conn.commit()
            finally:
                cur.close()
        return jsonify({'success': True, 'category': new_name})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


@app.route('/api/categories/<category_name>', methods=['DELETE'])
def delete_category(category_name):
    """Delete a category by moving its products to Other."""
    conn = get_db()
    database_url, _ = get_db_config()
    old_name = category_name.strip()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute("UPDATE products SET category = %s WHERE category = %s", ('Other', old_name))
                cur.execute("DELETE FROM categories WHERE name = %s", (old_name,))
                _ensure_category(conn, database_url, 'Other')
                conn.commit()
            finally:
                cur.close()
        else:
            cur = conn.cursor()
            try:
                cur.execute("UPDATE products SET category = ? WHERE category = ?", ('Other', old_name))
                cur.execute("DELETE FROM categories WHERE name = ?", (old_name,))
                _ensure_category(conn, database_url, 'Other')
                conn.commit()
            finally:
                cur.close()
        return jsonify({'success': True, 'category': old_name})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500


if __name__ == "__main__":
    # Read port from environment (e.g., Railway provides $PORT). Fallback to 5000 for local dev.
    port = int(os.getenv("PORT", "5000"))
    # Allow controlling debug mode via FLASK_DEBUG env var (optional)
    debug_env = os.getenv("FLASK_DEBUG", "False").lower() in ("1", "true", "yes")
    app.run(debug=debug_env, host="0.0.0.0", port=port)
