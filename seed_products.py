import os
from pathlib import Path

import psycopg2
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(Path(__file__).parent / "app.db"))


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(SQLITE_DB_PATH)


def seed_products():
    conn = get_connection()
    try:
        if DATABASE_URL:
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
                cur.execute("DELETE FROM products")
                cur.execute(
                    "INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)",
                    ("Kofe", 12.50, 20),
                )
                cur.execute(
                    "INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)",
                    ("Su", 2.50, 100),
                )
                cur.execute(
                    "INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)",
                    ("Çörək", 4.00, 50),
                )
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
            conn.execute("DELETE FROM products")
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ("Kofe", 12.50, 20))
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ("Su", 2.50, 100))
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ("Çörək", 4.00, 50))
            conn.commit()

        print("3 məhsul əlavə edildi.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_products()
