from sqlmodel import Field, SQLModel
from datetime import datetime

class PostBase(SQLModel):
    text: str
    likes: int | None = Field(default=0)

class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: datetime | None = Field(default=datetime.now())

class PostPublic(PostBase):
    id: int
    date: datetime

class PostCreate(PostBase):
    user_id: int

class PostUpdate(PostBase):
    text: str | None = None
    likes: int | None = None
    user_id: int | None = None
