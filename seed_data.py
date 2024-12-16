from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel, create_engine, select
from models import User, Post, PostUserLink, UserFollow, Topic, PostTopic, UserTopic, Interaction, InteractionType, ChatRoom, Message, MessageStatus
from core.config import get_settings
from auth.security import get_password_hash
import random

settings = get_settings()
engine = create_engine(settings.DATABASE_URL, echo=True)

def create_test_data():
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Create test topics
        topics = []
        base_topics = ["Technology", "Sports", "Entertainment", "Science", "Politics"]
        for topic_name in base_topics:
            topic = Topic(name=topic_name)
            topics.append(topic)
            session.add(topic)
        
        session.commit()  # Commit topics first
        
        # Create subtopics
        subtopics = {
            "Technology": ["Programming", "AI", "Cybersecurity"],
            "Sports": ["Football", "Basketball", "Tennis"],
            "Entertainment": ["Movies", "Music", "Gaming"],
            "Science": ["Physics", "Biology", "Space"],
            "Politics": ["International", "Economy", "Environment"]
        }
        
        all_topics = []
        for parent_topic in topics:
            all_topics.append(parent_topic)
            for subtopic_name in subtopics[parent_topic.name]:
                subtopic = Topic(
                    name=subtopic_name,
                    parent_id=parent_topic.id
                )
                all_topics.append(subtopic)
                session.add(subtopic)
        
        session.commit()  # Commit subtopics

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
        
        session.commit()  # Commit users
        
        # Assign random topics of interest to users
        for user in users:
            # Each user is interested in 3-5 random topics
            user_topics = random.sample(all_topics, random.randint(3, 5))
            for topic in user_topics:
                user_topic = UserTopic(user_id=user.id, topic_id=topic.id)
                session.add(user_topic)
        
        session.commit()  # Commit user topics
        
        # Create some posts for each user
        posts = []
        for user in users:
            for j in range(3):  # 3 posts per user
                post = Post(
                    post_body=f"This is test post {j+1} from {user.username}",
                    user_id=user.id,
                    date=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30)),
                    view_count=random.randint(10, 100),
                    like_count=random.randint(5, 50),
                    reply_count=random.randint(0, 10),
                    share_count=random.randint(0, 5),
                    engagement_score=random.uniform(0.1, 1.0)
                )
                posts.append(post)
                session.add(post)
                user.post_count += 1
        
        session.commit()  # Commit posts before creating post-topic relationships
        
        # Now create post-topic relationships
        for post in posts:
            # Assign 1-3 random topics to each post
            post_topics = random.sample(all_topics, random.randint(1, 3))
            for topic in post_topics:
                post_topic = PostTopic(
                    post_id=post.id,  # Now post.id exists
                    topic_id=topic.id,
                    confidence=random.uniform(0.7, 1.0)
                )
                session.add(post_topic)
        
        session.commit()  # Commit post topics
        
        # Create some follows between users
        for user in users:
            # Each user follows 2 random users
            possible_follows = [u for u in users if u.id != user.id]
            for followed in random.sample(possible_follows, min(2, len(possible_follows))):
                follow = UserFollow(
                    follower_id=user.id,
                    followed_id=followed.id
                )
                session.add(follow)
                # Update follower/following counts
                user.following_count += 1
                followed.follower_count += 1
        
        session.commit()  # Commit follows
        
        # Create some likes and interactions on posts
        for user in users:
            # Each user likes and interacts with 5 random posts
            possible_likes = [p for p in posts if p.user_id != user.id]
            for liked_post in random.sample(possible_likes, min(5, len(possible_likes))):
                # Create like
                post_like = PostUserLink(user_id=user.id, post_id=liked_post.id)
                session.add(post_like)
                liked_post.like_count += 1
                liked_post.user.total_likes_received += 1
                
                # Create view interaction
                view = Interaction(
                    user_id=user.id,
                    post_id=liked_post.id,
                    interaction_type=InteractionType.VIEW,
                    duration=random.uniform(10, 300),  # 10-300 seconds
                    source=random.choice(["feed", "profile", "search"])
                )
                session.add(view)
                liked_post.view_count += 1
                liked_post.user.total_views_received += 1
        
        session.commit()  # Commit likes and interactions
        
        # Update engagement rates
        for user in users:
            total_interactions = len(session.exec(
                select(Interaction).where(Interaction.user_id == user.id)
            ).all())
            user.engagement_rate = total_interactions / user.post_count if user.post_count > 0 else 0.0
            session.add(user)
        
        session.commit()  # Final commit for engagement rates

        # Create chat rooms
        chat_rooms = []
        # Create a chat room between user1 and user2
        chat_room1 = ChatRoom()
        chat_room1.participants = [users[0], users[1]]
        chat_rooms.append(chat_room1)

        # Create a chat room between user2 and user3
        chat_room2 = ChatRoom()
        chat_room2.participants = [users[1], users[2]]
        chat_rooms.append(chat_room2)

        for room in chat_rooms:
            session.add(room)
        session.commit()

        # Add some test messages
        messages = [
            Message(
                chat_room_id=chat_room1.id,
                sender_id=users[0].id,
                content="Hey, how are you?",
                status=MessageStatus.READ
            ),
            Message(
                chat_room_id=chat_room1.id,
                sender_id=users[1].id,
                content="I'm good, thanks! How about you?",
                status=MessageStatus.READ
            ),
            Message(
                chat_room_id=chat_room2.id,
                sender_id=users[1].id,
                content="Hello there!",
                status=MessageStatus.SENT
            )
        ]

        session.add_all(messages)
        session.commit()
        
        print("Test data created successfully!")
        print(f"Created {len(users)} users")
        print(f"Created {len(posts)} posts")
        print(f"Created {len(all_topics)} topics")
        print(f"Created {len(chat_rooms)} chat rooms")
        print(f"Created {len(messages)} messages")

if __name__ == "__main__":
    create_test_data() 