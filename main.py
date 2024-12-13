from contextlib import asynccontextmanager
import asyncio
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from sqlmodel import SQLModel, create_engine, Session, select
from redis import asyncio as aioredis
from prometheus_client import Counter, Histogram

from core.config import get_settings
from core.logging_config import setup_logging
from core.tasks import clean_old_files, update_engagement_scores
from dependencies import get_session, log_requests, setup_error_handlers, setup_last_active_middleware
from routers import (
    auth_router,
    users_router,
    posts_router,
    social_router,
    files_router,
    admin_router
)

# Initialize settings and logging
settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)

# Create upload folder
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)

# Database setup
engine = create_engine(settings.DATABASE_URL, echo=True)

# Add this near the top with other global variables
redis: aioredis.Redis = None

# Define custom metrics
api_users_total = Counter(
    "api_users_total",
    "Total number of users in the system"
)

custom_latency = Histogram(
    "custom_endpoint_latency_seconds",
    "Custom latency tracking for specific operations"
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0] if route.tags else ""}-{route.name}"

async def periodic_cleanup(days: int, interval: int):
    """Periodically clean up old files"""
    while True:
        try:
            await clean_old_files(days=days)
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
        await asyncio.sleep(interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Setup and cleanup tasks for the application lifecycle"""
    global redis
    # Start background cleanup task
    cleanup_task = asyncio.create_task(
        periodic_cleanup(days=7, interval=86400)  # Clean files older than 7 days, every 24h
    )
    engagement_task = asyncio.create_task(
        update_engagement_scores(next(get_session()))
    )
    try:
        # Initialize Redis cache
        redis = await aioredis.from_url(
            settings.REDIS_URL, encoding="utf8", decode_responses=True
        )
        logger.info("Successfully connected to Redis")
        yield
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise
    finally:
        cleanup_task.cancel()
        engagement_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        # Clean up Redis connection
        if redis:
            await redis.close()

def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        openapi_tags=settings.OPENAPI_TAGS,
        contact=settings.CONTACT,
        license_info=settings.LICENSE_INFO,
        lifespan=lifespan,
        generate_unique_id_function=custom_generate_unique_id,
    )

    # Add middleware
    app.middleware("http")(log_requests)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add error handlers
    setup_error_handlers(app)

    # Add last active middleware
    setup_last_active_middleware(app)

    # Enhanced instrumentation
    Instrumentator().instrument(app)\
        .add(metrics.request_size())\
        .add(metrics.response_size())\
        .add(metrics.latency(buckets=[0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]))\
        .add(metrics.requests(should_include_handler=True))\
        .expose(app, include_in_schema=True, should_gzip=True)

    # Include routers
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(posts_router, prefix="/posts", tags=["posts"])
    app.include_router(social_router, tags=["social"])
    app.include_router(files_router, prefix="/files", tags=["files"])
    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    return app

# Create the FastAPI application
app = create_application()

def main():
    """Main function for direct script execution"""
    create_db_and_tables()
    try:
        from seed_data import create_test_data
        create_test_data()
    except Exception as e:
        logger.error(f"Failed to create test data: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        with Session(engine) as session:
            session.exec(select().limit(1))
        
        # Check Redis connection
        await redis.ping()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc),
            "version": settings.APP_VERSION
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service unavailable"
        )

if __name__ == "__main__":
    main()
