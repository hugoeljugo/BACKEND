from sqlmodel import Field, SQLModel, Relationship
from .postuserlink import PostUserLink

class UserLink(SQLModel, table=True):
    follower_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    followed_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)

class UserBase(SQLModel):
    username: str = Field(index=True)
    full_name: str | None = Field(default=None)

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password: str = Field(index=True)
    pfp: bytes | None = Field(default=None)
    disabled: bool | None = Field(default=False)

    likes: list["Post"] = Relationship(back_populates="liked_by", link_model=PostUserLink)
    follows: list["User"] = Relationship(back_populates="followed_by", link_model=UserLink, sa_relationship_kwargs={'foreign_keys':[UserLink.follower_id]})
    followed_by: list["User"] = Relationship(back_populates="follows", link_model=UserLink, sa_relationship_kwargs={'foreign_keys':[UserLink.followed_id]})

class UserPublic(UserBase):
    id: int



class UserCreate(UserBase):
    password: str 

class UserUpdate(UserBase):
    username: str | None = None
    password: str | None = None
    full_name: str | None = None
    pfp: bytes | None = None