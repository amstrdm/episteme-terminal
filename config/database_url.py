import os

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(current_dir, "config.env")

load_dotenv(ENV_PATH)

DB_USER = os.getenv("POSTGRESQL_USER")
DB_PASSWORD = os.getenv("POSTGRESQL_PASSWORD")
DB_HOST = os.getenv("POSTGRESQL_HOST")
DB_NAME = os.getenv("POSTGRESQL_DBNAME")
STOCKS_DB_NAME = os.getenv("POSTGRESQL_STOCKS_DBNAME")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
STOCKS_DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{STOCKS_DB_NAME}"
)
