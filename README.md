# Medical Telegram Warehouse

This project implements an end-to-end Telegram analytics pipeline that scrapes public medical channels, stores raw data in a data lake, loads it into PostgreSQL, transforms the data with dbt, enriches images with YOLO, and exposes analytical endpoints with FastAPI.

## Project structure
- src/scraper.py: collects Telegram messages and downloads images to the raw data lake
- scripts/load_raw_to_postgres.py: loads JSON files into PostgreSQL
- medical_warehouse/: dbt project for staging and mart models
- src/yolo_detect.py: performs YOLO-based image enrichment and stores results
- api/: FastAPI application and Pydantic schemas
- pipeline.py: Dagster pipeline wrapper for orchestration

## Run locally
1. Install dependencies: `pip install -r requirements.txt`
2. Start PostgreSQL (Docker Compose is included): `docker compose up -d`
3. Run the scraper: `python src/scraper.py`
4. Load raw data: `python scripts/load_raw_to_postgres.py`
5. Run dbt: `dbt run --project-dir medical_warehouse && dbt test --project-dir medical_warehouse`
6. Run YOLO enrichment: `python src/yolo_detect.py`
7. Start the API: `uvicorn api.main:app --reload`
8. Launch Dagster: `dagster dev -f pipeline.py`

## Notes
- The Telegram scraper uses the credentials in `.env`.
- The API exposes analytical endpoints for top products, channel activity, message search, and visual content.
