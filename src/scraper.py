"""
src/scraper.py
Task 1 — Telegram scraping pipeline.

Scrapes messages + images from the target channels and writes them into
the raw data lake:
  data/raw/telegram_messages/YYYY-MM-DD/channel_name.json
  data/raw/images/{channel_name}/{message_id}.jpg
  logs/scrape_log.txt

Run from the project root:
    python src\\scraper.py
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")

# Required channels for this challenge
CHANNELS = [
    "Chemed123",          # CheMed
    "lobelia4cosmetics",  # Lobelia Cosmetics
    "tikvahpharma",       # Tikvah Pharma
]

# How many of the most recent messages to pull per channel per run.
# Telethon will paginate automatically if you raise this.
MESSAGE_LIMIT = 200

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_MESSAGES_DIR = BASE_DIR / "data" / "raw" / "telegram_messages"
RAW_IMAGES_DIR = BASE_DIR / "data" / "raw" / "images"
LOGS_DIR = BASE_DIR / "logs"
SESSION_NAME = str(BASE_DIR / "telegram_scraper_session")

RAW_MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
RAW_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "scrape_log.txt", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def serialize_message(message, channel_name: str, image_path: str | None) -> dict:
    """Convert a Telethon Message object into a JSON-serializable dict,
    preserving the original API field names as much as possible."""
    return {
        "message_id": message.id,
        "channel_name": channel_name,
        "message_date": message.date.isoformat() if message.date else None,
        "message_text": message.message or "",
        "has_media": message.media is not None,
        "image_path": image_path,
        "views": getattr(message, "views", None),
        "forwards": getattr(message, "forwards", None),
        "raw": {
            "id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "out": message.out,
            "post": getattr(message, "post", None),
            "edit_date": message.edit_date.isoformat() if message.edit_date else None,
        },
    }


def download_image(client: TelegramClient, message, channel_name: str) -> str | None:
    """Download a message's photo, if any, into the partitioned image folder.
    Returns the relative path stored, or None if there's no photo."""
    if not isinstance(message.media, MessageMediaPhoto):
        return None

    channel_image_dir = RAW_IMAGES_DIR / channel_name
    channel_image_dir.mkdir(parents=True, exist_ok=True)
    target_path = channel_image_dir / f"{message.id}.jpg"

    try:
        client.download_media(message, file=str(target_path))
        logger.info(f"Downloaded image for message {message.id} in {channel_name}")
        return str(target_path.relative_to(BASE_DIR))
    except Exception as exc:
        logger.error(f"Failed to download image for message {message.id} in {channel_name}: {exc}")
        return None


def scrape_channel(client: TelegramClient, channel_name: str) -> None:
    logger.info(f"Starting scrape for channel: {channel_name}")

    # group messages by the date they were posted, since one run may span
    # messages from multiple days
    messages_by_date: dict[str, list[dict]] = {}

    try:
        for message in client.iter_messages(channel_name, limit=MESSAGE_LIMIT):
            if message.message is None and message.media is None:
                continue  # skip service messages with no content

            image_path = download_image(client, message, channel_name)
            record = serialize_message(message, channel_name, image_path)

            day_key = message.date.strftime("%Y-%m-%d") if message.date else "unknown_date"
            messages_by_date.setdefault(day_key, []).append(record)

    except Exception as exc:
        logger.error(f"Error while scraping channel {channel_name}: {exc}")
        return

    # write one JSON file per day, per channel
    for day_key, records in messages_by_date.items():
        day_dir = RAW_MESSAGES_DIR / day_key
        day_dir.mkdir(parents=True, exist_ok=True)
        out_path = day_dir / f"{channel_name}.json"

        # if a file already exists for this day (re-run), merge and dedupe by message_id
        existing = []
        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        combined = {r["message_id"]: r for r in existing}
        for r in records:
            combined[r["message_id"]] = r

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(list(combined.values()), f, ensure_ascii=False, indent=2)

        logger.info(f"Wrote {len(records)} messages for {channel_name} on {day_key} -> {out_path}")

    logger.info(f"Finished scrape for channel: {channel_name} "
                f"({sum(len(v) for v in messages_by_date.values())} messages total)")


def main():
    logger.info("=== Scrape run started: %s ===" % datetime.now(timezone.utc).isoformat())

    with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        client.start(phone=PHONE)
        for channel_name in CHANNELS:
            scrape_channel(client, channel_name)

    logger.info("=== Scrape run finished ===")


if __name__ == "__main__":
    main()