from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import ARRAY, Column, String
from .postuserlink import PostUserLink
from pathlib import Path
from datetime import datetime, timezone
from .topic import UserTopic
from typing import List
from .chat import ChatRoom, ChatRoomParticipant
from typing import Optional

ROOT_DIR = Path(__file__).parent.parent
PFP = ROOT_DIR / 'default_pfp.png'

# Add this class to handle the follow relationships
class UserFollow(SQLModel, table=True):
    follower_id: int = Field(
        foreign_key="user.id",
        primary_key=True,
        ondelete="CASCADE"
    )
    followed_id: int = Field(
        foreign_key="user.id",
        primary_key=True,
        ondelete="CASCADE"
    )
class UserBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    full_name: str = Field(default=None)
    email: str = Field(index=True)


class User(UserBase, table=True):
    password: str = Field(index=True)
    pfp: str | None = Field(default='default_pfp.png' )
    disabled: bool | None = Field(default=False)
    is_admin: bool = Field(default=False)
    email_verified: bool = Field(default=False)
    verification_code: str | None = Field(default=None)
    verification_code_expires: datetime | None = Field(default=None)
    two_factor_enabled: bool = Field(default=False)
    two_factor_secret: str | None = Field(default=None)
    
    # Engagement metrics
    follower_count: int = Field(default=0)
    following_count: int = Field(default=0)
    post_count: int = Field(default=0)
    total_likes_received: int = Field(default=0)
    total_views_received: int = Field(default=0)
    engagement_rate: float = Field(default=0.0)
    account_creation_date: datetime = Field(default=datetime.now(timezone.utc))
    last_active: datetime = Field(default=datetime.now(timezone.utc))
    
    # User categorization
    is_verified: bool = Field(default=False)

    # Self-referential relationships for follows/followers
    followers: list["User"] = Relationship(
        back_populates="following",
        link_model=UserFollow,
        sa_relationship_kwargs={
            'primaryjoin': 'User.id==UserFollow.followed_id',
            'secondaryjoin': 'User.id==UserFollow.follower_id'
        }
    )
    following: list["User"] = Relationship(
        back_populates="followers",
        link_model=UserFollow,
        sa_relationship_kwargs={
            'primaryjoin': 'User.id==UserFollow.follower_id',
            'secondaryjoin': 'User.id==UserFollow.followed_id'
        }
    )
    
    likes: list["Post"] = Relationship(
        back_populates="liked_by", link_model=PostUserLink
    )
    posts: list["Post"] = Relationship(back_populates="user")
    
    # Add interested_topics relationship
    interested_topics: List["Topic"] = Relationship(
        back_populates="users",
        link_model=UserTopic
    )

    # Add chat relationships
    chat_rooms: List[ChatRoom] = Relationship(
        back_populates="participants",
        link_model=ChatRoomParticipant
    )

class UserPublic(UserBase):
    pfp: str
    is_admin: bool
    email_verified: bool
    two_factor_enabled: bool
    total_likes_received: int
    post_count: int
    follower_count: int
    following_count: int
    is_followed_by_user: Optional[bool] = None # Only used in response models

class UserCreate(UserBase):
    password: str


class UserUpdate(UserBase):
    username: str | None = None
    password: str | None = None
    full_name: str | None = None
    pfp: bytes | None = None
