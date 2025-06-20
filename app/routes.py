from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

from app.database import get_db, engine
from app.models import Base, User, Conversation, Message
from app.schemas import TOTRequest, UserCreate, UserResponse, Token, ConversationCreate, ConversationResponse, MessageCreate, MessageResponse, LLMRequest, OCRRequest, OCRResponse
from app.auth import authenticate_user, create_access_token, get_password_hash, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from app.llm_service import process_llm_request, format_history_for_llm, process_tot_request
from app.ocr_service import get_ocr_service

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 创建FastAPI应用
app = FastAPI(title="数学问答平台")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境中应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/users/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    用户注册
    """
    # 检查用户名是否已存在
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已被注册")

    # 检查邮箱是否已存在
    db_email = db.query(User).filter(User.email == user.email).first()
    if db_email:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 创建新用户
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# 用户登录
@app.post("/api/users/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    用户登录接口
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# 获取当前用户信息
@app.get("/api/users/me", response_model=UserResponse)
async def read_users_me(current_user=Depends(get_current_active_user)):
    """
    获取当前登录用户的信息
    """
    return current_user


# 创建新对话
@app.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(conversation: ConversationCreate, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    创建新的对话
    """
    db_conversation = Conversation(
        title=conversation.title,
        user_id=current_user.id
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation


# 获取用户的所有对话
@app.get("/api/conversations", response_model=List[ConversationResponse])
async def get_conversations(current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    获取当前用户的所有对话列表
    """
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id).all()
    return conversations


# 获取特定对话
@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    获取指定ID的对话信息
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


# 获取对话的所有消息
@app.get("/api/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(conversation_id: int, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    获取指定对话的所有消息
    """
    # 验证对话存在且属于当前用户
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    return messages


# 创建新消息并获取LLM回复
@app.post("/api/conversations/{conversation_id}/messages")
async def create_message(conversation_id: int, message: MessageCreate, model:str="tir" ,current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    创建新消息并获取LLM的回复
    """
    # 验证对话存在且属于当前用户
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 保存用户消息
    db_message = Message(
        conversation_id=conversation_id,
        content=message.content,
        is_user=True
    )
    db.add(db_message)
    db.commit()

    # 检查是否是第一条消息，如果是则更新对话标题
    message_count = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    if message_count == 1:
        # 截取用户消息的前30个字符作为标题，如果超过30个字符则添加...
        new_title = message.content[:30] + ('...' if len(message.content) > 30 else '')
        conversation.title = new_title

    # 更新对话的更新时间
    conversation.updated_at = db.query(Message).filter(
        Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).first().created_at
    db.commit()
    
    if model == 'tot':
        llm_request = TOTRequest(
            query=message.content
        )
        # 返回流式响应
        return await process_tot_request(llm_request)

    # 获取历史消息
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    history_chat = await format_history_for_llm(messages)

    # 创建LLM请求
    llm_request = LLMRequest(
        query=message.content,
        history_chat=history_chat,
        model=model
    )

    # 返回流式响应
    return await process_llm_request(llm_request)


# 直接调用LLM（无历史记录）
@app.post("/api/llm/chat")
async def chat_with_llm(request: LLMRequest, current_user=Depends(get_current_active_user)):
    """
    直接与LLM对话，不保存历史记录
    """
    return await process_llm_request(request)


@app.post("/api/tot/chat")
async def chat_with_tot(request: TOTRequest, current_user=Depends(get_current_active_user)):
    """
    直接与LLM对话，不保存历史记录
    """
    return await process_tot_request(request)


@app.post("/api/conversations/{conversation_id}/save_response", response_model=MessageResponse)
async def save_llm_response(conversation_id: int, message: MessageCreate, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    保存LLM的回复消息
    """
    # 验证对话存在且属于当前用户
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 保存LLM回复
    db_message = Message(
        conversation_id=conversation_id,
        content=message.content,
        is_user=False
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    # 更新对话的更新时间
    conversation.updated_at = db_message.created_at
    db.commit()

    return db_message


@app.patch("/api/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, title: str, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    更新对话标题
    """
    # 验证对话存在且属于当前用户
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    conversation.title = title
    db.commit()
    return conversation


@app.post("/api/ocr/recognize", response_model=OCRResponse)
async def ocr_recognize(request: OCRRequest, current_user=Depends(get_current_active_user)):
    """
    数学试题OCR识别接口
    
    支持通过base64编码的图片识别数学试题内容，
    返回结构化的文本识别结果，包括公式的Latex格式输出。
    """
    try:
        ocr_service = get_ocr_service()
        result = await ocr_service.recognize_math_paper(
            image_base64=request.image_base64,
            config=request.config
        )
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR识别服务异常: {str(e)}"
        )


@app.post("/api/ocr/test")
async def ocr_test():
    """
    OCR服务测试接口，检查服务配置是否正确
    """
    try:
        get_ocr_service()
        return {"success": True, "message": "OCR服务配置正常"}
    except Exception as e:
        return {"success": False, "message": f"OCR服务配置异常: {str(e)}"}


@app.get("/health")
async def health_check():
    """
    API服务健康检查接口
    """
    return {"status": "ok"}
