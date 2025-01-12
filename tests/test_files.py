import pytest
from fastapi import status
from io import BytesIO

def test_upload_profile_picture(client, db_session, auth_header):
    file_content = BytesIO(b"fake image data")
    file_content.name = "test_image.png"

    response = client.patch(
        "/users/me/pfp",
        headers=auth_header,
        files={"pfp": ("test_image.png", file_content, "image/png")}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "file_url" in response.json()