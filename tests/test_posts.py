import pytest
from fastapi import status
from models import Post, User

def test_create_post(client, db_session, auth_header):
    response = client.post(
        "/posts",
        headers=auth_header,
        json={"post_body": "Test post content"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["post_body"] == "Test post content"

def test_get_post(client, db_session):
    user = User(username="postuser", email="post@example.com")
    db_session.add(user)
    db_session.commit()
    
    post = Post(
        post_body="Test post",
        user_id=user.id
    )
    db_session.add(post)
    db_session.commit()

    response = client.get(f"/posts/{post.id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["post_body"] == "Test post"