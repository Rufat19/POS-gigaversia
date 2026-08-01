"""POS simple Flask application: products listing, cart checkout and basic DB setup.

This module provides endpoints to render a product kiosk-style frontend and to
process an in-memory cart via /checkout. It supports SQLite (local) and
PostgreSQL (via DATABASE_URL).
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

import psycopg2
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

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
                total_amount NUMERIC(10,2) NOT NULL
            )
            """
        )
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
                total_amount REAL NOT NULL
            )
            """
        )
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
            cur.execute("SELECT DISTINCT category FROM products ORDER BY category")
            categories = [r[0] for r in cur.fetchall()]
        finally:
            cur.close()
    else:
        products_sql = (
            "SELECT id, name, category, price, stock "
            "FROM products ORDER BY id"
        )
        cur = conn.cursor()
        try:
            cur.execute(products_sql)
            products = cur.fetchall()
            categories_sql = (
                "SELECT DISTINCT category FROM products "
                "ORDER BY category"
            )
            cur.execute(categories_sql)
            categories = [r[0] for r in cur.fetchall()]
        finally:
            cur.close()
    return render_template("products.html", products=products, categories=categories)


@app.route('/operations')
def operations_page():
    """Render operations page: add stock movements and show combined history."""
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    # load products for dropdown
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, name FROM products ORDER BY name")
            products = cur.fetchall()
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, name FROM products ORDER BY name")
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

    return render_template('operations.html', products=products, history=history)


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
            WHERE s.created_at::date BETWEEN %s AND %s
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
            WHERE s.created_at::date BETWEEN %s AND %s
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
            WHERE s.created_at::date BETWEEN %s AND %s
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
            WHERE s.created_at::date BETWEEN %s AND %s
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
            WHERE DATE(s.created_at) BETWEEN ? AND ?
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


@app.route('/add_product', methods=['POST'])
def add_product():
    """API endpoint to add a new product.

    Accepts JSON: {name, category, price, stock, image_url} and inserts a new
    product row, returning the created product id.
    """
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    category = data.get('category', 'Other')
    try:
        price = float(data.get('price', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid price'}), 400
    try:
        stock = int(data.get('stock', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid stock'}), 400
    image_url = data.get('image_url')

    conn = get_db()
    database_url, _ = get_db_config()
    if database_url:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO products (name, category, price, stock, image_url) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, category, price, stock, image_url),
            )
            row = cur.fetchone()
            conn.commit()
            if row is None:
                new_id = None
            elif isinstance(row, dict):
                new_id = row.get('id')
            else:
                new_id = row[0]
            return jsonify({'success': True, 'id': new_id})
        except (psycopg2.Error, sqlite3.Error) as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
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
            conn.commit()
            return jsonify({'success': True, 'id': new_id})
        except (sqlite3.Error, psycopg2.Error) as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            cur.close()


if __name__ == "__main__":
    # Read port from environment (e.g., Railway provides $PORT). Fallback to 5000 for local dev.
    port = int(os.getenv("PORT", "5000"))
    # Allow controlling debug mode via FLASK_DEBUG env var (optional)
    debug_env = os.getenv("FLASK_DEBUG", "False").lower() in ("1", "true", "yes")
    app.run(debug=debug_env, host="0.0.0.0", port=port)
