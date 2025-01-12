import pytest
from fastapi import status
from models import User, ChatRoom, Message

def test_create_chat_room(client, db_session, auth_header):
    user1 = User(username="user1", email="user1@example.com", password="password")
    user2 = User(username="user2", email="user2@example.com", password="password")
    db_session.add_all([user1, user2])
    db_session.commit()

    response = client.post(
        "/chat/rooms",
        headers=auth_header,
        json={"other_user_id": user2.id}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert "id" in response.json()

def test_send_message(client, db_session, auth_header):
    user1 = User(username="user1", email="user1@example.com", password="password")
    user2 = User(username="user2", email="user2@example.com", password="password")
    chat_room = ChatRoom(participants=[user1, user2])
    db_session.add_all([user1, user2, chat_room])
    db_session.commit()

    response = client.post(
        f"/chat/rooms/{chat_room.id}/messages",
        headers=auth_header,
        json={"content": "Hello, world!"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["content"] == "Hello, world!"