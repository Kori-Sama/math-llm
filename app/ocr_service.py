import json
import hmac
import hashlib
import base64
import datetime
import httpx
from typing import Dict, Any, Optional
import os
from app.schemas import OCRResponse, TextItem


class TencentOCRService:
    """腾讯云OCR服务类"""
    
    def __init__(self):
        # 从环境变量获取腾讯云密钥
        self.secret_id = os.getenv("TENCENT_SECRET_ID", "")
        self.secret_key = os.getenv("TENCENT_SECRET_KEY", "")
        self.region = os.getenv("TENCENT_REGION", "ap-guangzhou")
        self.endpoint = "ocr.tencentcloudapi.com"
        self.service = "ocr"
        self.version = "2018-11-19"
        self.action = "EduPaperOCR"
        
        if not self.secret_id or not self.secret_key:
            raise ValueError("请在环境变量中设置 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY")
    
    def sign(self, key: bytes, msg: str) -> bytes:
        """签名函数"""
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
    
    def get_authorization(self, params: Dict[str, Any]) -> str:
        """生成腾讯云API授权头"""
        # 获取当前时间戳
        timestamp = int(datetime.datetime.now().timestamp())
        date = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        
        # 拼接规范请求串
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{self.endpoint}\n"
        signed_headers = "content-type;host"
        payload = json.dumps(params)
        hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{hashed_request_payload}"
        
        # 拼接待签名字符串
        algorithm = "TC3-HMAC-SHA256"
        credential_scope = f"{date}/{self.service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"
        
        # 计算签名
        secret_date = self.sign(("TC3" + self.secret_key).encode("utf-8"), date)
        secret_service = self.sign(secret_date, self.service)
        secret_signing = self.sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        
        # 拼接 Authorization
        authorization = f"{algorithm} Credential={self.secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        return authorization, timestamp
    
    async def recognize_math_paper(self, image_base64: str, config: Dict[str, Any] = None) -> OCRResponse:
        """
        识别数学试题
        
        Args:
            image_base64: 图片的base64编码
            config: 扩展配置参数
        
        Returns:
            OCRResponse: 识别结果
        """
        try:
            # 准备请求参数
            params = {
                "ImageBase64": image_base64,
                "Config": json.dumps(config) if config else json.dumps({"task_type": 1, "is_structuralization": True})
            }
            
            # 生成授权头
            authorization, timestamp = self.get_authorization(params)
            
            # 准备请求头
            headers = {
                "Authorization": authorization,
                "Content-Type": "application/json; charset=utf-8",
                "Host": self.endpoint,
                "X-TC-Action": self.action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": self.version,
                "X-TC-Region": self.region
            }
            
            # 使用httpx发送同步请求
            url = f"https://{self.endpoint}"
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=params)
                response.raise_for_status()
                result = response.json()
            
            # 处理响应
            if "Error" in result.get("Response", {}):
                error = result["Response"]["Error"]
                return OCRResponse(
                    success=False,
                    message=f"腾讯云API错误: {error.get('Message', '未知错误')} (Code: {error.get('Code', 'Unknown')})"
                )
            
            # 解析成功响应
            response_data = result.get("Response", {})
            edu_paper_infos = response_data.get("EduPaperInfos", [])
            
            # 转换为简化的文本项列表
            text_items = []
            for item in edu_paper_infos:
                text_item = TextItem(
                    text=item.get("DetectedText", ""),
                    position={
                        "x": item.get("Itemcoord", {}).get("X", 0),
                        "y": item.get("Itemcoord", {}).get("Y", 0),
                        "width": item.get("Itemcoord", {}).get("Width", 0),
                        "height": item.get("Itemcoord", {}).get("Height", 0)
                    }
                )
                if text_item.text.strip():  # 只添加非空文本
                    text_items.append(text_item)
            
            return OCRResponse(
                success=True,
                message="OCR识别成功",
                data=response_data,
                text_items=text_items,
                angle=response_data.get("Angle", 0)
            )
            
        except httpx.RequestError as e:
            return OCRResponse(
                success=False,
                message=f"网络请求错误: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            return OCRResponse(
                success=False,
                message=f"HTTP状态错误: {e.response.status_code} - {str(e)}"
            )
        except json.JSONDecodeError as e:
            return OCRResponse(
                success=False,
                message=f"JSON解析错误: {str(e)}"
            )
        except Exception as e:
            return OCRResponse(
                success=False,
                message=f"未知错误: {str(e)}"
            )


# 全局OCR服务实例
ocr_service = None

def get_ocr_service() -> TencentOCRService:
    """获取OCR服务实例"""
    global ocr_service
    if ocr_service is None:
        try:
            ocr_service = TencentOCRService()
        except ValueError as e:
            raise ValueError(f"OCR服务初始化失败: {str(e)}")
    return ocr_service 