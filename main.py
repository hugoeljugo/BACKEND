from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
import os
import io
from contextlib import asynccontextmanager
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    status,
    WebSocket,
    WebSocketDisconnect,
    Query,
    UploadFile,
    File,
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select, col
from models import (
    User,
    UserPublic,
    UserCreate,
    UserUpdate,
    UserPublicWithLikesAndFollows,
    UserLink,
    Post,
    PostPublic,
    PostCreate,
    PostUpdate,
    PostPublicWithLikes,
)


# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "a9c4d905ad78133bcf5b5faa1ccaef8d3a2446c595719b10a273c02a5a38d065"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
db_name = os.getenv("DB_NAME")
DATABASE_URL = f"postgresql://{db_user}:{db_pass}@localhost:5432/{db_name}"

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def main():
    create_db_and_tables()


def get_session():
    with Session(engine) as session:
        yield session

def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0] if route.tags else ""}-{route.name}"


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(generate_unique_id_function=custom_generate_unique_id)

origins = [
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.broadcast(f"Client #{len(self.active_connections)} joined the chat")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(username: str, session: Session):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        return False
    return user


def authenticate_user(username: str, password: str, session: SessionDep):
    user = get_user(username, session)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(username=token_data.username, session=session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.patch("/users/me", response_model=UserPublic, tags=["users"])
async def update_own_user(
    user: UserUpdate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserPublic:
    user_db = User.model_validate(user)
    user_data = user.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@app.patch("/users/me/pfp", tags=["users"])
async def update_profile_picture(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    file: UploadFile = File(...),
):
    image_data = await file.read()

    current_user.pfp = image_data
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return StreamingResponse(io.BytesIO(current_user.pfp), media_type="image/jpeg")


@app.post("/users", response_model=UserPublic, tags=["users"])
async def create_user(user: UserCreate, session: SessionDep) -> UserPublic:
    user_db = User.model_validate(user)
    if (not user_db.username) or user_db.username == "me":
        raise HTTPException(status_code=400, detail="User is not valid")
    if get_user(user_db.username, session):
        raise HTTPException(status_code=409, detail="User already exists")
    user_db.password = get_password_hash(user_db.password)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    return user_db


@app.post("/token", tags=["users"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> Token:
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.post("/posts", response_model=PostPublic, tags=["posts"])
async def create_post(
    post: PostCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PostPublic:
    post_db = Post.model_validate(post)
    post_db.user_id = current_user.id
    post_db.date = datetime.now()
    session.add(post_db)
    session.commit()
    session.refresh(post_db)
    return post_db


@app.get("/posts/me", response_model=list[PostPublicWithLikes], tags=["posts"])
async def get_own_posts(
    current_user: Annotated[User, Depends(get_current_active_user)], session: SessionDep
):
    return current_user.posts


@app.get("/posts/{post_id}", response_model=PostPublicWithLikes, tags=["posts"])
async def get_post(post_id: int, session: SessionDep) -> PostPublicWithLikes:
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.delete("/posts/{post_id}", response_model=PostPublic, tags=["posts"])
async def delete_post(
    post_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PostPublic:
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not post.user_id == current_user.id:
        raise HTTPException(
            status_code=401, detail="You dont have permission to do this"
        )
    session.delete(post)
    session.commit()
    return post


@app.get("/users/{username}/posts", response_model=list[PostPublicWithLikes], tags=["users"])
async def read_user_posts(username: str, session: SessionDep):
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.posts


@app.get("/users/me", response_model=UserPublicWithLikesAndFollows, tags=["users"])
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
) -> UserPublicWithLikesAndFollows:
    user = get_user_with_follows(current_user.username, session)
    return user


def get_user_with_follows(username, session):
    user = get_user(username, session)
    if not user:
        return False
    user_public = UserPublicWithLikesAndFollows(
        username=user.username,
        full_name=user.full_name,
        likes=user.likes,
        posts=user.posts,
        follows=None,
        followed_by=None,
    )
    user_public.follows = session.exec(
        select(User).where(
            col(User.id).in_(
                select(UserLink.following_id).where(user.id == UserLink.user_id)
            )
        )
    ).all()
    user_public.followed_by = session.exec(
        select(User).where(
            col(User.id).in_(
                select(UserLink.user_id).where(user.id == UserLink.following_id)
            )
        )
    ).all()
    return user_public


@app.get(
    "/users/{username}", response_model=UserPublicWithLikesAndFollows, tags=["users"]
)
async def read_user(username: str, session: SessionDep):
    user = get_user_with_follows(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/me/pfp", tags=["users"])
async def get_profile_picture(
    session: SessionDep, current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.pfp is None:
        raise HTTPException(status_code=404, detail="Profile picture not found")

    return StreamingResponse(io.BytesIO(current_user.pfp), media_type="image/jpeg")

@app.get("/users/{username}/pfp", tags=["users"])
async def get_profile_picture(
    session: SessionDep, username: str
):
    user = get_user(username, session)
    if user.pfp is None:
        raise HTTPException(status_code=404, detail="Profile picture not found")

    return StreamingResponse(io.BytesIO(user.pfp), media_type="image/jpeg")


@app.post("/follow", response_model=UserLink, tags=["users"])
async def follow_user(session: SessionDep, follower_id: str, followed_id: str):
    follower = get_user(follower_id, session)
    followed = get_user(followed_id, session)

    if not follower:
        raise HTTPException(status_code=404, detail="Follower not found")
    if not followed:
        raise HTTPException(status_code=404, detail="Followed user not found")

    existing_link = session.exec(
        select(UserLink).where(
            UserLink.follower_id == follower_id, UserLink.followed_id == followed_id
        )
    ).first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Already following this user")

    user_link = UserLink(follower_id=follower_id, followed_id=followed_id)
    session.add(user_link)
    session.commit()
    session.refresh(user_link)
    return user_link


@app.get("/users/me/items")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return [{"item_id": "Foo", "owner": current_user.username}]


@app.get("/test")
async def test():
    return {"message": "this is a test"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = len(manager.active_connections) + 1
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")


if __name__ == "__main__":
    main()
