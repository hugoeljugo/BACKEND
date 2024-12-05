from typing import Annotated
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
import os
import logging
from uuid import uuid4

from models import BasicFileResponse, User
from dependencies import SessionDep, get_current_active_user
from core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

@router.patch("/users/me/pfp", response_model=BasicFileResponse)
async def update_profile_picture(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    pfp: UploadFile = File(...),
):
    """Update user's profile picture"""
    file_extension = pfp.filename.split(".")[-1].lower()
    if file_extension not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    image = Image.open(pfp.file)
    fixed_size = (256, 256)
    image = image.resize(fixed_size, Image.Resampling.LANCZOS)

    file_name = f"{uuid4()}.webp"
    file_path = os.path.join(settings.UPLOAD_FOLDER, file_name)

    image.save(file_path, format="WEBP", quality=85)

    current_user.pfp = file_name
    session.add(current_user)
    session.commit()

    return JSONResponse({
        "message": "Profile picture updated successfully",
        "file_name": file_name
    })

@router.get("/{file_name}", response_class=FileResponse)
async def get_file(file_name: str):
    """Get a file by name"""
    file_path = os.path.join(settings.UPLOAD_FOLDER, file_name)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found") 