import pytest
from fastapi import status
from models import User, UserFollow

def test_follow_user(client, db_session, auth_header):
    user1 = User(username="user1", email="user1@example.com", password="password")
    user2 = User(username="user2", email="user2@example.com", password="password")
    db_session.add_all([user1, user2])
    db_session.commit()

    response = client.post(
        "/social/follow",
        headers=auth_header,
        json={"followed_username": user2.username}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"

def test_unfollow_user(client, db_session, auth_header):
    user1 = User(username="user1", email="user1@example.com", password="password")
    user2 = User(username="user2", email="user2@example.com", password="password")
    follow = UserFollow(follower_id=user1.id, followed_id=user2.id)
    db_session.add_all([user1, user2, follow])
    db_session.commit()

    response = client.post(
        "/social/unfollow",
        headers=auth_header,
        json={"unfollowed_username": user2.username}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"