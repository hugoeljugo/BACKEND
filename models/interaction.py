from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from enum import Enum

class InteractionType(str, Enum):
    VIEW = "view"
    LIKE = "like"
    REPLY = "reply"
    SHARE = "share"
    CLICK = "click"
    PROFILE_VIEW = "profile_view"

class Interaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    post_id: int = Field(foreign_key="post.id", index=True, ondelete="CASCADE")
    interaction_type: InteractionType
    timestamp: datetime = Field(default=datetime.now(timezone.utc))
    duration: float | None = Field(default=None)  # For view duration tracking
    source: str | None = Field(default=None)  # feed, profile, search, etc.