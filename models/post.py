from sqlmodel import Field, SQLModel
from datetime import datetime

class PostBase(SQLModel):
    text: str

class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: datetime = Field(default=datetime.now())
    likes: int = Field(default=0)

class PostPublic(PostBase):
    id: int
    date: datetime
    likes: int

class PostCreate(PostBase):
    user_id: int

class PostUpdate(PostBase):
    text: str | None = None
    likes: int | None = None
    user_id: int | None = None
