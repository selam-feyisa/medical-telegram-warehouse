from pydantic import BaseModel, Field
from typing import List, Optional


class ProductReport(BaseModel):
    term: str
    count: int


class ChannelActivity(BaseModel):
    channel_name: str
    total_posts: int
    avg_views: float
    first_post_date: Optional[str] = None
    last_post_date: Optional[str] = None


class MessageSearchItem(BaseModel):
    message_id: int
    channel_name: str
    message_text: str
    views: int


class VisualContentStat(BaseModel):
    channel_name: str
    total_messages: int
    with_images: int
    image_ratio: float
