from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Column, DateTime
from typing import Optional, Dict, Any
from sqlalchemy import JSON

class Log(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    level: str
    message: str
    timestamp: datetime = Field(default=datetime.now(timezone.utc))
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )
    user_id: Optional[int] = Field(default=None, foreign_key="user.id") 