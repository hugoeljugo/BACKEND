from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum

class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class ChatRoom(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationships
    messages: List["Message"] = Relationship(back_populates="chat_room")
    participants: List["User"] = Relationship(
        back_populates="chat_rooms",
        link_model="ChatRoomParticipant"
    )

class ChatRoomParticipant(SQLModel, table=True):
    chat_room_id: int = Field(foreign_key="chatroom.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    last_read_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Message(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    chat_room_id: int = Field(foreign_key="chatroom.id")
    sender_id: int = Field(foreign_key="user.id")
    content: str
    file_url: Optional[str] = Field(default=None)
    status: MessageStatus = Field(default=MessageStatus.SENT)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationships
    chat_room: ChatRoom = Relationship(back_populates="messages")
    sender: "User" = Relationship() 