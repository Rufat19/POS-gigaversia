"""POS simple Flask application: products listing, cart checkout and basic DB setup.

This module provides endpoints to render a product kiosk-style frontend and to
process an in-memory cart via /checkout. It supports SQLite (local) and
PostgreSQL (via DATABASE_URL).
"""

import os
from pathlib import Path
import sqlite3

import psycopg2
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


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

        cur.execute("SELECT COUNT(*) AS count FROM products")
        row = cur.fetchone()
        pg_count = 0
        if row is not None:
            try:
                # Support both mapping-like (RealDictCursor) and tuple rows
                if not isinstance(row, tuple) and hasattr(row, "get"):
                    pg_count = int(row.get("count", 0))
                else:
                    pg_count = int(row[0])
            except (ValueError, TypeError):
                pg_count = 0
        if pg_count == 0:
            cur.execute(
                "INSERT INTO products (name, price, stock, image_url) VALUES (%s, %s, %s, %s)",
                ("Kofe", 12.50, 20, None),
            )
            cur.execute(
                "INSERT INTO products (name, price, stock, image_url) VALUES (%s, %s, %s, %s)",
                ("Su", 2.50, 100, None),
            )
            cur.execute(
                "INSERT INTO products (name, price, stock, image_url) VALUES (%s, %s, %s, %s)",
                ("Çörək", 4.00, 50, None),
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
        cur.execute("SELECT COUNT(*) AS count FROM products")
        row = cur.fetchone()
        existing_count = 0
        if row is not None:
            try:
                # sqlite3.Row supports mapping access by column name. Use
                # an isinstance check to satisfy type checkers before
                # indexing by key.
                if isinstance(row, sqlite3.Row):
                    existing_count = int(row["count"])  # type: ignore[index]
                else:
                    existing_count = int(row[0])
            except (ValueError, TypeError):
                existing_count = 0
        if existing_count == 0:
            cur.execute(
                "INSERT INTO products (name, price, stock, image_url) VALUES (?, ?, ?, ?)",
                ("Kofe", 12.50, 20, None),
            )
            cur.execute(
                "INSERT INTO products (name, price, stock, image_url) VALUES (?, ?, ?, ?)",
                ("Su", 2.50, 100, None),
            )
            cur.execute(
                "INSERT INTO products (name, price, stock, image_url) VALUES (?, ?, ?, ?)",
                ("Çörək", 4.00, 50, None),
            )
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
            cur.execute("SELECT id, name, category, price, stock FROM products ORDER BY id")
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

        return jsonify({"success": True, "message": "Satış tamamlandı!", "sale_id": sale_id, "total": total})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:  # pylint: disable=broad-except
        # Top-level exception handler: log/rollback and return 500
        conn.rollback()
        return jsonify({"success": False, "message": f"Satış yazılarkən xəta: {exc}"}), 500


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
                "INSERT INTO products (name, category, price, stock, image_url) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, category, price, stock, image_url),
            )
            row = cur.fetchone()
            conn.commit()
            new_id = row['id'] if row and not isinstance(row, tuple) and hasattr(row, 'get') else (row[0] if row else None)
            return jsonify({'success': True, 'id': new_id})
        except Exception as exc:  # pylint: disable=broad-except
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            cur.close()
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO products (name, category, price, stock, image_url) VALUES (?, ?, ?, ?, ?)",
                (name, category, price, stock, image_url),
            )
            new_id = cur.lastrowid
            conn.commit()
            return jsonify({'success': True, 'id': new_id})
        except Exception as exc:  # pylint: disable=broad-except
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
