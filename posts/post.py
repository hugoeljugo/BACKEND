from sqlmodel import Field, SQLModel
from users import User

class PostBase(SQLModel):
    text: string 
    likes: int | None = Field(default=0)

class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user: User = Field(foreign_key="user.id")

class PostPublic(PostBase):
    id: int
