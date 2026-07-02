from __future__ import annotations

import re
from typing import List

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import text

from api.database import get_engine
from api.schemas import ChannelActivity, MessageSearchItem, ProductReport, VisualContentStat

app = FastAPI(title="Medical Telegram Warehouse API", version="1.0.0")


def extract_keywords(text: str, limit: int = 10) -> List[str]:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    stop_words = {"the", "and", "for", "with", "this", "that", "from", "are", "was", "have", "has", "our", "now", "at", "in", "on", "to", "of", "a", "an", "is", "it", "be", "or", "na", "mg"}
    filtered = [word for word in words if word not in stop_words and len(word) > 2]
    return filtered[:limit]


@app.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/reports/top-products", response_model=list[ProductReport], tags=["Reports"])
def top_products(limit: int = Query(default=10, ge=1, le=50)) -> list[ProductReport]:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT lower(trim(regexp_replace(message_text, '[^A-Za-z0-9 ]+', ' ', 'g'))) AS term,
                       count(*) AS count
                FROM public.fct_messages
                WHERE message_text IS NOT NULL AND trim(message_text) <> ''
                GROUP BY 1
                ORDER BY 2 DESC, 1 ASC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        rows = result.fetchall()
    return [ProductReport(term=row[0], count=int(row[1])) for row in rows]


@app.get("/api/channels/{channel_name}/activity", response_model=ChannelActivity, tags=["Channels"])
def channel_activity(channel_name: str) -> ChannelActivity:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT dc.channel_name, count(f.message_id) AS total_posts, avg(f.views) AS avg_views,
                       dc.first_post_date, dc.last_post_date
                FROM public.dim_channels dc
                LEFT JOIN public.fct_messages f ON f.channel_key = dc.channel_key
                WHERE dc.channel_name = :channel_name
                GROUP BY dc.channel_name, dc.first_post_date, dc.last_post_date
                """
            ),
            {"channel_name": channel_name},
        )
        row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="channel not found")
    return ChannelActivity(
        channel_name=row[0],
        total_posts=int(row[1]),
        avg_views=float(row[2] or 0),
        first_post_date=str(row[3]) if row[3] else None,
        last_post_date=str(row[4]) if row[4] else None,
    )


@app.get("/api/search/messages", response_model=list[MessageSearchItem], tags=["Search"])
def search_messages(query: str, limit: int = Query(default=20, ge=1, le=100)) -> list[MessageSearchItem]:
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT f.message_id, dc.channel_name, f.message_text, f.views
                FROM public.fct_messages f
                JOIN public.dim_channels dc ON dc.channel_key = f.channel_key
                WHERE lower(f.message_text) LIKE :pattern
                ORDER BY f.message_id DESC
                LIMIT :limit
                """
            ),
            {"pattern": f"%{query.lower()}%", "limit": limit},
        )
        rows = result.fetchall()
    return [MessageSearchItem(message_id=int(row[0]), channel_name=row[1], message_text=row[2] or "", views=int(row[3] or 0)) for row in rows]


@app.get("/api/reports/visual-content", response_model=list[VisualContentStat], tags=["Reports"])
def visual_content() -> list[VisualContentStat]:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT dc.channel_name,
                       count(*) AS total_messages,
                       sum(CASE WHEN f.has_image THEN 1 ELSE 0 END) AS with_images,
                       avg(CASE WHEN f.has_image THEN 1.0 ELSE 0.0 END) AS image_ratio
                FROM public.fct_messages f
                JOIN public.dim_channels dc ON dc.channel_key = f.channel_key
                GROUP BY dc.channel_name
                ORDER BY with_images DESC
                """
            )
        )
        rows = result.fetchall()
    return [VisualContentStat(channel_name=row[0], total_messages=int(row[1]), with_images=int(row[2] or 0), image_ratio=float(row[3] or 0)) for row in rows]
