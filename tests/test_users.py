import pytest
from fastapi import status
from models import User
from auth.security import get_password_hash

def test_get_user_by_username(client, db_session):
    user = User(
        username="testuser",
        email="test@example.com",
        password=get_password_hash("testpass123")
    )
    db_session.add(user)
    db_session.commit()

    response = client.get(f"/users/{user.username}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "testuser"

def test_update_user_profile(client, db_session, auth_header):
    user = User(
        username="testuser",
        email="test@example.com",
        password=get_password_hash("testpass123")
    )
    db_session.add(user)
    db_session.commit()

    response = client.put(
        f"/users/{user.id}",
        headers=auth_header,
        json={"full_name": "Updated Name"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["full_name"] == "Updated Name"