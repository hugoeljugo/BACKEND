from models import PostPublic, UserPublic

class UserPublicWithLikesAndFollows(UserPublic):
    posts: list["PostPublic"]
    likes: list["PostPublic"]
    follows: list["UserPublic"] | None
    followed_by: list["UserPublic"] | None