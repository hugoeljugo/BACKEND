from sqlmodel import Field, SQLModel

class PostBase(SQLModel):
    text: str
    likes: int | None = Field(default=0)

class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

class PostPublic(PostBase):
    id: int

class PostCreate(PostBase):
    user_id: int

class PostUpdate(PostBase):
    text: str | None = None
    likes: int | None = None
    user_id: int | None = None
