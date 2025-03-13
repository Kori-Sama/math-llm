import httpx
import json
import asyncio
from typing import List, AsyncGenerator
from sse_starlette.sse import EventSourceResponse
from app.schemas import LLMRequest, LLMResponse
import os
from dotenv import load_dotenv

load_dotenv()

# 获取LLM API URL
LLM_API_URL = os.getenv("LLM_API_URL")


async def call_llm_api(query: str, history_chat: List[str]) -> AsyncGenerator[str, None]:
    """
    调用LLM API并返回流式响应
    """
    request_data = {
        "query": query,
        "history_chat": history_chat
    }
    
    async with httpx.AsyncClient() as client:
        async with client.stream('POST', LLM_API_URL, json=request_data, timeout=60.0) as response:
            if response.status_code != 200:
                error_msg = json.dumps({
                    "status": -1,
                    "error": f"LLM API请求失败: {response.status_code}",
                    "answer": ""
                })
                yield f"data:{error_msg}\n\n"
                return
                
            async for chunk in response.aiter_text():
                if chunk.startswith('data:'):
                    yield chunk
                else:
                    # 确保格式正确
                    yield f"data:{chunk}\n\n"


async def process_llm_request(request: LLMRequest) -> EventSourceResponse:
    """
    处理LLM请求并返回SSE响应
    """
    return EventSourceResponse(
        call_llm_api(request.query, request.history_chat),
        media_type="text/event-stream"
    )


async def format_history_for_llm(conversation_messages) -> List[str]:
    """
    将数据库中的对话记录格式化为LLM API所需的格式
    """
    history_chat = []
    for message in conversation_messages:
        if message.is_user:
            history_chat.append(message.content)  # 用户问题
        else:
            history_chat.append(message.content)  # AI回答
    return history_chat