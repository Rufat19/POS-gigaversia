"""POS simple Flask application: products listing, cart checkout and basic DB setup.

This module provides endpoints to render a product kiosk-style frontend and to
process an in-memory cart via /checkout. It supports SQLite (local) and
PostgreSQL (via DATABASE_URL).
"""

import os
import html
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import getaddresses
from datetime import datetime, timedelta, timezone
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
from click import ClickException
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
BAKU_TIMEZONE = timezone(timedelta(hours=4), name="AZT")
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


@app.errorhandler(403)
def forbidden_page(error):
    """Show a useful access message instead of the server's generic 403 page."""
    return render_template(
        "forbidden.html",
        role=session.get("role"),
        is_admin=session.get("role") == "admin",
    ), 403

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
    "radio": True,
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
            cursor = conn.cursor()
            try:
                cursor.execute("SET TIME ZONE 'UTC'")
            finally:
                cursor.close()
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
        cur.execute(
            "SELECT products, tables, open_orders, operations, reports, radio "
            "FROM feature_permissions WHERE id = 1"
        )
        row = cur.fetchone()
        if row is None:
            return FEATURE_DEFAULTS.copy()
        return {
            "products": bool(_row_value(row, "products")),
            "tables": bool(_row_value(row, "tables")),
            "open_orders": bool(_row_value(row, "open_orders")),
            "operations": bool(_row_value(row, "operations")),
            "reports": bool(_row_value(row, "reports")),
            "radio": bool(_row_value(row, "radio")),
        }
    finally:
        cur.close()


def _feature_for_endpoint(endpoint):
    if endpoint in {"products_page", "checkout"} or endpoint in {
        "add_product", "update_product", "delete_product", "archive_all_products"
    }:
        return "products"
    if endpoint == "clear_stock_history":
        return "operations"
    if endpoint == "clear_debt_history":
        return "open_orders"
    if endpoint in {
        "tables_page", "tables_api", "table_products_api", "add_table_items",
        "close_table", "table_credit",
    }:
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
    if "db" not in g:
        return {"feature_enabled": lambda feature: True}
    database_url, _ = get_db_config()
    permissions = _get_permissions(g.db, database_url)
    if role == "admin":
        return {
            "feature_enabled": lambda feature: (
                permissions.get(feature, True) if feature == "radio" else True
            )
        }
    return {"feature_enabled": lambda feature: permissions.get(feature, True)}


@app.before_request
def enforce_access():
    """Restrict pages based on the logged-in user role."""
    if request.endpoint in {None, 'static', 'login_page', 'logout'}:
        return None
    if not session.get('role'):
        if request.path.startswith("/api/") or request.method != "GET":
            return jsonify({
                "success": False,
                "message": "Daxil olmaq üçün sistemə giriş edin.",
            }), 401
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
        'archive_all_products',
        'clear_stock_history',
        'clear_sales_history',
        'clear_debt_history',
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
        role = PIN_USERS.get(pin)
        username = None
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT username, role, pin_hash FROM users WHERE active = TRUE"
                if database_url
                else "SELECT username, role, pin_hash FROM users WHERE active = 1"
            )
            for user in cur.fetchall():
                if check_password_hash(_row_value(user, "pin_hash"), pin):
                    username = _row_value(user, "username")
                    role = _row_value(user, "role")
                    break
        finally:
            cur.close()
        if role:
            session.clear()
            session['role'] = role
            session['username'] = username or ("Admin" if role == "admin" else role.title())
            _audit_event(conn, database_url, "login", "session", details=role)
            conn.commit()
            return redirect(url_for('products_page'))
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
                image_url TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
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
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
        )

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
                reports BOOLEAN NOT NULL DEFAULT TRUE,
                radio BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        cur.execute(
            "ALTER TABLE feature_permissions ADD COLUMN IF NOT EXISTS radio BOOLEAN NOT NULL DEFAULT TRUE"
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                role VARCHAR(20) NOT NULL CHECK (role IN ('seller', 'manager')),
                pin_hash TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

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
                image_url TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
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
        if 'is_active' not in cols:
            cur.execute("ALTER TABLE products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

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
                reports INTEGER NOT NULL DEFAULT 1,
                radio INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute("PRAGMA table_info(feature_permissions)")
        permission_columns = {row[1] for row in cur.fetchall()}
        if "radio" not in permission_columns:
            cur.execute(
                "ALTER TABLE feature_permissions ADD COLUMN radio INTEGER NOT NULL DEFAULT 1"
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK (role IN ('seller', 'manager')),
                pin_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


def _sync_categories(conn, database_url):
    """Add categories found on products without deleting unused categories."""
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
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_active = TRUE")
            existing = {
                row["category"] for row in cur.fetchall()
                if row and row["category"]
            }
            for name in sorted(existing):
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_active = 1")
            existing = {row[0] for row in cur.fetchall() if row and row[0]}
            for name in sorted(existing):
                cur.execute(
                    "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (name,),
                )
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
            cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_active = TRUE ORDER BY category")
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
        cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_active = 1 ORDER BY category")
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
    _seed_default_products(conn, database_url)
    _sync_categories(conn, database_url)
    _sync_table_definitions(conn, database_url)
    _sync_default_users(conn, database_url)


def _seed_default_products(conn, database_url):
    """Seed defaults once without restoring renamed or archived products."""
    cur = conn.cursor()
    placeholder = "%s" if database_url else "?"
    try:
        if database_url:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS default_product_seeds (
                    name VARCHAR(200) PRIMARY KEY
                )
                """
            )
            cur.execute("LOCK TABLE default_product_seeds IN EXCLUSIVE MODE")
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS default_product_seeds (
                    name TEXT PRIMARY KEY
                )
                """
            )

        cur.execute("SELECT COUNT(*) AS count FROM products")
        products_exist = int(_row_value(cur.fetchone(), "count")) > 0
        cur.execute("SELECT COUNT(*) AS count FROM default_product_seeds")
        seeds_exist = int(_row_value(cur.fetchone(), "count")) > 0

        if not seeds_exist and products_exist:
            for product in DEFAULT_PRODUCTS:
                if database_url:
                    cur.execute(
                        "INSERT INTO default_product_seeds (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (product[0],),
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO default_product_seeds (name) VALUES (?)",
                        (product[0],),
                    )
        elif not seeds_exist:
            for product in DEFAULT_PRODUCTS:
                if database_url:
                    cur.execute(
                        "INSERT INTO products (name, category, price, stock, image_url) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        product,
                    )
                    cur.execute(
                        "INSERT INTO default_product_seeds (name) VALUES (%s)",
                        (product[0],),
                    )
                else:
                    cur.execute(
                        "INSERT INTO products (name, category, price, stock, image_url) "
                        "VALUES (?, ?, ?, ?, ?)",
                        product,
                    )
                    cur.execute(
                        "INSERT INTO default_product_seeds (name) VALUES (?)",
                        (product[0],),
                    )
        else:
            cur.execute("SELECT name FROM default_product_seeds")
            seeded_names = {
                str(_row_value(row, "name")) for row in cur.fetchall()
            }
            cur.execute("SELECT name FROM products")
            existing_names = {
                str(_row_value(row, "name")) for row in cur.fetchall()
            }
            for product in DEFAULT_PRODUCTS:
                if product[0] in seeded_names:
                    continue
                if product[0] not in existing_names:
                    cur.execute(
                        f"INSERT INTO products (name, category, price, stock, image_url) "
                        f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                        product,
                    )
                if database_url:
                    cur.execute(
                        "INSERT INTO default_product_seeds (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (product[0],),
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO default_product_seeds (name) VALUES (?)",
                        (product[0],),
                    )
        conn.commit()
    finally:
        cur.close()


def _sync_default_users(conn, database_url):
    defaults = (
        ("Satıcı", "seller", seller_pin or "1111"),
        ("Müdir", "manager", manager_pin or "1991"),
    )
    cur = conn.cursor()
    try:
        for username, role, pin in defaults:
            placeholder = "%s" if database_url else "?"
            cur.execute(
                f"SELECT id FROM users WHERE role = {placeholder} LIMIT 1",
                (role,),
            )
            if cur.fetchone() is None:
                if database_url:
                    cur.execute(
                        "INSERT INTO users (username, role, pin_hash) VALUES (%s, %s, %s)",
                        (username, role, generate_password_hash(pin)),
                    )
                else:
                    cur.execute(
                        "INSERT INTO users (username, role, pin_hash) VALUES (?, ?, ?)",
                        (username, role, generate_password_hash(pin)),
                    )
        conn.commit()
    finally:
        cur.close()


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
            cur.execute("SELECT id, name, category, price, stock, image_url FROM products WHERE is_active = TRUE ORDER BY id")
            products = cur.fetchall()
        finally:
            cur.close()
    else:
        products_sql = (
            "SELECT id, name, category, price, stock, image_url "
            "FROM products WHERE is_active = 1 ORDER BY id"
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
    """Render operations page: add and review stock movements."""
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    end = datetime.now(BAKU_TIMEZONE).date()
    start = end - timedelta(days=6)

    # load products for dropdown
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, category, price, stock, image_url "
                "FROM products WHERE is_active = TRUE ORDER BY name"
            )
            products = cur.fetchall()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, category, price, stock, image_url "
                "FROM products WHERE is_active = 1 ORDER BY name"
            )
            products = cur.fetchall()
        finally:
            cur.close()

    # Stock movement history stays separate from the sales history page.
    history = []
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
    return render_template(
        'operations.html',
        products=products,
        history=history,
        categories=categories,
        default_start=start.isoformat(),
        default_end=end.isoformat(),
    )


@app.route('/sales-history')
def sales_history_page():
    """Show completed sales to every authenticated role, filtered by date."""
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    today = datetime.now(BAKU_TIMEZONE).date()
    default_start = today.isoformat()
    default_end = today.isoformat()
    start_value = request.args.get("start_date", default_start)
    end_value = request.args.get("end_date", default_end)

    try:
        start_date = datetime.strptime(start_value, "%Y-%m-%d").date() if start_value else None
        end_date = datetime.strptime(end_value, "%Y-%m-%d").date() if end_value else None
    except ValueError:
        abort(400, description="Tarix YYYY-MM-DD formatında olmalıdır.")
    if start_date and end_date and start_date > end_date:
        abort(400, description="Başlanğıc tarixi bitmə tarixindən sonra ola bilməz.")

    placeholder = "%s" if database_url else "?"
    local_created_at = (
        "(s.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Baku')"
        if database_url
        else "datetime(s.created_at, '+4 hours')"
    )
    date_expression = (
        f"{local_created_at}::date" if database_url else f"DATE({local_created_at})"
    )
    date_conditions = []
    parameters = []
    if start_date:
        date_conditions.append(f"{date_expression} >= {placeholder}")
        parameters.append(start_date.isoformat())
    if end_date:
        date_conditions.append(f"{date_expression} <= {placeholder}")
        parameters.append(end_date.isoformat())
    where_clause = " AND ".join(["s.status = 'completed'", *date_conditions])

    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT {local_created_at} AS created_at,
                   p.name AS product_name,
                   si.quantity AS quantity,
                   (si.unit_price * si.quantity) AS amount
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE {where_clause}
            ORDER BY s.created_at DESC, s.id DESC, si.id DESC
            """,
            tuple(parameters),
        )
        sales = cur.fetchall()
    finally:
        cur.close()

    return render_template(
        "sales_history.html",
        sales=sales,
        sales_count=len(sales),
        start_date=start_value,
        end_date=end_value,
        default_start=default_start,
        default_end=default_end,
    )


def _query_reports_postgres(conn, start_date, end_date):
    cur = conn.cursor()
    try:
        local_created_at = (
            "(s.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Baku')"
        )
        local_created_date = f"{local_created_at}::date"
        cur.execute(
            f"""
            SELECT p.id,
                   p.name,
                   SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND {local_created_date} BETWEEN %s AND %s
            GROUP BY p.id, p.name
            ORDER BY total_qty DESC
            """,
            (start_date, end_date),
        )
        prod_totals = cur.fetchall()

        cur.execute(
            f"""
            SELECT p.category,
                   SUM(si.quantity * si.unit_price) AS total_amount
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND {local_created_date} BETWEEN %s AND %s
            GROUP BY p.category
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        )
        cat_break = cur.fetchall()

        cur.execute(
            f"""
            SELECT DATE_TRUNC('day', {local_created_at}) AS day,
                   SUM(si.quantity * si.unit_price) AS total
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.status = 'completed' AND {local_created_date} BETWEEN %s AND %s
            GROUP BY day
            ORDER BY day ASC
            """,
            (start_date, end_date),
        )
        daily = cur.fetchall()

        cur.execute(
            f"""
            SELECT p.name, SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND {local_created_date} BETWEEN %s AND %s
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
        local_created_at = "datetime(s.created_at, '+4 hours')"
        local_created_date = f"DATE({local_created_at})"
        cur.execute(
            f"""
            SELECT p.id, p.name, SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.status = 'completed' AND {local_created_date} BETWEEN ? AND ?
            GROUP BY p.id, p.name
            ORDER BY total_qty DESC
            """,
            (start_date, end_date),
        )
        prod_totals = cur.fetchall()

        cur.execute(
            f"""
            SELECT p.category, SUM(si.quantity * si.unit_price) AS total_amount
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE {local_created_date} BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        )
        cat_break = cur.fetchall()

        cur.execute(
            f"""
            SELECT {local_created_date} AS day,
                   SUM(si.quantity * si.unit_price) AS total
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE {local_created_date} BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day ASC
            """,
            (start_date, end_date),
        )
        daily = cur.fetchall()

        cur.execute(
            f"""
            SELECT p.name, SUM(si.quantity) AS total_qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE {local_created_date} BETWEEN ? AND ?
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

    active_value = "TRUE" if placeholder == "%s" else "1"
    select_sql = f'SELECT stock, name FROM products WHERE id = {placeholder} AND is_active = {active_value}'
    insert_sql = (
        f'INSERT INTO stock_movements (product_id, type, quantity, note) '
        f'VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})'
        f'{" RETURNING id" if placeholder == "%s" else ""}'
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
    end = datetime.now(BAKU_TIMEZONE).date()
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
    conn = get_db()
    permissions = _get_permissions(conn, database_url)
    report_recipients = _get_app_setting(
        conn, database_url, "daily_report_recipients"
    )
    return render_template(
        "admin.html",
        permissions=permissions,
        report_recipients=report_recipients,
    )


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
                    operations = %s, reports = %s, radio = %s
                WHERE id = 1
                """,
                values,
            )
        else:
            cur.execute(
                """
                UPDATE feature_permissions
                SET products = ?, tables = ?, open_orders = ?,
                    operations = ?, reports = ?, radio = ?
                WHERE id = 1
                """,
                values,
            )
        _audit_event(conn, database_url, "update_permissions", "feature_permissions", details=str(permissions))
        conn.commit()
    finally:
        cur.close()
    return jsonify({"success": True, "permissions": permissions})


def _require_admin():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Yalnız admin bu əməliyyatı edə bilər."}), 403
    return None


def _get_app_setting(conn, database_url, key, default=""):
    cur = conn.cursor()
    try:
        placeholder = "%s" if database_url else "?"
        cur.execute(
            f"SELECT setting_value FROM app_settings WHERE setting_key = {placeholder}",
            (key,),
        )
        row = cur.fetchone()
        return str(_row_value(row, "setting_value")) if row else default
    finally:
        cur.close()


def _set_app_setting(conn, database_url, key, value):
    cur = conn.cursor()
    try:
        if database_url:
            cur.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON CONFLICT (setting_key) DO UPDATE
                SET setting_value = EXCLUDED.setting_value
                """,
                (key, value),
            )
        else:
            cur.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (?, ?)
                ON CONFLICT (setting_key) DO UPDATE
                SET setting_value = excluded.setting_value
                """,
                (key, value),
            )
    finally:
        cur.close()


def _parse_email_recipients(raw_value):
    addresses = [
        address
        for _, address in getaddresses([raw_value.replace(";", ",")])
        if address
    ]
    if len(raw_value) > 2000:
        raise ValueError("E-poçt ünvanları çox uzundur.")
    if any(not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address) for address in addresses):
        raise ValueError("E-poçt ünvanlarından biri düzgün deyil.")
    return list(dict.fromkeys(addresses))


def _smtp_configuration():
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USERNAME", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST və SMTP_FROM (və ya SMTP_USERNAME) dəyişənlərini təyin edin.")
    if bool(username) != bool(password):
        raise RuntimeError("SMTP_USERNAME və SMTP_PASSWORD birlikdə təyin olunmalıdır.")
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        timeout = int(os.getenv("SMTP_TIMEOUT", "20"))
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT və SMTP_TIMEOUT tam ədəd olmalıdır.") from exc
    use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}
    if use_ssl and use_tls:
        raise RuntimeError("SMTP_USE_SSL və SMTP_USE_TLS eyni vaxtda aktiv ola bilməz.")
    if not 1 <= port <= 65535 or timeout <= 0:
        raise RuntimeError("SMTP portu və timeout dəyəri düzgün deyil.")
    return {
        "host": host,
        "port": port,
        "sender": sender,
        "username": username,
        "password": password,
        "timeout": timeout,
        "use_ssl": use_ssl,
        "use_tls": use_tls,
    }


def _send_email(recipients, subject, text_body, html_body):
    config = _smtp_configuration()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["sender"]
    message["To"] = ", ".join(recipients)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    smtp_class = smtplib.SMTP_SSL if config["use_ssl"] else smtplib.SMTP
    smtp_kwargs = {"timeout": config["timeout"]}
    if config["use_ssl"]:
        smtp_kwargs["context"] = context
    with smtp_class(config["host"], config["port"], **smtp_kwargs) as smtp:
        if config["use_tls"]:
            smtp.starttls(context=context)
        if config["username"]:
            smtp.login(config["username"], config["password"])
        smtp.send_message(message)


def _build_daily_email_report(conn, database_url, report_date):
    placeholder = "%s" if database_url else "?"
    local_created_at = (
        "(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Baku')"
        if database_url
        else "datetime(created_at, '+4 hours')"
    )
    local_sales_date = (
        f"(s.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Baku')::date"
        if database_url
        else "DATE(datetime(s.created_at, '+4 hours'))"
    )
    local_credit_date = (
        f"(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Baku')::date"
        if database_url
        else "DATE(datetime(created_at, '+4 hours'))"
    )
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT COUNT(*) AS sale_count,
                   COALESCE(SUM(total_amount), 0) AS sales_total
            FROM sales s
            WHERE s.status = 'completed' AND {local_sales_date} = {placeholder}
            """,
            (report_date.isoformat(),),
        )
        sales_summary = cur.fetchone()
        cur.execute(
            f"""
            SELECT p.name AS product_name,
                   SUM(si.quantity) AS quantity,
                   SUM(si.quantity * si.unit_price) AS amount
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE s.status = 'completed' AND {local_sales_date} = {placeholder}
            GROUP BY p.name
            ORDER BY amount DESC, p.name
            """,
            (report_date.isoformat(),),
        )
        sold_products = cur.fetchall()
        cur.execute(
            f"""
            SELECT customer_name, total_amount, status, {local_created_at} AS local_created_at
            FROM credit_orders
            WHERE {local_credit_date} = {placeholder}
            ORDER BY created_at, id
            """,
            (report_date.isoformat(),),
        )
        debts = cur.fetchall()
        cur.execute(
            """
            SELECT name, category, stock
            FROM products
            WHERE is_active = TRUE
            ORDER BY stock ASC, name
            """
            if database_url
            else """
            SELECT name, category, stock
            FROM products
            WHERE is_active = 1
            ORDER BY stock ASC, name
            """
        )
        stock = cur.fetchall()
    finally:
        cur.close()

    sale_count = int(_row_value(sales_summary, "sale_count") or 0)
    sales_total = float(_row_value(sales_summary, "sales_total") or 0)
    total_debt = sum(float(_row_value(order, "total_amount") or 0) for order in debts)
    date_label = report_date.strftime("%d.%m.%Y")
    text_lines = [
        f"Gündəlik hesabat — {date_label} (Bakı vaxtı)",
        "",
        f"Satış: {sale_count} satış, {sales_total:.2f} AZN",
        "Satılan məhsullar:",
    ]
    if sold_products:
        text_lines.extend(
            f"- {_row_value(item, 'product_name')}: {_row_value(item, 'quantity')} ədəd, "
            f"{float(_row_value(item, 'amount') or 0):.2f} AZN"
            for item in sold_products
        )
    else:
        text_lines.append("- Satış olmayıb")
    text_lines.extend(["", "Yeni borclar:"])
    if debts:
        text_lines.extend(
            f"- {_row_value(order, 'customer_name')}: "
            f"{float(_row_value(order, 'total_amount') or 0):.2f} AZN "
            f"({_row_value(order, 'status')})"
            for order in debts
        )
    else:
        text_lines.append("- Yeni borc yoxdur")
    text_lines.extend(["", "Aktiv məhsulların stok qalığı:"])
    if stock:
        text_lines.extend(
            f"- {_row_value(product, 'name')} ({_row_value(product, 'category')}): "
            f"{_row_value(product, 'stock')}"
            for product in stock
        )
    else:
        text_lines.append("- Aktiv məhsul yoxdur")
    text_lines.extend(["", f"Yeni borcların ümumi məbləği: {total_debt:.2f} AZN"])
    text_body = "\n".join(text_lines)

    def escaped(value):
        return html.escape(str(value), quote=True)

    sold_rows = "".join(
        f"<tr><td>{escaped(_row_value(item, 'product_name'))}</td>"
        f"<td>{escaped(_row_value(item, 'quantity'))}</td>"
        f"<td>{float(_row_value(item, 'amount') or 0):.2f} AZN</td></tr>"
        for item in sold_products
    ) or '<tr><td colspan="3">Satış olmayıb</td></tr>'
    debt_rows = "".join(
        f"<tr><td>{escaped(_row_value(order, 'customer_name'))}</td>"
        f"<td>{escaped(_row_value(order, 'status'))}</td>"
        f"<td>{float(_row_value(order, 'total_amount') or 0):.2f} AZN</td></tr>"
        for order in debts
    ) or '<tr><td colspan="3">Yeni borc yoxdur</td></tr>'
    stock_rows = "".join(
        f"<tr><td>{escaped(_row_value(product, 'name'))}</td>"
        f"<td>{escaped(_row_value(product, 'category'))}</td>"
        f"<td>{escaped(_row_value(product, 'stock'))}</td></tr>"
        for product in stock
    ) or '<tr><td colspan="3">Aktiv məhsul yoxdur</td></tr>'
    table_style = "border-collapse:collapse;width:100%;margin:12px 0 24px"
    cell_style = "border:1px solid #d9e1ea;padding:9px;text-align:left"
    html_body = f"""
    <!doctype html><html><body style="margin:0;background:#f3f6fa;font-family:Arial,sans-serif;color:#1f2937">
      <main style="max-width:760px;margin:24px auto;padding:24px;background:#fff;border-radius:12px">
        <h1 style="margin:0 0 6px;color:#17324d">Gündəlik hesabat</h1>
        <p style="margin:0 0 22px;color:#64748b">{date_label} · Bakı vaxtı</p>
        <div style="padding:16px;background:#eff6ff;border-radius:8px">
          <strong>Satış: {sale_count} satış · {sales_total:.2f} AZN</strong><br>
          Yeni borclar: {len(debts)} · {total_debt:.2f} AZN
        </div>
        <h2>Satılan məhsullar</h2>
        <table style="{table_style}"><thead><tr>
          <th style="{cell_style}">Məhsul</th><th style="{cell_style}">Miqdar</th><th style="{cell_style}">Məbləğ</th>
        </tr></thead><tbody>{sold_rows}</tbody></table>
        <h2>Yeni borclar</h2>
        <table style="{table_style}"><thead><tr>
          <th style="{cell_style}">Müştəri</th><th style="{cell_style}">Status</th><th style="{cell_style}">Məbləğ</th>
        </tr></thead><tbody>{debt_rows}</tbody></table>
        <h2>Aktiv məhsulların stok qalığı</h2>
        <table style="{table_style}"><thead><tr>
          <th style="{cell_style}">Məhsul</th><th style="{cell_style}">Kateqoriya</th><th style="{cell_style}">Qalıq</th>
        </tr></thead><tbody>{stock_rows}</tbody></table>
      </main>
    </body></html>
    """
    return {
        "subject": f"Gündəlik satış və stok hesabatı — {date_label}",
        "text": text_body,
        "html": html_body,
        "sale_count": sale_count,
        "sales_total": sales_total,
        "debt_count": len(debts),
        "debt_total": total_debt,
        "stock_count": len(stock),
    }


@app.route("/api/admin/daily-report", methods=["POST"])
def update_daily_report_settings():
    denied = _require_admin()
    if denied:
        return denied
    init_db()
    data = request.get_json(silent=True) or {}
    raw_recipients = str(data.get("recipients", "")).strip()
    try:
        recipients = _parse_email_recipients(raw_recipients)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    normalized = ", ".join(recipients)
    conn = get_db()
    database_url, _ = get_db_config()
    try:
        _set_app_setting(conn, database_url, "daily_report_recipients", normalized)
        _audit_event(
            conn,
            database_url,
            "daily_report_recipients_updated",
            "app_settings",
            details=f"recipient_count={len(recipients)}",
        )
        conn.commit()
        return jsonify({
            "success": True,
            "recipients": normalized,
            "message": "Hesabat alıcıları yadda saxlanıldı.",
        })
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Ayar yadda saxlanmadı: {exc}"}), 500


@app.route("/api/admin/daily-report/test", methods=["POST"])
def send_daily_report_test():
    denied = _require_admin()
    if denied:
        return denied
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    try:
        recipients = _parse_email_recipients(
            _get_app_setting(conn, database_url, "daily_report_recipients")
        )
        if not recipients:
            return jsonify({"success": False, "message": "Əvvəlcə ən azı bir alıcı e-poçtu qeyd edin."}), 400
        report_date = datetime.now(BAKU_TIMEZONE).date()
        _send_email(
            recipients,
            f"Test: gündəlik hesabat — {report_date.strftime('%d.%m.%Y')}",
            "Bu test məktubudur. Gündəlik hesabat e-poçt göndərişi işləyir.",
            "<p>Bu test məktubudur. <strong>Gündəlik hesabat e-poçt göndərişi işləyir.</strong></p>",
        )
        _audit_event(conn, database_url, "daily_report_test_sent", "app_settings")
        conn.commit()
        return jsonify({"success": True, "message": "Test məktubu göndərildi."})
    except (RuntimeError, smtplib.SMTPException, OSError, ValueError) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"E-poçt göndərilmədi: {exc}"}), 502
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"E-poçt ayarı oxunmadı: {exc}"}), 500


@app.route('/api/admin/users', methods=['GET', 'POST'])
def admin_users():
    denied = _require_admin()
    if denied:
        return denied
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        if request.method == "GET":
            cur.execute("SELECT id, username, role, active FROM users ORDER BY id")
            users = [
                {
                    "id": _row_value(row, "id"),
                    "username": _row_value(row, "username"),
                    "role": _row_value(row, "role"),
                    "active": bool(_row_value(row, "active")),
                }
                for row in cur.fetchall()
            ]
            return jsonify({"success": True, "users": users})

        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        role = str(data.get("role", "")).strip()
        pin = str(data.get("pin", "")).strip()
        if not username or role not in {"seller", "manager"} or not pin.isdigit() or len(pin) < 4:
            return jsonify({"success": False, "message": "Ad, rol və ən azı 4 rəqəmli PIN tələb olunur."}), 400
        placeholder = "%s" if database_url else "?"
        cur.execute(
            f"SELECT id FROM users WHERE username = {placeholder}",
            (username,),
        )
        if cur.fetchone():
            return jsonify({"success": False, "message": "Bu istifadəçi adı artıq mövcuddur."}), 409
        if database_url:
            cur.execute(
                "INSERT INTO users (username, role, pin_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, role, generate_password_hash(pin)),
            )
            user_id = _row_value(cur.fetchone(), "id")
        else:
            cur.execute(
                "INSERT INTO users (username, role, pin_hash) VALUES (?, ?, ?)",
                (username, role, generate_password_hash(pin)),
            )
            user_id = cur.lastrowid
        _audit_event(conn, database_url, "user_created", "user", user_id, username)
        conn.commit()
        return jsonify({"success": True, "id": user_id})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        cur.close()


@app.route('/api/admin/users/<int:user_id>', methods=['PUT', 'DELETE'])
def manage_admin_user(user_id):
    denied = _require_admin()
    if denied:
        return denied
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    placeholder = "%s" if database_url else "?"
    cur = conn.cursor()
    try:
        if request.method == "DELETE":
            cur.execute(f"DELETE FROM users WHERE id = {placeholder}", (user_id,))
            if cur.rowcount == 0:
                return jsonify({"success": False, "message": "İstifadəçi tapılmadı."}), 404
            conn.commit()
            return jsonify({"success": True})

        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        role = str(data.get("role", "")).strip()
        pin = str(data.get("pin", "")).strip()
        if not username or role not in {"seller", "manager"}:
            return jsonify({"success": False, "message": "Ad və düzgün rol tələb olunur."}), 400
        cur.execute(
            f"SELECT id FROM users WHERE username = {placeholder} AND id != {placeholder}",
            (username, user_id),
        )
        if cur.fetchone():
            return jsonify({"success": False, "message": "Bu istifadəçi adı artıq mövcuddur."}), 409
        if pin:
            if not pin.isdigit() or len(pin) < 4:
                return jsonify({"success": False, "message": "PIN ən azı 4 rəqəm olmalıdır."}), 400
            if database_url:
                cur.execute(
                    "UPDATE users SET username = %s, role = %s, pin_hash = %s WHERE id = %s",
                    (username, role, generate_password_hash(pin), user_id),
                )
            else:
                cur.execute(
                    "UPDATE users SET username = ?, role = ?, pin_hash = ? WHERE id = ?",
                    (username, role, generate_password_hash(pin), user_id),
                )
        else:
            cur.execute(
                f"UPDATE users SET username = {placeholder}, role = {placeholder} WHERE id = {placeholder}",
                (username, role, user_id),
            )
        if cur.rowcount == 0:
            return jsonify({"success": False, "message": "İstifadəçi tapılmadı."}), 404
        _audit_event(conn, database_url, "user_updated", "user", user_id, username)
        conn.commit()
        return jsonify({"success": True})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        cur.close()


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
    product stock. Stock may go negative when the sold quantity exceeds the
    recorded inventory.
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
                "SELECT id, name, price, stock FROM products WHERE id = %s AND is_active = TRUE",
                (product_id,),
            )
            product = cur.fetchone()
            if product is None:
                raise ValueError("Məhsul tapılmadı")
            line_total = float(product["price"]) * quantity
            total_amount += line_total

        # create sale
        insert_sale_sql = "INSERT INTO sales (total_amount) VALUES (%s) RETURNING id"
        cur.execute(insert_sale_sql, (round(total_amount, 2),))
        sale = cur.fetchone()
        sale_id = sale["id"]

        # insert items and update stock
        select_price_sql = "SELECT id, price FROM products WHERE id = %s AND is_active = TRUE"
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
            "WHERE id = ? AND is_active = 1"
        )
        product = conn.execute(select_sql, (product_id,)).fetchone()
        if product is None:
            raise ValueError("Məhsul tapılmadı")
        line_total = float(product["price"]) * quantity
        total_amount += line_total

    cursor = conn.cursor()
    insert_sale_sql = "INSERT INTO sales (total_amount) VALUES (?)"
    cursor.execute(insert_sale_sql, (round(total_amount, 2),))
    sale_id = cursor.lastrowid

    select_price_sql = "SELECT id, price FROM products WHERE id = ? AND is_active = 1"
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
    """Create an open credit order and deduct sold quantities from stock."""
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
                    "SELECT id, name, price, stock FROM products WHERE id = %s AND is_active = TRUE FOR UPDATE",
                    (product_id,),
                )
                product = cur.fetchone()
                if product is None:
                    raise ValueError("Məhsul tapılmadı")
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
            "SELECT id, name, price, stock FROM products WHERE id = ? AND is_active = 1",
            (product_id,),
        ).fetchone()
        if product is None:
            raise ValueError("Məhsul tapılmadı")
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
    """Render the table floor view and management settings."""
    init_db()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM table_categories ORDER BY name")
        table_categories = [_row_value(row, "name") for row in cur.fetchall()]
    finally:
        cur.close()
    return render_template("tables.html", table_categories=table_categories)


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
        cur.execute("SELECT id, name, category, price, stock FROM products WHERE is_active = TRUE ORDER BY name")
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
                f"SELECT id, price, stock FROM products WHERE id = {placeholder} AND is_active = {'TRUE' if database_url else '1'}",
                (product_id,),
            )
            product = cur.fetchone()
            if product is None:
                raise ValueError("Məhsul tapılmadı.")
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


@app.route("/api/tables/<int:table_number>/credit", methods=["POST"])
def table_credit(table_number):
    """Move an open table bill to open credit orders without deducting stock again."""
    data = request.get_json(silent=True) or {}
    customer_name = str(data.get("customer_name", "")).strip()
    if not customer_name:
        return jsonify({"success": False, "message": "Borc kimə yazılsın? Ad vacibdir."}), 400
    if len(customer_name) > 200:
        return jsonify({"success": False, "message": "Ad çox uzundur."}), 400

    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    permissions = _get_permissions(conn, database_url)
    if session.get("role") != "admin" and not permissions.get("open_orders", True):
        return jsonify({
            "success": False,
            "message": "Açıq qalanlar bölməsi admin tərəfindən bloklanıb.",
        }), 403

    placeholder = "%s" if database_url else "?"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT id FROM table_orders
            WHERE table_number = {placeholder} AND status = 'open'
            ORDER BY id DESC LIMIT 1
            """ + (" FOR UPDATE" if database_url else ""),
            (table_number,),
        )
        order = cur.fetchone()
        if not order:
            return jsonify({"success": False, "message": "Bu masa boşdur."}), 400

        order_id = _row_value(order, "id")
        items = _table_order_items(conn, database_url, order_id)
        if not items:
            return jsonify({"success": False, "message": "Masada məhsul yoxdur."}), 400

        total = round(sum(float(_row_value(item, "line_total")) for item in items), 2)
        if database_url:
            cur.execute(
                "INSERT INTO credit_orders (customer_name, total_amount) VALUES (%s, %s) RETURNING id",
                (customer_name, total),
            )
            credit_order_id = cur.fetchone()["id"]
        else:
            cur.execute(
                "INSERT INTO credit_orders (customer_name, total_amount) VALUES (?, ?)",
                (customer_name, total),
            )
            credit_order_id = cur.lastrowid

        for item in items:
            values = (
                credit_order_id,
                _row_value(item, "product_id"),
                _row_value(item, "quantity"),
                _row_value(item, "unit_price"),
            )
            cur.execute(
                """
                INSERT INTO credit_order_items
                    (credit_order_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
                """ if database_url else """
                INSERT INTO credit_order_items
                    (credit_order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                values,
            )

        cur.execute(
            f"""
            UPDATE table_orders
            SET status = 'closed', closed_at = CURRENT_TIMESTAMP
            WHERE id = {placeholder} AND status = 'open'
            """,
            (order_id,),
        )
        if cur.rowcount != 1:
            raise ValueError("Masa sifarişi artıq dəyişdirilib.")

        conn.commit()
        return jsonify({
            "success": True,
            "id": credit_order_id,
            "total": total,
            "message": "Masa borc kimi Açıq qalanlara köçürüldü.",
        })
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 409
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Masa borca keçirilərkən xəta: {exc}"}), 500
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
                    "SELECT id, name, price, stock FROM products WHERE id = %s AND is_active = TRUE FOR UPDATE",
                    (product_id,),
                )
                product = cur.fetchone()
            else:
                cur.execute(
                    "SELECT id, name, price, stock FROM products WHERE id = ? AND is_active = 1",
                    (product_id,),
                )
                product = cur.fetchone()
            if product is None:
                raise ValueError("Məhsul tapılmadı")
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
        sale_id = None
        if is_paid:
            if database_url:
                cur.execute(
                    "INSERT INTO sales (total_amount) VALUES (%s) RETURNING id",
                    (total_amount,),
                )
                sale_id = cur.fetchone()["id"]
            else:
                cur.execute("INSERT INTO sales (total_amount) VALUES (?)", (total_amount,))
                sale_id = cur.lastrowid

            for item in _credit_order_items(conn, database_url, order_id):
                if database_url:
                    cur.execute(
                        """
                        INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            sale_id,
                            _row_value(item, "product_id"),
                            _row_value(item, "quantity"),
                            _row_value(item, "unit_price"),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            sale_id,
                            _row_value(item, "product_id"),
                            _row_value(item, "quantity"),
                            _row_value(item, "unit_price"),
                        ),
                    )
            _audit_event(
                conn,
                database_url,
                "sale_completed",
                "sale",
                sale_id,
                f"credit_order={order_id}",
            )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "Sifariş tam ödənildi." if is_paid else "Hissəli ödəniş qeydə alındı.",
                "paid_amount": new_paid_amount,
                "remaining_amount": round(total_amount - new_paid_amount, 2),
                "status": "paid" if is_paid else "open",
                "sale_id": sale_id,
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
                    "UPDATE products SET name = %s, category = %s, price = %s, stock = %s, image_url = %s WHERE id = %s AND is_active = TRUE",
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
                    "UPDATE products SET name = ?, category = ?, price = ?, stock = ?, image_url = ? WHERE id = ? AND is_active = 1",
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
    """Archive a product while preserving its historical references."""
    conn = get_db()
    database_url, _ = get_db_config()
    try:
        if database_url:
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE products SET is_active = FALSE WHERE id = %s AND is_active = TRUE",
                    (product_id,),
                )
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
                cur.execute(
                    "UPDATE products SET is_active = 0 WHERE id = ? AND is_active = 1",
                    (product_id,),
                )
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


@app.route('/api/products/archive-all', methods=['POST'])
def archive_all_products():
    """Archive every active product without removing historical references."""
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE products SET is_active = FALSE WHERE is_active = TRUE"
            if database_url
            else "UPDATE products SET is_active = 0 WHERE is_active = 1"
        )
        archived_count = cur.rowcount
        _audit_event(
            conn,
            database_url,
            "products_archived",
            "product",
            details=f"count={archived_count}",
        )
        conn.commit()
        return jsonify({
            "success": True,
            "archived_count": archived_count,
            "message": f"{archived_count} məhsul arxivləndi.",
        })
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Məhsulları arxivləmək mümkün olmadı: {exc}",
        }), 500
    finally:
        cur.close()


def _clear_history_tables(tables, action, entity_type, parent_table):
    conn = get_db()
    database_url, _ = get_db_config()
    cur = conn.cursor()
    try:
        deleted_counts = {}
        for table in tables:
            cur.execute(f"DELETE FROM {table}")
            deleted_counts[table] = cur.rowcount
        history_count = deleted_counts[parent_table]
        _audit_event(
            conn,
            database_url,
            action,
            entity_type,
            details=f"deleted={deleted_counts}",
        )
        conn.commit()
        return jsonify({"success": True, "deleted_count": history_count})
    except (sqlite3.Error, psycopg2.Error) as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Tarixçəni təmizləmək mümkün olmadı: {exc}",
        }), 500
    finally:
        cur.close()


@app.route("/api/history/stock/clear", methods=["POST"])
def clear_stock_history():
    """Remove stock movement history without changing current stock levels."""
    return _clear_history_tables(
        ["stock_movements"],
        "stock_history_cleared",
        "stock_history",
        "stock_movements",
    )


@app.route("/api/history/sales/clear", methods=["POST"])
def clear_sales_history():
    """Remove sales and their line items while preserving products and stock."""
    return _clear_history_tables(
        ["sale_items", "sales"],
        "sales_history_cleared",
        "sales_history",
        "sales",
    )


@app.route("/api/history/debts/clear", methods=["POST"])
def clear_debt_history():
    """Remove all credit orders, including unpaid ones, and their line items."""
    return _clear_history_tables(
        ["credit_order_items", "credit_orders"],
        "debt_history_cleared",
        "debt_history",
        "credit_orders",
    )


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


@app.cli.command("send-daily-report")
def send_daily_report_command():
    """Send the daily sales, stock and new-debt report to configured managers."""
    with app.app_context():
        init_db()
        conn = get_db()
        database_url, _ = get_db_config()
        recipients = _parse_email_recipients(
            _get_app_setting(conn, database_url, "daily_report_recipients")
        )
        if not recipients:
            raise ClickException(
                "Admin səhifəsində gündəlik hesabat üçün e-poçt alıcıları qeyd edilməyib."
            )
        report_date = datetime.now(BAKU_TIMEZONE).date() - timedelta(days=1)
        report = _build_daily_email_report(conn, database_url, report_date)
        try:
            _send_email(
                recipients,
                report["subject"],
                report["text"],
                report["html"],
            )
        except (RuntimeError, smtplib.SMTPException, OSError) as exc:
            raise ClickException(f"Gündəlik hesabat göndərilmədi: {exc}") from exc
        print(
            f"Daily report sent for {report_date.isoformat()} to {len(recipients)} "
            f"recipient(s): {report['sale_count']} sales, "
            f"{report['debt_count']} new debts, {report['stock_count']} active products."
        )


if __name__ == "__main__":
    # Read port from environment (e.g., Railway provides $PORT). Fallback to 5000 for local dev.
    port = int(os.getenv("PORT", "5000"))
    # Allow controlling debug mode via FLASK_DEBUG env var (optional)
    debug_env = os.getenv("FLASK_DEBUG", "False").lower() in ("1", "true", "yes")
    app.run(debug=debug_env, host="0.0.0.0", port=port)
