from sqlmodel import Field, SQLModel, Relationship
from .postuserlink import PostUserLink


class UserLink(SQLModel, table=True):
    user_id: int = Field(
        default=None, 
        foreign_key="user.id", 
        primary_key=True
    )
    following_id: int  = Field(
        default=None, 
        foreign_key="user.id", 
        primary_key=True
    )


class UserBase(SQLModel):
    username: str = Field(index=True)
    full_name: str = Field(default=None)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password: str = Field(index=True)
    pfp: bytes | None = Field(default=None)
    disabled: bool | None = Field(default=False)

    likes: list["Post"] = Relationship(
        back_populates="liked_by", link_model=PostUserLink
    )


class UserPublic(UserBase):
    pass


class UserCreate(UserBase):
    password: str


class UserUpdate(UserBase):
    username: str | None = None
    password: str | None = None
    full_name: str | None = None
    pfp: bytes | None = None
