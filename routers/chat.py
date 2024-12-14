from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, UploadFile, File, HTTPException
from typing import Annotated, Dict, List
import json
from datetime import datetime, timezone
from sqlalchemy import func
from sqlmodel import select
import logging
import os
from uuid import uuid4

from models import User, ChatRoom, Message, ChatRoomParticipant, MessageStatus
from dependencies import get_current_active_user, SessionDep
from core.config import get_settings
from models.response import BasicFileResponse

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    async def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)

manager = ConnectionManager()

@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    try:
        await manager.connect(websocket, current_user.id)
        
        try:
            while True:
                data = await websocket.receive_json()
                
                if data["type"] == "message":
                    # Create and save message
                    message = Message(
                        chat_room_id=data["chat_room_id"],
                        sender_id=current_user.id,
                        content=data["content"],
                        file_url=data.get("file_url")
                    )
                    session.add(message)
                    
                    # Update chat room last message time
                    chat_room = session.get(ChatRoom, data["chat_room_id"])
                    chat_room.last_message_at = datetime.now(timezone.utc)
                    
                    session.commit()
                    session.refresh(message)
                    
                    # Send to all participants
                    for participant in chat_room.participants:
                        if participant.id != current_user.id:
                            await manager.send_message({
                                "type": "message",
                                "message_id": message.id,
                                "chat_room_id": message.chat_room_id,
                                "sender_id": message.sender_id,
                                "content": message.content,
                                "file_url": message.file_url,
                                "timestamp": message.created_at.isoformat()
                            }, participant.id)
                    
        except WebSocketDisconnect:
            await manager.disconnect(current_user.id)
            
    except Exception as e:
        await websocket.close()
        logger.error(f"WebSocket error: {e}")

@router.post("/rooms")
async def create_chat_room(
    other_user_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new private chat room"""
    # Check if chat room already exists
    existing_room = session.exec(
        select(ChatRoom)
        .join(ChatRoomParticipant)
        .where(
            ChatRoomParticipant.user_id.in_([current_user.id, other_user_id])
        )
        .group_by(ChatRoom.id)
        .having(func.count() == 2)
    ).first()
    
    if existing_room:
        return existing_room
    
    other_user = session.get(User, other_user_id)
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    chat_room = ChatRoom()
    chat_room.participants = [current_user, other_user]
    
    session.add(chat_room)
    session.commit()
    session.refresh(chat_room)
    
    return chat_room

@router.get("/rooms")
async def get_chat_rooms(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get all chat rooms for current user"""
    query = (
        select(ChatRoom)
        .join(ChatRoomParticipant)
        .where(ChatRoomParticipant.user_id == current_user.id)
        .order_by(ChatRoom.last_message_at.desc())
    )
    return session.exec(query).all()

@router.get("/rooms/{room_id}/messages")
async def get_messages(
    room_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get messages for a specific chat room"""
    chat_room = session.get(ChatRoom, room_id)
    if not chat_room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Verify user is participant
    if current_user.id not in [p.id for p in chat_room.participants]:
        raise HTTPException(status_code=403, detail="Not a participant")
    
    # Update last read timestamp
    participant = session.exec(
        select(ChatRoomParticipant)
        .where(
            ChatRoomParticipant.chat_room_id == room_id,
            ChatRoomParticipant.user_id == current_user.id
        )
    ).first()
    participant.last_read_at = datetime.now(timezone.utc)
    session.add(participant)
    session.commit()
    
    return chat_room.messages

@router.post("/upload", response_model=BasicFileResponse)
async def upload_file(
    chat_room_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    file: UploadFile = File(...)
):
    """Upload a file to a chat"""
    chat_room = session.get(ChatRoom, chat_room_id)
    if not chat_room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    if current_user.id not in [p.id for p in chat_room.participants]:
        raise HTTPException(status_code=403, detail="Not a participant")
    
    # Save file
    file_extension = file.filename.split(".")[-1]
    file_name = f"chat_{uuid4()}.{file_extension}"
    file_path = os.path.join(settings.UPLOAD_FOLDER, file_name)
    
    with open(file_path, "wb+") as file_object:
        file_object.write(await file.read())
    
    return BasicFileResponse(message="File uploaded successfully", file_name=file_name) 