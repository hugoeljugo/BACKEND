from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel, create_engine
from models import User, Post, PostUserLink, UserLink
from core.config import get_settings
from auth.security import get_password_hash
import random

settings = get_settings()
engine = create_engine(settings.DATABASE_URL, echo=True)

def create_test_data():
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Create test users
        users = []
        for i in range(1, 6):
            user = User(
                username=f"test_user{i}",
                full_name=f"Test User {i}",
                email=f"test{i}@example.com",
                password=get_password_hash("password123"),
                email_verified=True,
                is_admin=True if i == 1 else False
            )
            users.append(user)
            session.add(user)
        
        session.commit()
        
        # Create some posts for each user
        posts = []
        for user in users:
            for j in range(3):  # 3 posts per user
                post = Post(
                    post_body=f"This is test post {j+1} from {user.username}",
                    user_id=user.id,
                    date=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
                )
                posts.append(post)
                session.add(post)
        
        session.commit()
        
        # Create some follows between users
        for user in users:
            # Each user follows 2 random users
            possible_follows = [u for u in users if u.id != user.id]
            for followed in random.sample(possible_follows, min(2, len(possible_follows))):
                user_link = UserLink(user_id=user.id, following_id=followed.id)
                session.add(user_link)
        
        session.commit()
        
        # Create some likes on posts
        for user in users:
            # Each user likes 5 random posts
            possible_likes = [p for p in posts if p.user_id != user.id]
            for liked_post in random.sample(possible_likes, min(5, len(possible_likes))):
                post_like = PostUserLink(user_id=user.id, post_id=liked_post.id)
                session.add(post_like)
        
        session.commit()
        
        print("Test data created successfully!")
        print(f"Created {len(users)} users")
        print(f"Created {len(posts)} posts")

if __name__ == "__main__":
    create_test_data() 