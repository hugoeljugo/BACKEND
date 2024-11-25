from models import PostPublic, UserPublic, PostPublicWithLikes

class UserPublicWithLikesAndFollows(UserPublic):
    posts: list["PostPublicWithLikes"]
    likes: list["PostPublicWithLikes"]
    follows: list["UserPublic"] | None
    followed_by: list["UserPublic"] | None