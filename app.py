import os
from pathlib import Path

import psycopg2
import sqlite3
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


def get_db_config():
    database_url = os.getenv("DATABASE_URL")
    sqlite_db_path = os.getenv("SQLITE_DB_PATH", str(Path(__file__).parent / "app.db"))
    return database_url, sqlite_db_path


def get_db():
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
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = get_db()
    database_url, _ = get_db_config()

    if database_url:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    price NUMERIC(10,2) NOT NULL,
                    stock INT NOT NULL DEFAULT 0
                )
                """
            )
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
            if cur.fetchone()["count"] == 0:
                cur.execute("INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)", ("Kofe", 12.50, 20))
                cur.execute("INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)", ("Su", 2.50, 100))
                cur.execute("INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)", ("Çörək", 4.00, 50))
            conn.commit()
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL
            )
            """
        )
        conn.execute(
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
        existing_count = conn.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
        if existing_count == 0:
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ("Kofe", 12.50, 20))
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ("Su", 2.50, 100))
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ("Çörək", 4.00, 50))
        conn.commit()


@app.route("/")
def products_page():
    init_db()
    conn = get_db()
    database_url, _ = get_db_config()
    if database_url:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, price, stock FROM products ORDER BY id")
            products = cur.fetchall()
    else:
        products = conn.execute("SELECT id, name, price, stock FROM products ORDER BY id").fetchall()
    return render_template("products.html", products=products)


@app.route("/checkout", methods=["POST"])
def checkout():
    data = request.get_json(silent=True) or {}
    cart = data.get("cart", [])

    if not isinstance(cart, list) or not cart:
        return jsonify({"success": False, "message": "Səbət boşdur."}), 400

    conn = get_db()
    database_url, _ = get_db_config()

    try:
        if database_url:
            with conn.cursor() as cur:
                total_amount = 0.0
                for item in cart:
                    product_id = item.get("id")
                    quantity = item.get("quantity", 0)
                    if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
                        raise ValueError("Yanlış məhsul məlumatı")

                    cur.execute("SELECT id, name, price, stock FROM products WHERE id = %s", (product_id,))
                    product = cur.fetchone()
                    if product is None:
                        raise ValueError("Məhsul tapılmadı")
                    if quantity > product["stock"]:
                        return jsonify({"success": False, "message": f"{product['name']} üçün kifayət qədər stok yoxdur."}), 400

                    line_total = float(product["price"]) * quantity
                    total_amount += line_total

                cur.execute("INSERT INTO sales (total_amount) VALUES (%s) RETURNING id", (round(total_amount, 2),))
                sale = cur.fetchone()
                sale_id = sale["id"]

                for item in cart:
                    product_id = item["id"]
                    quantity = item["quantity"]
                    cur.execute("SELECT id, price FROM products WHERE id = %s", (product_id,))
                    product = cur.fetchone()
                    cur.execute(
                        "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                        (sale_id, product_id, quantity, product["price"]),
                    )
                    cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (quantity, product_id))

                conn.commit()
        else:
            total_amount = 0.0
            for item in cart:
                product_id = item.get("id")
                quantity = item.get("quantity", 0)
                if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
                    raise ValueError("Yanlış məhsul məlumatı")

                product = conn.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,)).fetchone()
                if product is None:
                    raise ValueError("Məhsul tapılmadı")
                if quantity > product["stock"]:
                    return jsonify({"success": False, "message": f"{product['name']} üçün kifayət qədər stok yoxdur."}), 400

                line_total = float(product["price"]) * quantity
                total_amount += line_total

            cursor = conn.cursor()
            cursor.execute("INSERT INTO sales (total_amount) VALUES (?)", (round(total_amount, 2),))
            sale_id = cursor.lastrowid

            for item in cart:
                product_id = item["id"]
                quantity = item["quantity"]
                product = conn.execute("SELECT id, price FROM products WHERE id = ?", (product_id,)).fetchone()
                cursor.execute(
                    "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (sale_id, product_id, quantity, product["price"]),
                )
                conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))

            conn.commit()

        return jsonify({"success": True, "message": "Satış tamamlandı!"})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        conn.rollback()
        return jsonify({"success": False, "message": f"Satış yazılarkən xəta: {exc}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
