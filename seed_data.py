import random
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel, create_engine, select
from models import User, Post, PostUserLink, UserFollow, Topic, PostTopic, UserTopic, Interaction, InteractionType, ChatRoom, Message, MessageStatus
from core.config import get_settings
from auth.security import get_password_hash

# Data pools
FIRST_NAMES = [
    "Juan", "María", "Alberto", "Lucía", "Pedro", "Ana", "Carlos", "Sofia",
    "John", "Emma", "Michael", "Sarah", "David", "Isabella", "James", "Laura"
]

LAST_NAMES = [
    "Domínguez", "García", "Rodríguez", "López", "Martínez", "González",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis"
]

PROFILE_PICTURES = [
    "default_pfp.png"
]

CONVERSATION_STARTERS = [
    "Hey, how are you?",
    "Did you watch the last episode of that show?",
    "I saw the new Marvel movie, it's amazing!",
    "When are we playing Valorant?",
    "Have you started the new project?",
    "Anyone up for coffee later?",
    "Can't believe what happened in the game yesterday!",
    "Did you finish the assignment?",
    "What are your plans for the weekend?"
]

CONVERSATION_REPLIES = [
    "I'm good, thanks! How about you?",
    "Yes! It was incredible!",
    "Not yet, but I heard it's great",
    "I'm free tonight if you want to play",
    "Still working on it, need help?",
    "Sure, I'm free after 3",
    "I know right? Crazy match!",
    "Almost done, just need to review",
    "Nothing planned yet, any suggestions?"
]

POST_CONTENTS = [
    "Just finished my first project with Vue.js! 🚀",
    "Anyone else loving the new TypeScript features? #coding",
    "Beautiful day for a coffee and some coding ☕️",
    "Finally solved that bug that was driving me crazy! 🐛",
    "Learning FastAPI has been an amazing journey",
    "Who's up for a game of Valorant tonight? 🎮",
    "Just deployed my first full-stack application! 🎉",
    "Does anyone have good resources for learning Docker?",
    "The new VS Code update is amazing! 💻"
]

settings = get_settings()
engine = create_engine(settings.DATABASE_URL, echo=True)

def random_date(start_date, end_date):
    time_between = end_date - start_date
    days_between = time_between.days
    random_number_of_days = random.randrange(days_between)
    random_time = timedelta(
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    return start_date + timedelta(days=random_number_of_days) + random_time

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

        # Create users with random names and profile pictures
        users = []
        for i in range(10):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            username = f"{first_name.lower()}{random.randint(1, 999)}"
            
            user = User(
                username=username,
                email=f"{username}@example.com",
                full_name=f"{first_name} {last_name}",
                pfp=random.choice(PROFILE_PICTURES),
                password=get_password_hash("password123"),
                email_verified=random.choice([True, False])
            )
            users.append(user)
        
        session.add_all(users)
        session.commit()
        
        # Assign random topics of interest to users
        for user in users:
            # Each user is interested in 3-5 random topics
            user_topics = random.sample(all_topics, random.randint(3, 5))
            for topic in user_topics:
                user_topic = UserTopic(user_id=user.id, topic_id=topic.id)
                session.add(user_topic)
        
        session.commit()  # Commit user topics
        
        # Create posts with random content and dates
        posts = []
        start_date = datetime(2023, 1, 1)
        end_date = datetime.now()
        for i in range(50):  # Create 50 posts
            user = random.choice(users)
            post = Post(
                user_id=user.id,
                post_body=random.choice(POST_CONTENTS),
                date=random_date(start_date, end_date)
            )
            posts.append(post)
            user.post_count += 1  # Increment the user's post count
            session.add(user)  # Refresh the user object
        
        session.add_all(posts)
        session.commit()
        
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

        # Create chat rooms and messages
        chat_rooms = []
        for _ in range(5):
            participants = random.sample(users, 2)
            chat_room = ChatRoom()
            chat_room.participants = participants
            chat_rooms.append(chat_room)
        session.add_all(chat_rooms)
        session.commit()

        # Add messages with random content and dates
        messages = []
        for room in chat_rooms:
            num_messages = random.randint(3, 10)
            for _ in range(num_messages):
                is_starter = random.choice([True, False])
                content = random.choice(CONVERSATION_STARTERS if is_starter else CONVERSATION_REPLIES)
                sender = random.choice(room.participants)
                
                message = Message(
                    chat_room_id=room.id,
                    sender_id=sender.id,
                    content=content,
                    date=random_date(start_date, end_date),
                    status=random.choice(list(MessageStatus))
                )
                messages.append(message)
                
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