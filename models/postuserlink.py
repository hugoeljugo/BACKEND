from sqlmodel import Field, SQLModel, Relationship


class PostUserLink(SQLModel, table=True):
    post_id: int | None = Field(default=None, foreign_key="post.id", primary_key=True, ondelete="CASCADE")
    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True, ondelete="CASCADE")