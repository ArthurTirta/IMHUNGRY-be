import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    user="postgres",
    password="postgres",
    dbname="postgres",
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = 'imhungry'")
if cur.fetchone():
    print("Database imhungry already exists")
else:
    cur.execute("CREATE DATABASE imhungry")
    print("Database imhungry created successfully")
cur.close()
conn.close()
