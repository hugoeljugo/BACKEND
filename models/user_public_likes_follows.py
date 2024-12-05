from typing import List
from pydantic import BaseModel

from .post import PostPublicWithLikes
from .user import UserPublic

class UserPublicWithLikesAndFollows(UserPublic):
    likes: List[PostPublicWithLikes] = []
    posts: List[PostPublicWithLikes] = []
    follows: List[UserPublic] | None = None
    followed_by: List[UserPublic] | None = None