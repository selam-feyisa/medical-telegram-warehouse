"""
scripts/load_raw_to_postgres.py
Task 2 (part 1) — Load raw JSON files from the data lake into PostgreSQL.

Reads every JSON file under data/raw/telegram_messages/, and inserts all
records into raw.telegram_messages, preserving the original scraped fields.

Run from the project root:
    python scripts\\load_raw_to_postgres.py
"""

import os
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_MESSAGES_DIR = BASE_DIR / "data" / "raw" / "telegram_messages"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "load_log.txt", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "medical_warehouse"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS raw;"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw.telegram_messages (
    message_id      BIGINT,
    channel_name    TEXT,
    message_date    TIMESTAMP,
    message_text    TEXT,
    has_media       BOOLEAN,
    image_path      TEXT,
    views           INTEGER,
    forwards        INTEGER,
    loaded_at       TIMESTAMP DEFAULT now(),
    PRIMARY KEY (message_id, channel_name)
);

CREATE TABLE IF NOT EXISTS raw.image_detections (
    message_id BIGINT,
    channel_name TEXT,
    image_path TEXT,
    detected_objects TEXT,
    confidence_score DOUBLE PRECISION,
    image_category TEXT,
    loaded_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (message_id, channel_name)
);
"""

UPSERT_SQL = """
INSERT INTO raw.telegram_messages
    (message_id, channel_name, message_date, message_text, has_media, image_path, views, forwards)
VALUES %s
ON CONFLICT (message_id, channel_name) DO UPDATE SET
    message_date = EXCLUDED.message_date,
    message_text = EXCLUDED.message_text,
    has_media     = EXCLUDED.has_media,
    image_path    = EXCLUDED.image_path,
    views         = EXCLUDED.views,
    forwards      = EXCLUDED.forwards,
    loaded_at     = now();
"""


def find_json_files():
    return sorted(RAW_MESSAGES_DIR.rglob("*.json"))


def load_records_from_file(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse {path}: {exc}")
            return []


def main():
    json_files = find_json_files()
    if not json_files:
        logger.warning(f"No JSON files found under {RAW_MESSAGES_DIR}. Run the scraper first.")
        return

    logger.info(f"Found {len(json_files)} JSON files to load.")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute(CREATE_SCHEMA_SQL)
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()

        total_rows = 0
        for path in json_files:
            records = load_records_from_file(path)
            if not records:
                continue

            rows = [
                (
                    r.get("message_id"),
                    r.get("channel_name"),
                    r.get("message_date"),
                    r.get("message_text"),
                    r.get("has_media"),
                    r.get("image_path"),
                    r.get("views"),
                    r.get("forwards"),
                )
                for r in records
            ]

            execute_values(cur, UPSERT_SQL, rows)
            conn.commit()
            total_rows += len(rows)
            logger.info(f"Loaded {len(rows)} rows from {path.name}")

        logger.info(f"Done. Total rows upserted: {total_rows}")

        cur.execute("SELECT COUNT(*) FROM raw.telegram_messages;")
        count = cur.fetchone()[0]
        logger.info(f"raw.telegram_messages now has {count} total rows.")

    except Exception as exc:
        conn.rollback()
        logger.error(f"Error during load, rolled back: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()