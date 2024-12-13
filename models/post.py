from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from .topic import PostTopic
from .postuserlink import PostUserLink
from .user import UserPublic

if TYPE_CHECKING:
    from .user import User
    from .topic import Topic

class PostBase(SQLModel):
    post_body: str

class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True, ondelete="CASCADE")
    date: datetime = Field(default=datetime.now(timezone.utc))
    
    # Engagement metrics
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)
    reply_count: int = Field(default=0)
    share_count: int = Field(default=0)
    engagement_score: float = Field(default=0.0)
    
    # Content type flags
    has_image: bool = Field(default=False)
    has_link: bool = Field(default=False)
    
    # Relationships
    liked_by: List["User"] = Relationship(back_populates="likes", link_model=PostUserLink)
    user: "User" = Relationship(back_populates="posts")
    topics: List["Topic"] = Relationship(back_populates="posts", link_model=PostTopic)
    
    # Self-referential relationship for replies
    parent_id: Optional[int] = Field(default=None, foreign_key="post.id")
    replies: List["Post"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "cascade": "all, delete",
            "remote_side": "Post.id"
        }
    )
    parent: Optional["Post"] = Relationship(
        back_populates="replies",
        sa_relationship_kwargs={"remote_side": "[Post.parent_id]"}
    )

class PostPublic(PostBase):
    id: int
    date: datetime
    user: UserPublic
    view_count: int
    like_count: int
    reply_count: int
    share_count: int
    has_image: bool
    has_link: bool
    parent_id: Optional[int]  # To show if it's a reply
    is_liked_by_user: Optional[bool] = None  # Add this instead

class PostCreate(PostBase):
    pass

class PostUpdate(PostBase):
    text: str | None = None
    likes: int | None = None
    user_id: int | None = None
