import pytest
from fastapi import status
from models import User
from auth.security import get_password_hash

def test_register_user(client, db_session):
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["username"] == "testuser"

def test_login_user(client, db_session):
    user = User(
        username="testuser",
        email="test@example.com",
        password=get_password_hash("testpass123")
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/token", data={
        "username": "testuser",
        "password": "testpass123"
    })
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()