from sqlmodel import Field, SQLModel, Relationship
from .postuserlink import PostUserLink
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
PFP = ROOT_DIR / 'default_pfp.png'


class UserLink(SQLModel, table=True):
    user_id: int = Field(
        default=None, 
        foreign_key="user.id", 
        primary_key=True, 
        ondelete="CASCADE"
    )
    following_id: int  = Field(
        default=None, 
        foreign_key="user.id", 
        primary_key=True, 
        ondelete="CASCADE"
    )


class UserBase(SQLModel):
    username: str = Field(index=True)
    full_name: str = Field(default=None)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password: str = Field(index=True)
    pfp: str | None = Field(default='default_pfp.png' )
    disabled: bool | None = Field(default=False)

    likes: list["Post"] = Relationship(
        back_populates="liked_by", link_model=PostUserLink
    )
    posts: list["Post"] = Relationship(back_populates="user")


class UserPublic(UserBase):
    pfp: str


class UserCreate(UserBase):
    password: str


class UserUpdate(UserBase):
    username: str | None = None
    password: str | None = None
    full_name: str | None = None
    pfp: bytes | None = None
