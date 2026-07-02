from dagster import job, op, schedule

from scripts.load_raw_to_postgres import main as load_raw
from src.scraper import main as scrape_data
from src.yolo_detect import main as run_yolo


@op
def scrape_telegram_data():
    scrape_data()


@op
def load_raw_to_postgres():
    load_raw()


@op
def run_dbt_transformations():
    import subprocess
    subprocess.run(["dbt", "run", "--project-dir", "medical_warehouse"], check=True)
    subprocess.run(["dbt", "test", "--project-dir", "medical_warehouse"], check=True)


@op
def run_yolo_enrichment():
    run_yolo()


@job
def medical_pipeline():
    run_dbt_transformations.after(load_raw_to_postgres)
    run_yolo_enrichment.after(load_raw_to_postgres)
    load_raw_to_postgres.after(scrape_telegram_data)


@schedule(job=medical_pipeline, cron_schedule="0 0 * * *")
def daily_schedule(context):
    return {}
