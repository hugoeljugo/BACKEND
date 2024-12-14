from .auth import router as auth_router
from .users import router as users_router
from .posts import router as posts_router
from .social import router as social_router
from .files import router as files_router
from .admin import router as admin_router
from .chat import router as chat_router

__all__ = [
    "auth_router", 
    "users_router", 
    "posts_router", 
    "social_router", 
    "files_router", 
    "admin_router",
    "chat_router"
] 