# 数学LLM项目

一个基于FastAPI的数学问答平台，集成了腾讯云OCR数学试题识别功能。

## 功能特性

- 用户注册和认证系统
- 对话管理和消息历史记录
- LLM数学问答服务
- **数学试题OCR识别** - 支持识别数学试题并转换为LaTeX格式

## 环境配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 环境变量配置

创建 `.env` 文件并配置以下环境变量：

```bash
# 腾讯云OCR服务配置
TENCENT_SECRET_ID=your_secret_id_here
TENCENT_SECRET_KEY=your_secret_key_here
TENCENT_REGION=ap-guangzhou

# 数据库配置
DATABASE_URL=your_database_url_here

# JWT秘钥
SECRET_KEY=your_jwt_secret_key_here
```

### 3. 获取腾讯云密钥

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 前往 [访问密钥管理](https://console.cloud.tencent.com/cam/capi)
3. 创建或获取 `SecretId` 和 `SecretKey`
4. 确保账户已开通 [文字识别服务](https://console.cloud.tencent.com/ocr)

## 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8123` 启动。

## OCR API 使用说明

### 1. 身份认证

所有API请求都需要先获取访问令牌：

```bash
# 用户登录获取token
curl -X POST "http://localhost:8123/api/users/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"
```

### 2. OCR识别接口

**接口地址：** `POST /api/ocr/recognize`

**请求头：**
```
Authorization: Bearer your_access_token
Content-Type: application/json
```

**请求体：**
```json
{
  "image_base64": "base64编码的图片数据",
  "config": {
    "task_type": 1,
    "is_structuralization": true,
    "if_readable_format": false
  }
}
```

**参数说明：**
- `image_base64`: 图片的Base64编码（必填）
- `config`: 扩展配置（可选）
  - `task_type`: 任务类型，0=关闭版式分析，1=启用版式分析（默认：1）
  - `is_structuralization`: 是否结构化输出（默认：true）
  - `if_readable_format`: 是否按版式整合输出（默认：false）

**响应格式：**
```json
{
  "success": true,
  "message": "OCR识别成功",
  "data": {
    // 腾讯云原始响应数据
  },
  "text_items": [
    {
      "text": "识别出的文本内容",
      "confidence": null,
      "position": {
        "x": 100,
        "y": 200,
        "width": 300,
        "height": 50
      }
    }
  ],
  "angle": 0
}
```

### 3. 使用示例

#### JavaScript示例：

```javascript
// 将图片转换为base64
function imageToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // 移除data:image/xxx;base64,前缀
      const base64 = reader.result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// 调用OCR API
async function recognizeImage(imageFile, token) {
  try {
    const base64Image = await imageToBase64(imageFile);
    
    const response = await fetch('http://localhost:8123/api/ocr/recognize', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        image_base64: base64Image,
        config: {
          task_type: 1,
          is_structuralization: true
        }
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('识别成功：', result.text_items);
      return result.text_items;
    } else {
      console.error('识别失败：', result.message);
    }
  } catch (error) {
    console.error('请求失败：', error);
  }
}
```

#### Python示例：

```python
import httpx
import base64

def recognize_image(image_path, token):
    # 读取图片并转换为base64
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # 准备请求
    url = 'http://localhost:8123/api/ocr/recognize'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        'image_base64': image_data,
        'config': {
            'task_type': 1,
            'is_structuralization': True
        }
    }
    
    # 发送请求
    with httpx.Client() as client:
        response = client.post(url, headers=headers, json=data)
        result = response.json()
    
    if result['success']:
        print('识别成功：')
        for item in result['text_items']:
            print(f"文本: {item['text']}")
            print(f"位置: {item['position']}")
    else:
        print(f'识别失败：{result["message"]}')
        
    return result
```

### 4. 测试接口

可以使用测试接口检查OCR服务配置是否正确：

```bash
curl -X POST "http://localhost:8123/api/ocr/test"
```

## 支持的图片格式

- PNG
- JPG
- JPEG
- 图片大小：Base64编码后不超过7M
- 图片下载时间：不超过3秒

## 错误处理

API会返回详细的错误信息，常见错误包括：

- `图片内容为空`
- `图片解码失败`
- `图片中未检测到文本`
- `腾讯云API错误`
- `网络请求错误`

## 注意事项

1. 确保腾讯云账户余额充足
2. 注意API调用频率限制（默认5次/秒）
3. 图片质量会影响识别准确度
4. 建议使用清晰的数学题目图片

## API文档

启动服务后，可访问 `http://localhost:8123/docs` 查看完整的API文档。
