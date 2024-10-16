from sqlmodel import Field, SQLModel

class UserBase(SQLModel):
    username: str = Field(index=True)

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password: str = Field(index=True)
    full_name: str | None = Field(default=None)
    disabled: bool | None = Field(default=False)

class UserPublic(UserBase):
    id: int
    full_name: str

class UserCreate(UserBase):
    password: str 
    full_name: str | None = None

class UserUpdate(UserBase):
    username: str | None = None
    password: str | None = None
    full_name: str | None = None