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
        # Full product list derived from user-provided data. Default stock=50 for most items.
        products = [
            ("Cola 0.5", "Drinks", 2.00, 50),
            ("Cola banka", "Drinks", 2.50, 50),
            ("Pepsi banka", "Drinks", 2.50, 50),
            ("Ice Coffee", "Drinks", 2.50, 50),
            ("Fuse Tea 0.5", "Drinks", 2.00, 50),
            ("Red bul", "Drinks", 5.00, 50),
            ("Moxito", "Drinks", 2.00, 50),
            ("Bizon Hell", "Drinks", 1.40, 50),
            ("Sirab 0.5", "Drinks", 1.00, 50),
            ("Sirab 1 lt", "Drinks", 1.50, 50),
            ("Sirab Qazlı 0.5", "Drinks", 1.00, 50),
            ("SARIKIZ", "Drinks", 1.00, 50),
            ("Natura təbii şirə", "Drinks", 1.40, 50),
            ("Lovita Peçenye", "Snacks", 5.00, 50),
            ("Crax Böyük", "Snacks", 2.00, 50),
            ("TUC", "Snacks", 3.50, 50),
            ("7 Days", "Snacks", 2.00, 50),
            ("OZMO fun", "Snacks", 2.20, 50),
            ("OZMO Cornet", "Snacks", 1.60, 50),
            ("OZMO yumurta", "Snacks", 3.00, 50),
            ("Snickers, Mars, Twix", "Snacks", 2.40, 50),
            ("Albeni şokolad", "Snacks", 2.40, 50),
            ("Hoşbeş", "Snacks", 1.20, 50),
            ("Ozmo ogopogo", "Snacks", 1.20, 50),
            ("POP cake", "Snacks", 1.20, 50),
            ("Barni", "Snacks", 2.00, 50),
            ("LAYS", "Snacks", 5.00, 50),
            ("Chetos", "Snacks", 4.00, 50),
            ("Yummy gummy", "Snacks", 2.50, 50),
            ("Biskolata mood", "Snacks", 4.00, 50),
            ("Biskolata  Stick", "Snacks", 2.50, 50),
            ("Chupa Chups", "Snacks", 1.50, 50),
            ("Chupa Chups Vata", "Snacks", 2.50, 50),
            ("Nut GO", "Snacks", 2.00, 50),
            ("Marshmallow rainbow", "Snacks", 3.00, 50),
            ("Morsok", "Snacks", 3.50, 50),
            ("Kinder Surprise", "Snacks", 4.00, 50),
            ("Rainbow", "Snacks", 1.00, 50),
            ("Dirol", "Snacks", 1.00, 50),
            ("ŞOKOLAD", "Snacks", 1.50, 50),
            ("ŞOKOLAD balaca", "Snacks", 1.00, 50),
            ("Xrusteam", "Snacks", 2.00, 50),
            ("BALMİTO", "Snacks", 2.00, 50),
            ("KİT-KAT", "Snacks", 4.00, 50),
            ("MİLKA", "Snacks", 5.00, 50),
            ("ƏTİR", "Other", 6.00, 50),
            ("OREO", "Snacks", 3.50, 50),
            ("Yubileynoe peçenye şokolad", "Snacks", 2.70, 50),
            ("Yubileynoe peçenye sadə", "Snacks", 2.20, 50),
            ("Lovita balaca", "Snacks", 3.00, 50),
            ("Balık kreker", "Snacks", 2.00, 50),
            ("Biskolata starz", "Snacks", 3.00, 50),
            ("İkram", "Snacks", 2.00, 50),
            ("Mentos duo", "Snacks", 2.50, 50),
            ("Bambbar shok  50 gr", "Protein", 5.00, 50),
            ("Snaqfabrique 55 gr", "Protein", 4.50, 50),
            ("Snager 50 gr", "Protein", 4.00, 50),
            ("Pritein delice 60 gr", "Protein", 4.00, 50),
            ("Bombbar wafer 45 gr", "Protein", 4.00, 50),
            ("Fitness shock 50 gr", "Protein", 4.00, 50),
            ("Bombbar l-carnitine", "Protein", 5.00, 50),
            ("Bambbar protein chips", "Protein", 4.00, 50),
            ("Boul", "Salads", 8.00, 50),
            ("Sezar Salat", "Salads", 8.00, 50),
            ("Club Sendvich", "Fastfood", 7.00, 50),
            ("Burger", "Fastfood", 6.00, 50),
            ("Sezar Roll", "Fastfood", 7.00, 50),
            ("Bulka", "Fastfood", 2.50, 50),
            ("Bulka 3₼", "Fastfood", 3.00, 50),
            ("Sirab 1.5", "Drinks", 2.00, 50),
        ]

        if DATABASE_URL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS products (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Other',
                        price NUMERIC(10,2) NOT NULL,
                        stock INT NOT NULL DEFAULT 0
                    )
                    """
                )
                cur.execute("DELETE FROM products")
                for p in products:
                    cur.execute("INSERT INTO products (name, category, price, stock) VALUES (%s, %s, %s, %s)", p)
                conn.commit()
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'Other',
                    price REAL NOT NULL,
                    stock INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("DELETE FROM products")
            for p in products:
                conn.execute("INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)", p)
            conn.commit()

        print(f"{len(products)} məhsul əlavə edildi.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_products()
