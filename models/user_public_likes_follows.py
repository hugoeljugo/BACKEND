from models import PostPublic, UserPublic

class UserPublicWithLikesAndFollows(UserPublic):
    likes: list["PostPublic"]
    follows: list["UserPublic"]
    followed_by: list["UserPublic"]