from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .post import Post
    from .user import User

class PostTopic(SQLModel, table=True):
    post_id: int = Field(foreign_key="post.id", primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", primary_key=True)
    confidence: float = Field(default=1.0)

class UserTopic(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", primary_key=True)

class Topic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="topic.id")
    
    # Many-to-many relationships
    posts: List["Post"] = Relationship(
        back_populates="topics",
        link_model=PostTopic
    )
    users: List["User"] = Relationship(
        back_populates="interested_topics",
        link_model=UserTopic
    )