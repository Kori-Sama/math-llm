from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


# 用户相关模型
class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


# 对话相关模型
class ConversationBase(BaseModel):
    title: str = "新对话"


class ConversationCreate(ConversationBase):
    pass


class ConversationResponse(ConversationBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# 消息相关模型
class MessageBase(BaseModel):
    content: str
    is_user: bool = True


class MessageCreate(MessageBase):
    conversation_id: int


class MessageResponse(MessageBase):
    id: int
    conversation_id: int
    created_at: datetime

    class Config:
        orm_mode = True


# LLM相关模型
class LLMRequest(BaseModel):
    query: str
    history_chat: List[str] = Field(default_factory=list)


class LLMResponse(BaseModel):
    status: int
    error: str = ""
    answer: str = ""


# Token相关模型
class Token(BaseModel):
    access_token: str
    token_type: str