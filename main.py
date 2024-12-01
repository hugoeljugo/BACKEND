from datetime import datetime, timedelta, timezone
from time import time
from typing import Annotated, Optional
from uuid import uuid4
import asyncio
import logging
import os

from cache import cache_response
from core.tasks import clean_old_files
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    status,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Security,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    APIKeyHeader,
)
from fastapi.routing import APIRoute
from sqlmodel import Session, select, col, SQLModel
from pydantic import BaseModel
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
import jwt
from PIL import Image
from redis import asyncio as aioredis
from prometheus_fastapi_instrumentator import Instrumentator

from core.config import get_settings
from core.logging_config import setup_logging
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
    PostUserLink,
    BasicResponse,
    BasicFileResponse,
    Log,
)

from sqlmodel import create_engine

settings = get_settings()

# Setup structured logging
setup_logging()

# Create upload folder
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)

# Database setup
engine = create_engine(settings.DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def main():
    create_db_and_tables()


def get_session():
    with Session(engine) as session:
        yield session


def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0] if route.tags else ""}-{route.name}"


# FastAPI app initialization
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_tags=settings.OPENAPI_TAGS,
    contact=settings.CONTACT,
    license_info=settings.LICENSE_INFO,
)

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time

    logger.info(
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Status: {response.status_code} | "
        f"Process Time: {process_time:.2f}s"
    )
    return response


def setup_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        error_id = str(uuid4())
        logger.error(
            f"Unhandled error {error_id}: {str(exc)}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "method": request.method,
                "error_id": error_id,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred", "error_id": error_id},
        )


# Add to main.py
app.middleware("http")(log_requests)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def startup_event():
    try:
        # Initialize Redis cache
        redis = aioredis.from_url(
            settings.REDIS_URL, encoding="utf8", decode_responses=True
        )
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise


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

SessionDep = Annotated[Session, Depends(get_session)]

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

    user.posts.sort(key=lambda post: post.date, reverse=True)
    user.likes.sort(key=lambda post: post.date, reverse=True)
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
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


async def get_current_user(request: Request, session: SessionDep):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Obtener token desde cookies
        token = request.cookies.get("access_token")
        if not token:
            raise credentials_exception
        # Eliminar prefijo "Bearer"
        token = token.replace("Bearer ", "")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
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


ActiveUser = Annotated[User, Depends(get_current_active_user)]


async def admin_only(current_user: ActiveUser) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


AdminUser = Annotated[User, Depends(admin_only)]

# ============= Authentication Endpoints =============


async def rate_limit(key_prefix: str, limit: int, window: int = 60) -> None:
    """
    Rate limiting dependency
    :param key_prefix: Prefix for the Redis key
    :param limit: Number of requests allowed per window
    :param window: Time window in seconds
    """
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        key = f"rate_limit:{key_prefix}:{int(time.time() // window)}"

        requests = await redis.incr(key)
        if requests == 1:
            await redis.expire(key, window)

        if requests > limit:
            raise HTTPException(status_code=429, detail="Too many requests")
    except Exception as e:
        logger.error(f"Rate limit error: {str(e)}")
        # Allow request to proceed if Redis is down
        pass


@app.post("/token", response_model=BasicResponse, tags=["auth"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
    _: Annotated[
        None, Depends(lambda: rate_limit("login", settings.LOGIN_ATTEMPTS_PER_MINUTE))
    ],
) -> JSONResponse:
    """
    Login endpoint to obtain access token.

    Rate limited to prevent brute force attacks.
    Returns a JWT token in an HTTP-only cookie.
    """
    try:
        user = authenticate_user(form_data.username, form_data.password, session)
        if not user:
            logger.warning(f"Failed login attempt for user: {form_data.username}")
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )

        logger.info(f"Successful login for user: {user.username}")
        response = JSONResponse({"message": "Login successful"})
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=True,
            samesite="Lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return response

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/logout", response_model=BasicResponse, tags=["auth"])
async def logout():
    """
    Logout endpoint that clears the authentication cookie.
    """
    try:
        response = JSONResponse({"message": "Logged out"})
        response.delete_cookie("access_token")
        logger.info("User logged out successfully")
        return response
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        raise HTTPException(status_code=500, detail="Error during logout")


# ============= User Management Endpoints =============


@app.post("/users", response_model=BasicResponse, tags=["users"])
async def create_user(user: UserCreate, session: SessionDep) -> BasicResponse:
    """
    Create a new user account.

    Validates username and password, checks for duplicates,
    and sets up initial authentication.
    """
    user_db = User.model_validate(user)
    if (not user_db.username.strip()) or user_db.username == "me":
        raise HTTPException(status_code=400, detail="User is not valid")
    if not user_db.password.strip():
        raise HTTPException(status_code=400, detail="Password is not valid")
    if get_user(user_db.username, session):
        raise HTTPException(status_code=409, detail="User already exists")
    user_db.password = get_password_hash(user_db.password)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_db.username}, expires_delta=access_token_expires
    )
    response = JSONResponse({"message": f"User {user.username} created successfully"})
    # Configurar cookie HttpOnly
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,  # Evita acceso desde JavaScript
        secure=True,  # Solo para HTTPS
        samesite="Lax",  # Cambiar según necesidad
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@app.get("/users/me", response_model=UserPublicWithLikesAndFollows, tags=["users"])
@cache_response(settings.CACHE_EXPIRE_TIME)  # Cache for 1 minute
async def get_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)], session: SessionDep
) -> UserPublicWithLikesAndFollows:
    """
    Get current user's profile information including their likes and follows.
    Requires authentication.
    """
    user = get_user_with_follows(current_user.username, session)
    return user


@app.patch("/users/me", response_model=UserPublic, tags=["users"])
async def update_own_user(
    user: UserUpdate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserPublic:
    """
    Update current user's profile information.
    Requires authentication.
    """
    user_db = User.model_validate(user)
    user_data = user_db.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@app.delete("/users", response_model=BasicResponse, tags=["users"])
async def delete_user_me(
    session: SessionDep, current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Delete current user's account.
    This action is irreversible.
    """
    session.delete(current_user)
    session.commit()
    return JSONResponse(
        {"message": f"User {current_user.username} deleted successfully."}
    )


# ============= Profile Picture Endpoints =============


@app.patch("/users/me/pfp", response_model=BasicFileResponse, tags=["users"])
async def update_profile_picture(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    pfp: UploadFile = File(...),
):
    """
    Update user's profile picture.

    Accepts: jpg, jpeg, png, webp
    Max size: 10MB
    Image will be processed and optimized in the background.
    """
    # Validate image format
    file_extension = pfp.filename.split(".")[-1].lower()
    if file_extension not in settings.ALLOWED_IMAGE_TYPES:
        logger.warning(f"Invalid file format attempted: {file_extension}")
        raise HTTPException(status_code=400, detail="Unsupported image format")

    # Cargar la imagen usando PIL
    image = Image.open(pfp.file)

    # Redimensionar la imagen al tamaño fijo (ejemplo: 256x256 píxeles)
    fixed_size = (256, 256)
    image = image.resize(fixed_size, Image.Resampling.LANCZOS)

    # Convertir a WEBP para reducir el tamaño (si no es ya WEBP)
    file_name = f"{uuid4()}.webp"
    file_path = os.path.join(settings.UPLOAD_FOLDER, file_name)

    # Guardar la imagen procesada en el disco
    image.save(file_path, format="WEBP", quality=85)  # Ajustar calidad si es necesario

    # Actualizar la referencia del usuario en la base de datos
    current_user.pfp = file_name
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    # Devolver una respuesta JSON
    return JSONResponse(
        {"message": "Profile picture updated successfully", "file_name": file_name}
    )


# ============= Post Management Endpoints =============


@app.post(
    "/posts",
    response_model=PostPublic,
    tags=["posts"],
    dependencies=[Depends(lambda: rate_limit("posts", settings.POSTS_PER_MINUTE))],
)
async def create_post(
    post: PostCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PostPublic:
    """
    Create a new post.
    Rate limited to prevent spam.
    """
    try:
        post_db = Post.model_validate(post)
        post_db.user_id = current_user.id
        session.add(post_db)
        session.commit()
        session.refresh(post_db)
        logger.info(f"Post created successfully by user {current_user.username}")
        return post_db
    except Exception as e:
        logger.error(f"Error creating post by user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating post")


@app.get("/posts/me", response_model=list[PostPublicWithLikes], tags=["posts"])
async def get_own_posts(
    current_user: Annotated[User, Depends(get_current_active_user)], session: SessionDep
):
    """
    Get all posts created by the current user.
    Includes like information.
    """
    return current_user.posts


@app.get("/posts/{post_id}", response_model=PostPublicWithLikes, tags=["posts"])
async def get_post(post_id: int, session: SessionDep) -> PostPublicWithLikes:
    """
    Get a specific post by its ID.
    Includes like information.
    """
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
    """
    Delete a specific post.
    Only the post owner can delete it.
    """
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


# ============= Social Interaction Endpoints =============


@app.post("/follow", response_model=BasicResponse, tags=["social"])
async def follow_user(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    followed_username: str,
):
    """
    Follow another user.
    Cannot follow the same user multiple times.
    """
    followed = get_user(followed_username, session)

    if not followed:
        raise HTTPException(status_code=404, detail="Followed user not found")

    existing_link = session.exec(
        select(UserLink).where(
            UserLink.user_id == current_user.id, UserLink.following_id == followed.id
        )
    ).first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Already following this user")

    user_link = UserLink(user_id=current_user.id, following_id=followed.id)
    session.add(user_link)
    session.commit()
    session.refresh(user_link)
    return JSONResponse(
        {
            "message": f"User {current_user.username} followed {followed.username} successfully."
        }
    )


@app.delete("/follow", response_model=BasicResponse, tags=["social"])
async def unfollow_user(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    unfollowed_username: str,
):
    """
    Unfollow a user that you are currently following.
    """
    unfollowed = get_user(unfollowed_username, session)

    if not unfollowed:
        raise HTTPException(status_code=404, detail="Unfollowed user not found")

    existing_link = session.exec(
        select(UserLink).where(
            UserLink.user_id == current_user.id, UserLink.following_id == unfollowed.id
        )
    ).first()

    if not existing_link:
        raise HTTPException(status_code=400, detail="Not following this user")

    session.delete(existing_link)
    session.commit()
    return JSONResponse(
        {
            "message": f"User {current_user.username} unfollowed the user {unfollowed.username} successfully."
        }
    )


@app.post("/like", response_model=BasicResponse, tags=["social"])
async def like_post(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    post_id: int,
):
    """
    Like a post.
    Cannot like the same post multiple times.
    """
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_link = session.exec(
        select(PostUserLink).where(
            PostUserLink.user_id == current_user.id, PostUserLink.post_id == post.id
        )
    ).first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Already liking this post")

    post_user_link = PostUserLink(user_id=current_user.id, post_id=post.id)
    session.add(post_user_link)
    session.commit()
    session.refresh(post_user_link)
    return JSONResponse(
        {
            "message": f"User {current_user.username} liked the post {post.id} successfully."
        }
    )


# ============= User Profile Endpoints =============


@app.get(
    "/users/{username}", response_model=UserPublicWithLikesAndFollows, tags=["users"]
)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_user_by_username(username: str, session: SessionDep):
    """
    Get public profile information for any user.
    Includes their posts, likes, and follow information.
    Response is cached for 5 minutes.
    """
    try:
        user = get_user_with_follows(username, session)
        if not user:
            logger.warning(f"User not found: {username}")
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        logger.error(f"Error fetching user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching user")


@app.get(
    "/users/{username}/posts", response_model=list[PostPublicWithLikes], tags=["users"]
)
async def get_user_posts(username: str, session: SessionDep):
    """
    Get all posts from a specific user.
    Includes like information for each post.
    """
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.posts


@app.get(
    "/users/{username}/likes", response_model=list[PostPublicWithLikes], tags=["users"]
)
async def get_user_likes(username: str, session: SessionDep):
    """
    Get all posts that a specific user has liked.
    """
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.likes


def get_user_with_follows(username, session):
    user = get_user(username, session)
    if not user:
        return False
    user_public = UserPublicWithLikesAndFollows(
        username=user.username,
        full_name=user.full_name,
        likes=user.likes,
        posts=user.posts,
        pfp=user.pfp,
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


@app.get("/files/{file_name}", response_model=bytes)
async def get_file(file_name: str):
    file_path = os.path.join(settings.UPLOAD_FOLDER, file_name)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")


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


api_key_header = APIKeyHeader(name=settings.API_KEY_NAME, auto_error=False)


@app.post("/api/logs", response_model=Log)
async def create_log(
    request: Request,
    log: Log,
    session: SessionDep,
    current_user: Optional[ActiveUser] = None,
    api_key: Optional[str] = Security(api_key_header),
) -> Log:
    # Allow internal requests without authentication
    if request.client.host == "127.0.0.1":
        is_authorized = True
    else:
        is_authorized = current_user is not None or api_key == API_KEY

    if not is_authorized:
        raise HTTPException(status_code=401, detail="Authentication required")

    db_log = Log(
        level=log.level,
        message=log.message,
        context=log.context,
        user_id=current_user.id if current_user else None,
    )
    session.add(db_log)
    session.commit()
    session.refresh(db_log)
    return db_log


@app.get("/logs", tags=["logs"])
async def get_logs(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    level: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
):
    query = select(Log)
    if level:
        query = query.where(Log.level == level)
    if from_date:
        query = query.where(Log.timestamp >= from_date)
    if to_date:
        query = query.where(Log.timestamp <= to_date)
    return session.exec(query).all()


@app.get("/posts/feed", response_model=list[PostPublicWithLikes])
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_posts_feed(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    try:
        offset = (page - 1) * limit
        posts = session.exec(
            select(Post).order_by(Post.date.desc()).offset(offset).limit(limit)
        ).all()
        logger.info(f"Feed fetched for user {current_user.username}: page {page}")
        return posts
    except Exception as e:
        logger.error(f"Error fetching feed for user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching feed")


@app.post("/admin/cache/clear")
async def clear_cache(current_user: AdminUser):
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.flushall()
        logger.info(f"Cache cleared by admin: {current_user.username}")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Error clearing cache")


@app.on_event("startup")
async def setup_periodic_tasks():
    async def cleanup_task():
        while True:
            await clean_old_files(days=7)
            await asyncio.sleep(86400)  # Wait 24 hours

    asyncio.create_task(cleanup_task())


if __name__ == "__main__":
    main()
