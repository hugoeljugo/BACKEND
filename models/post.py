from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime
from .user import UserPublic, User
from .postuserlink import PostUserLink

class PostBase(SQLModel):
    post_body: str

class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    date: datetime = Field(default=datetime.now())
    
    liked_by: list["User"] | None = Relationship(back_populates="likes", link_model=PostUserLink)
    user: User | None = Relationship(back_populates="posts")

class PostPublic(PostBase):
    id: int
    date: datetime
    user: UserPublic

class PostPublicWithLikes(PostPublic):
    liked_by: list["UserPublic"]
    user: UserPublic

class PostCreate(PostBase):
    pass

class PostUpdate(PostBase):
    text: str | None = None
    likes: int | None = None
    user_id: int | None = None
