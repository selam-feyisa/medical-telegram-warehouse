from __future__ import annotations

import csv
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_ROOT = BASE_DIR / "data" / "raw" / "images"
OUTPUT_CSV = BASE_DIR / "data" / "raw" / "yolo_detections.csv"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "yolo_log.txt", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover - package may be absent in some environments
    YOLO = None


def classify_detected_objects(objects: List[str]) -> str:
    """Map detected object labels into a simple business-friendly category."""
    lowered = {obj.lower() for obj in objects}
    product_objects = {"bottle", "container", "box", "tablet", "pill", "cream", "jar", "tube"}

    if "person" in lowered and lowered.intersection(product_objects):
        return "promotional"
    if "person" in lowered:
        return "lifestyle"
    if lowered.intersection(product_objects):
        return "product_display"
    return "other"


def detect_objects(image_path: Path) -> Dict[str, Any]:
    """Detect objects from an image using YOLO when available, otherwise use heuristics."""
    detected_objects: List[str] = []
    confidence_score = 0.0

    if YOLO is not None:
        try:
            model = YOLO("yolov8n.pt")
            results = model(str(image_path), stream=False, conf=0.25)
            boxes = results[0].boxes
            if boxes is not None:
                for box in boxes:
                    label = model.names[int(box.cls[0])]
                    detected_objects.append(label)
                    confidence_score = max(confidence_score, float(box.conf[0]))
        except Exception as exc:  # pragma: no cover - network/model download issues
            logger.warning("YOLO detection failed for %s: %s", image_path, exc)

    if not detected_objects:
        text = image_path.stem.lower()
        if re.search(r"(pill|tablet|bottle|cream|jar|tube|box)", text):
            detected_objects = ["bottle"]
        elif re.search(r"(person|man|woman|face)", text):
            detected_objects = ["person"]
        else:
            detected_objects = []

    image_category = classify_detected_objects(detected_objects)
    return {
        "detected_objects": detected_objects,
        "confidence_score": round(confidence_score, 3),
        "image_category": image_category,
    }


def scan_images() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not IMAGE_ROOT.exists():
        return records

    for image_path in sorted(IMAGE_ROOT.rglob("*.jpg")):
        if image_path.name.lower().endswith(".jpg"):
            channel_name = image_path.parent.name
            message_id = image_path.stem
            detection = detect_objects(image_path)
            records.append(
                {
                    "message_id": int(message_id) if message_id.isdigit() else None,
                    "channel_name": channel_name,
                    "image_path": str(image_path.relative_to(BASE_DIR)),
                    "detected_objects": ";".join(detection["detected_objects"]),
                    "confidence_score": detection["confidence_score"],
                    "image_category": detection["image_category"],
                }
            )
    return records


def write_csv(records: List[Dict[str, Any]]) -> Path:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "message_id",
        "channel_name",
        "image_path",
        "detected_objects",
        "confidence_score",
        "image_category",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return OUTPUT_CSV


def save_to_postgres(records: List[Dict[str, Any]]) -> None:
    try:
        import psycopg2
    except Exception as exc:  # pragma: no cover - dependency issue
        logger.warning("psycopg2 not available; skipping PostgreSQL load: %s", exc)
        return

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "medical_warehouse"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
            cur.execute(
                """
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
            )
            for record in records:
                cur.execute(
                    """
                    INSERT INTO raw.image_detections
                    (message_id, channel_name, image_path, detected_objects, confidence_score, image_category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id, channel_name) DO UPDATE SET
                        image_path = EXCLUDED.image_path,
                        detected_objects = EXCLUDED.detected_objects,
                        confidence_score = EXCLUDED.confidence_score,
                        image_category = EXCLUDED.image_category,
                        loaded_at = now();
                    """,
                    (
                        record["message_id"],
                        record["channel_name"],
                        record["image_path"],
                        record["detected_objects"],
                        record["confidence_score"],
                        record["image_category"],
                    ),
                )
            conn.commit()
    finally:
        conn.close()


def main() -> None:
    logger.info("Starting YOLO enrichment run")
    records = scan_images()
    if records:
        write_csv(records)
        save_to_postgres(records)
        logger.info("Saved %s image detection records", len(records))
    else:
        logger.info("No images were found to enrich")


if __name__ == "__main__":
    main()
