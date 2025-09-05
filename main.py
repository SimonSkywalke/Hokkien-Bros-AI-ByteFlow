#!/usr/bin/env python3
"""
ByteFlow FastAPI 主应用程序

功能：
1. 提供RESTful API接口
2. WebSocket实时通信支持
3. 集成Baidu搜索API
4. 集成Agents报告生成系统
5. 可视化报告生成进度展示
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import traceback

# 尝试导入dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("⚠️ python-dotenv未安装，将无法自动加载.env文件")

# FastAPI相关导入
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import Optional

# 添加ReportRequest模型定义
class ReportRequest(BaseModel):
    topic: str
    word_limit: int
    report_type: str
    use_baidu_api: bool = False
    use_bailian: bool = False
    model_provider: str = "ollama"
    baidu_api_key: Optional[str] = None
    client_id: Optional[str] = None

# 添加项目路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "agents"))

# 加载环境变量
if DOTENV_AVAILABLE:
    dotenv_path = current_dir / "agents" / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        print("✅ 已加载.env文件:", dotenv_path)
    else:
        print("⚠️ .env文件不存在:", dotenv_path)
else:
    print("⚠️ 无法加载.env文件，python-dotenv未安装")

# 导入项目模块
try:
    from agents.agent_factory import AgentFactory
    BAIDU_API_AVAILABLE = True
    print("✅ 百度搜索API模块可用")
    
    print("✅ 成功导入所有项目模块")
except ImportError as e:
    print(f"❌ 导入项目模块失败: {e}")
    sys.exit(1)

# 导入新的工作流模块
try:
    from workflow import generate_report_with_progress, ProgressCallback
    WORKFLOW_MODULE_AVAILABLE = True
    print("✅ 统一工作流模块导入成功")
except ImportError:
    WORKFLOW_MODULE_AVAILABLE = False
    print("⚠️ 统一工作流模块未找到，将使用旧版模块")

# 创建全局AgentFactory实例
agent_factory = AgentFactory()

# 创建FastAPI应用
app = FastAPI(
    title="ByteFlow 智能报告生成系统",
    description="基于AI的智能报告生成平台，支持实时进度展示",
    version="1.0.0"
)

# 添加异常处理器来捕获验证错误
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"❌ 请求验证错误: {exc}")
    print(f"   请求URL: {request.url}")
    print(f"   请求方法: {request.method}")
    # 尝试获取请求体
    try:
        body = await request.body()
        print(f"   请求体: {body.decode()}")
    except:
        print("   无法读取请求体")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="app"), name="static")

# 添加CSS和JS文件的直接路由（解决404问题）
@app.get("/styles.css")
async def get_styles():
    return FileResponse("app/styles.css", media_type="text/css")

@app.get("/script.js")
async def get_script():
    return FileResponse("app/script.js", media_type="application/javascript")

# 添加工作区专用资源路由
@app.get("/workspace.css")
async def get_workspace_styles():
    return FileResponse("app/workspace.css", media_type="text/css")

@app.get("/workspace.js")
async def get_workspace_script():
    return FileResponse("app/workspace.js", media_type="application/javascript")

# 全局变量
active_connections: Dict[str, WebSocket] = {}
task_status: Dict[str, Dict] = {}
cancel_tokens: Dict[str, bool] = {}  # 用于任务取消的标记

# 在文件顶部添加这个全局变量
client_task_map: Dict[str, str] = {}  # 映射client_id到task_id

# 添加一个全局变量来存储客户端ID和WebSocket的映射
client_websockets: Dict[str, WebSocket] = {}

# 添加一个全局变量来存储客户端连接时间，用于清理过期连接
client_connection_times: Dict[str, datetime] = {}

# 添加一个全局变量来存储客户端最后活动时间
client_last_activity: Dict[str, datetime] = {}

# 添加一个全局变量来存储客户端连接的详细信息，用于调试
client_debug_info: Dict[str, Dict] = {}

# 添加一个全局变量来存储所有已知的客户端ID
known_client_ids: Set[str] = set()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        # 同时更新全局映射
        client_websockets[client_id] = websocket
        # 记录连接时间
        client_connection_times[client_id] = datetime.now()
        # 记录最后活动时间
        client_last_activity[client_id] = datetime.now()
        # 记录调试信息
        client_debug_info[client_id] = {
            "connected_at": datetime.now(),
            "user_agent": "unknown",  # 可以从请求头获取
            "ip_address": "unknown"   # 可以从websocket获取
        }
        # 添加到已知客户端ID集合
        known_client_ids.add(client_id)
        print(f"🔗 客户端 {client_id} 已连接")
        print(f"   当前活跃连接: {list(self.active_connections.keys())}")
        print(f"   已知客户端ID: {list(known_client_ids)}")

    def disconnect(self, client_id: str, reason: str = "unknown"):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"🔌 客户端 {client_id} 已断开连接 (原因: {reason})")
        # 同时从全局映射中移除
        if client_id in client_websockets:
            del client_websockets[client_id]
        # 从时间记录中移除
        if client_id in client_connection_times:
            del client_connection_times[client_id]
        if client_id in client_last_activity:
            del client_last_activity[client_id]
        # 从调试信息中移除
        if client_id in client_debug_info:
            del client_debug_info[client_id]
        # 从任务映射中移除
        if client_id in client_task_map:
            del client_task_map[client_id]

    async def send_personal_message(self, message: dict, client_id: str):
        # 更新客户端最后活动时间
        if client_id in client_last_activity:
            client_last_activity[client_id] = datetime.now()
        
        # 首先检查WebSocket是否仍然在活跃连接中
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message, ensure_ascii=False))
                return True
            except Exception as e:
                print(f"❌ 发送消息到客户端 {client_id} 失败: {e}")
                self.disconnect(client_id, f"send_error: {e}")
                return False
        # 如果不在活跃连接中，尝试使用全局映射
        elif client_id in client_websockets:
            try:
                await client_websockets[client_id].send_text(json.dumps(message, ensure_ascii=False))
                # 更新最后活动时间
                if client_id in client_last_activity:
                    client_last_activity[client_id] = datetime.now()
                return True
            except Exception as e:
                print(f"❌ 发送消息到客户端 {client_id} 失败: {e}")
                if client_id in client_websockets:
                    del client_websockets[client_id]
                if client_id in client_last_activity:
                    del client_last_activity[client_id]
                return False
        else:
            print(f"⚠️ 客户端 {client_id} 不在活跃连接中，无法发送消息")
            return False

    async def broadcast(self, message: dict):
        disconnected_clients = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_text(json.dumps(message, ensure_ascii=False))
                # 更新最后活动时间
                if client_id in client_last_activity:
                    client_last_activity[client_id] = datetime.now()
            except Exception as e:
                print(f"❌ 广播消息到客户端 {client_id} 失败: {e}")
                disconnected_clients.append(client_id)
        
        for client_id in disconnected_clients:
            self.disconnect(client_id, f"broadcast_error: {e}")

    async def ping_clients(self):
        """向所有客户端发送ping消息以保持连接活跃"""
        disconnected_clients = []
        # 创建字典副本以避免在遍历时修改字典
        active_connections_copy = dict(self.active_connections)
        for client_id, connection in active_connections_copy.items():
            try:
                await connection.send_text(json.dumps({"type": "ping"}, ensure_ascii=False))
            except Exception as e:
                print(f"❌ 向客户端 {client_id} 发送ping失败: {e}")
                disconnected_clients.append(client_id)
        
        for client_id in disconnected_clients:
            self.disconnect(client_id, f"ping_error: {e}")

    def get_connection_info(self) -> Dict[str, Any]:
        """获取所有连接的信息"""
        now = datetime.now()
        connections_info = {}
        for client_id in self.active_connections.keys():
            connection_time = client_connection_times.get(client_id, now)
            last_activity = client_last_activity.get(client_id, now)
            debug_info = client_debug_info.get(client_id, {})
            connections_info[client_id] = {
                "connected_at": connection_time.isoformat(),
                "last_activity": last_activity.isoformat(),
                "connected_duration": str(now - connection_time),
                "inactive_duration": str(now - last_activity),
                "debug_info": debug_info
            }
        return connections_info

manager = ConnectionManager()

# 工具函数
async def send_progress_update(client_id: str, task_id: str, status: str, progress: int, message: str, current_step: str = ""):
    """发送进度更新消息"""
    update = {
        "type": "progress_update",
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "message": message,
        "current_step": current_step,
        "timestamp": datetime.now().isoformat()
    }
    
    # 更新任务状态
    task_status[task_id] = update
    
    # 检查客户端是否在活跃连接中
    is_client_active = client_id in active_connections or client_id in client_websockets
    if is_client_active:
        # 发送WebSocket消息
        await manager.send_personal_message(update, client_id)
    else:
        print(f"⚠️ 客户端 {client_id} 不在活跃连接中，进度更新消息将仅存储在任务状态中")

async def send_error_message(client_id: str, task_id: str, error_message: str):
    """发送错误消息"""
    error_update = {
        "type": "error",
        "task_id": task_id,
        "status": "error",
        "progress": 0,
        "message": f"❌ 错误: {error_message}",
        "error": error_message,
        "timestamp": datetime.now().isoformat()
    }
    
    task_status[task_id] = error_update
    
    # 检查客户端是否在活跃连接中
    is_client_active = client_id in active_connections or client_id in client_websockets
    if is_client_active:
        await manager.send_personal_message(error_update, client_id)
    else:
        print(f"⚠️ 客户端 {client_id} 不在活跃连接中，错误消息将仅存储在任务状态中")

async def send_completion_message(client_id: str, task_id: str, result: Dict):
    """发送完成消息"""
    completion_update = {
        "type": "completion",
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "✅ 报告生成完成！",
        "result": result,
        "timestamp": datetime.now().isoformat()
    }
    
    task_status[task_id] = completion_update
    # 确保client_id在活跃连接中，如果不在则尝试其他方式通知
    is_client_active = client_id in active_connections or client_id in client_websockets
    print(f"✅ 任务 {task_id} 完成，客户端 {client_id} 状态: {'活跃' if is_client_active else '不活跃'}")
    
    if is_client_active:
        success = await manager.send_personal_message(completion_update, client_id)
        if success:
            print(f"📤 任务完成消息已发送到客户端 {client_id}")
        else:
            print(f"❌ 无法发送任务完成消息到客户端 {client_id}")
    else:
        print(f"⚠️ 客户端 {client_id} 不在活跃连接中，任务完成消息将存储在任务状态中")

async def check_task_cancelled(task_id: str) -> bool:
    """检查任务是否被取消"""
    return cancel_tokens.get(task_id, False)

async def send_cancel_message(client_id: str, task_id: str):
    """发送任务取消消息"""
    cancel_update = {
        "type": "cancelled",
        "task_id": task_id,
        "status": "cancelled",
        "progress": 0,
        "message": "⏹️ 任务已被用户取消",
        "timestamp": datetime.now().isoformat()
    }
    
    task_status[task_id] = cancel_update
    
    # 检查客户端是否在活跃连接中
    is_client_active = client_id in active_connections or client_id in client_websockets
    if is_client_active:
        await manager.send_personal_message(cancel_update, client_id)
    else:
        print(f"⚠️ 客户端 {client_id} 不在活跃连接中，取消消息将仅存储在任务状态中")

# API路由
@app.get("/")
async def root():
    """返回主页"""
    return FileResponse("app/index.html")

@app.get("/workspace")
async def workspace():
    """返回工作页面"""
    return FileResponse("app/workspace.html")

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/config")
async def get_config():
    """获取系统配置信息"""
    import os
    from dotenv import load_dotenv
    
    # 加载环境变量
    dotenv_path = os.path.join(current_dir, "agents", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    
    return {
        "baidu_api_key": os.getenv("BAIDU_API_KEY", ""),
        "mcp_api_key": os.getenv("ZHIPU_API_KEY", ""),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", ""),
        "ollama_default_model": os.getenv("OLLAMA_DEFAULT_MODEL", ""),
        "qwen_base_url": os.getenv("QWEN_BASE_URL", ""),
        "qwen_default_model": os.getenv("QWEN_DEFAULT_MODEL", ""),
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY", "")
    }

@app.get("/api/tasks")
async def get_all_tasks():
    """获取所有任务状态"""
    return {
        "tasks": list(task_status.values()),
        "total": len(task_status)
    }

@app.get("/api/connections")
async def get_connections():
    """获取所有活跃连接信息"""
    return {
        "connections": manager.get_connection_info(),
        "total": len(manager.active_connections),
        "debug_info": client_debug_info
    }

@app.get("/api/connection-debug/{client_id}")
async def get_connection_debug(client_id: str):
    """获取特定客户端的调试信息"""
    if client_id in client_debug_info:
        return {
            "client_id": client_id,
            "debug_info": client_debug_info[client_id],
            "is_active": client_id in active_connections or client_id in client_websockets,
            "connection_time": client_connection_times.get(client_id),
            "last_activity": client_last_activity.get(client_id)
        }
    else:
        raise HTTPException(status_code=404, detail="客户端不存在")

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """获取指定任务状态"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task_status[task_id]

@app.post("/api/cancel-task/{task_id}")
async def cancel_task(task_id: str):
    """取消指定任务"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 设置取消标记
    cancel_tokens[task_id] = True
    
    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "任务取消请求已发送"
    }

@app.post("/api/test-baidu")
async def test_baidu_api(request: dict):
    """测试百度API连接"""
    try:
        api_key = request.get('api_key', '')
        query = request.get('query', '')
        
        if not api_key.strip():
            return {"success": False, "error": "API密钥不能为空"}
        
        if not query.strip():
            return {"success": False, "error": "查询内容不能为空"}
        
        # 构建测试请求
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": f"查询: {query}"
                }
            ],
            "search_source": "baidu_search_v2",
            "model": "ernie-4.5-turbo-128k",
            "temperature": 0.1,
            "max_completion_tokens": 100,
            "search_mode": "required"
        }
        
        # 调用百度API
        response_json = await safe_call_baidu_api(payload, headers, max_retries=1)
        
        if response_json:
            return {
                "success": True, 
                "message": "API连接成功",
                "result_count": 1,
                "response_data": response_json  # 返回完整的API响应数据
            }
        else:
            return {
                "success": False, 
                "error": "API调用失败，请检查密钥是否正确"
            }
            
    except Exception as e:
        return {
            "success": False, 
            "error": f"测试失败: {str(e)}"
        }

@app.post("/api/test-mcp")
async def test_mcp_api(request: dict):
    """测试智谱MCP API连接"""
    try:
        api_key = request.get('api_key', '')
        query = request.get('query', '')
        max_results = request.get('max_results', 10)
        
        if not api_key.strip():
            return {"success": False, "error": "ZHIPU_API_KEY不能为空"}
        
        if not query.strip():
            return {"success": False, "error": "搜索查询不能为空"}
        
        # 调用智谱MCP API
        result = await call_zhipu_mcp_api(api_key, query, max_results)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"智谱MCP API连接成功，获取到 {len(result['data'].get('search_results', []))} 条搜索结果",
                "result_count": len(result['data'].get('search_results', [])),
                "response_data": result['data'],
                "raw_response": result.get('raw_response', '')
            }
        else:
            return {
                "success": False,
                "error": result['error']
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"智谱MCP测试失败: {str(e)}"
        }

@app.post("/api/generate-report")
async def create_report_task(request: ReportRequest, background_tasks: BackgroundTasks):
    """创建报告生成任务"""
    try:
        task_id = str(uuid.uuid4())
        
        # 添加调试信息
        print(f"📥 接收到报告生成请求: {request.topic}")
        print(f"   客户端ID: {request.client_id}")
        print(f"   任务ID: {task_id}")
        
        # 初始化任务状态
        initial_status = {
            "type": "task_created",
            "task_id": task_id,
            "status": "created",
            "progress": 0,
            "message": f"📝 已创建报告生成任务: {request.topic}",
            "current_step": "初始化",
            "timestamp": datetime.now().isoformat(),
            "topic": request.topic,
            "word_limit": request.word_limit,
            "report_type": request.report_type
        }
        
        task_status[task_id] = initial_status
        
        # 添加后台任务
        background_tasks.add_task(generate_report_background, task_id, request)
        
        return {
            "task_id": task_id,
            "status": "created",
            "message": "报告生成任务已创建，请通过WebSocket连接获取实时进度"
        }
    except Exception as e:
        print(f"❌ 创建报告任务时出错: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def generate_report_background(task_id: str, request: ReportRequest):
    """后台报告生成任务"""
    # 使用前端传递的client_id
    client_id = request.client_id
    
    # 如果没有提供client_id，则记录警告并使用task_id作为备用
    if not client_id:
        print(f"⚠️ 警告: 未提供客户端ID，将使用任务ID {task_id} 作为备用客户端ID")
        client_id = task_id
    
    # 添加调试信息
    print(f"🔍 接收到的客户端ID: {client_id}")
    print(f"🔍 活跃连接: {list(active_connections.keys())}")
    print(f"🔍 客户端WebSocket映射: {list(client_websockets.keys())}")
    print(f"🔍 已知客户端ID: {list(known_client_ids)}")
    
    # 映射client_id到task_id
    client_task_map[client_id] = task_id
    print(f"📊 客户端任务映射已更新: {client_id} -> {task_id}")
    
    # 检查客户端是否在活跃连接中
    is_client_active = client_id in active_connections or client_id in client_websockets
    print(f"📋 任务 {task_id} 开始执行，客户端 {client_id} 状态: {'活跃' if is_client_active else '不活跃'}")
    
    # 确保client_id在活跃连接中
    if not is_client_active:
        print(f"⚠️ 客户端 {client_id} 不在活跃连接中，将仅存储任务状态而不发送WebSocket消息")
        # 如果客户端不活跃，我们将只存储任务状态而不发送WebSocket消息
        # 不再尝试使用task_id作为备用客户端ID，因为task_id不是一个有效的WebSocket客户端ID
    
    try:
        # 检查任务是否已被取消
        if await check_task_cancelled(task_id):
            await send_cancel_message(client_id, task_id)
            return
        
        # 步骤1: 数据收集
        if request.use_baidu_api and request.baidu_api_key:
            await send_progress_update(
                client_id, task_id, "running", 10, 
                "🔍 正在使用百度API收集实时数据...", "数据收集"
            )
            # 使用百度API
            data = await collect_data_with_baidu_api(request.topic, request.baidu_api_key)
        elif request.use_bailian:
            await send_progress_update(
                client_id, task_id, "running", 10, 
                "🔍 正在使用智谱MCP收集实时数据...", "数据收集"
            )
            # 使用智谱MCP API
            # 优先使用请求中提供的API密钥，如果没有则使用环境变量
            zhipu_api_key = request.baidu_api_key if request.baidu_api_key else os.getenv("ZHIPU_API_KEY", "")
            if zhipu_api_key:
                mcp_result = await call_zhipu_mcp_api(zhipu_api_key, request.topic, 10)
                if mcp_result["success"]:
                    data = await generate_mock_data_with_mcp(request.topic, mcp_result["data"])
                else:
                    await send_progress_update(
                        client_id, task_id, "running", 10, 
                        "⚠️ MCP数据收集失败，使用模拟数据...", "数据收集"
                    )
                    data = await generate_mock_data(request.topic)
            else:
                await send_progress_update(
                    client_id, task_id, "running", 10, 
                    "⚠️ 未配置MCP API密钥，使用模拟数据...", "数据收集"
                )
                data = await generate_mock_data(request.topic)
        else:
            await send_progress_update(
                client_id, task_id, "running", 10, 
                "🤖 正在使用Ollama本地模型收集相关数据...", "数据收集"
            )
            # 使用Ollama生成数据
            data = await collect_data_from_baidu(request.topic)
        
        # 检查任务是否已被取消
        if await check_task_cancelled(task_id):
            await send_cancel_message(client_id, task_id)
            return
        
        # 步骤2: 初始化智能体
        model_name = "Ollama" if request.model_provider == "ollama" else "通义千问"
        await send_progress_update(
            client_id, task_id, "running", 20,
            f"🤖 正在初始化{model_name} AI智能体系统...", "智能体初始化"
        )
        
        # 检查任务是否已被取消
        if await check_task_cancelled(task_id):
            await send_cancel_message(client_id, task_id)
            return
        
        # 步骤3: 生成报告
        await send_progress_update(
            client_id, task_id, "running", 30,
            f"📝 开始{model_name} AI协作撰写报告...", "报告生成"
        )
        
        # 构建任务数据，包含配置信息
        task_data = {
            "id": task_id,
            "question": request.topic,
            "type": request.report_type,
            "word_limit": request.word_limit,
            "data": data,
            "config": {
                "use_baidu_api": request.use_baidu_api,
                "use_bailian": request.use_bailian,
                "model_provider": request.model_provider
            }
        }
        
        # 调用报告生成函数，传递任务取消检查器
        if WORKFLOW_MODULE_AVAILABLE:
            # 使用新的统一工作流模块
            # 修复函数调用参数，将check_task_cancelled作为关键字参数传递
            result = await generate_report_with_progress(
                task_data, 
                client_id=client_id, 
                task_id=task_id, 
                cancel_checker=check_task_cancelled
            )
        else:
            # 使用旧版模块
            result = await generate_report_with_progress_old(
                task_data, 
                client_id=client_id, 
                task_id=task_id
            )
        
        # 检查任务是否已被取消
        if await check_task_cancelled(task_id):
            await send_cancel_message(client_id, task_id)
            return
        
        # 发送完成消息
        await send_completion_message(client_id, task_id, result)
        
    except asyncio.CancelledError:
        # 任务被取消，发送取消消息
        await send_cancel_message(client_id, task_id)
    except Exception as e:
        print(f"❌ 报告生成任务 {task_id} 失败: {e}")
        traceback.print_exc()
        await send_error_message(client_id, task_id, str(e))

async def collect_data_with_baidu_api(topic: str, api_key: str) -> Dict:
    """使用用户提供的百度API密钥收集数据"""
    try:
        print(f"🔍 使用百度API收集数据: {topic}")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": f"For the exact topic '{topic}', retrieve authoritative data from credible sources accessible within mainland China covering 2022-2024. Return strictly formatted JSON with: background (3 key facts with concise explanations + verified sources), statistics (3-5 metrics with precise values/timeframes/sources), case_studies (2-3 real-world examples with location/implementation details/outcomes), expert_opinions (2 contrasting viewpoints with expert credentials), and challenges (3 current limitations/barriers). Return only JSON—no additional text, explanations, or markdown."
                }
            ],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [
                {"type": "image", "top_k": 4},
                {"type": "video", "top_k": 4},
                {"type": "web", "top_k": 4}
            ],
            "search_recency_filter": "year",
            "model": "ernie-4.5-turbo-128k",
            "temperature": 1e-10,
            "top_p": 1e-10,
            "search_mode": "required",
            "enable_reasoning": True,
            "enable_deep_search": False,
            "max_completion_tokens": 10000,
            "response_format": "auto",
            "enable_corner_markers": True,
            "enable_followup_queries": False,
            "stream": False,
            "safety_level": "standard",
            "max_search_query_num": 10
        }
        
        response_json = await safe_call_baidu_api(payload, headers)
        
        if response_json:
            content = response_json['choices'][0]['message']['content']
            try:
                # 尝试提取JSON
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    extracted_data = json.loads(json_match.group(1))
                else:
                    # 如果没有代码包装，直接解析
                    extracted_data = json.loads(content)
                
                print(f"✅ 成功从百度API获取数据")
                return extracted_data
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON解析失败：{e}，使用模拟数据")
                return await generate_mock_data(topic)
        else:
            print(f"❌ 百度API调用失败，使用模拟数据")
            return await generate_mock_data(topic)
            
    except Exception as e:
        print(f"❌ 百度数据收集失败: {e}")
        return await generate_mock_data(topic)

async def collect_data_from_baidu(topic: str) -> Dict:
    """使用Ollama本地模型生成数据，替代百度API"""
    try:
        print(f"🤖 使用Ollama本地模型生成数据: {topic}")
        
        # 使用全局Agent工厂实例
        from agents.agent_factory import AgentFactory
        
        # 创建数据收集Agent（使用Ollama）
        data_collector = agent_factory.create_role_agent(
            'ollama', 
            'simple_chat'  # 使用简单聊天角色
        )
        
        # 构建数据收集提示
        data_prompt = f"""请为以下主题生成研究数据："{topic}"

请返回JSON格式的数据，包含：
1. background: 3个背景事实和来源
2. statistics: 3-5个相关统计数据
3. case_studies: 2-3个实际案例
4. expert_opinions: 2个专家观点
5. challenges: 3个主要挑战

请直接返回JSON格式，不要包含任何解释性文字。"""
        
        # 创建Agent请求对象
        from agents.base_agent import AgentRequest
        request = AgentRequest(prompt=data_prompt)
        
        # 调用模型生成数据
        response = await asyncio.to_thread(data_collector.generate, request)
        
        # 解析JSON响应
        try:
            if response and hasattr(response, 'content'):
                # 如果response是一个对象，获取content属性
                content = response.content
                # 尝试提取JSON
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    print(f"✅ 成功使Ollama生成数据")
                    return data
                else:
                    print(f"⚠️ Ollama响应中未找到JSON，使用模拟数据")
                    return await generate_mock_data(topic)
            elif response and isinstance(response, str):
                # 如果response是字符串
                # 尝试提取JSON
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    print(f"✅ 成功使Ollama生成数据")
                    return data
                else:
                    print(f"⚠️ Ollama响应中未找到JSON，使用模拟数据")
                    return await generate_mock_data(topic)
            else:
                print(f"⚠️ Ollama响应为空，使用模拟数据")
                return await generate_mock_data(topic)
                
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON解析失败：{e}，使用模拟数据")
            return await generate_mock_data(topic)
            
    except Exception as e:
        print(f"❌ Ollama数据收集失败: {e}")
        print(f"🔄 使用模拟数据代替")
        return await generate_mock_data(topic)

async def safe_call_baidu_api(payload: dict, headers: dict, max_retries: int = 2) -> Optional[dict]:
    """安全的百度API调用函数，解决编码问题"""
    import requests
    
    # API URL
    api_url = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"
    
    for attempt in range(max_retries):
        try:
            print(f"🔁 正在尝试第 {attempt + 1} 次请求...")
            
            # 确保正确的JSON编码
            json_data = json.dumps(payload, ensure_ascii=False)
            
            # 确保headers包含正确的编码
            request_headers = headers.copy()
            request_headers['Content-Type'] = 'application/json; charset=utf-8'
            
            # 使用data参数而不是json参数，并指定UTF-8编码
            response = requests.post(
                api_url,
                headers=request_headers,
                data=json_data.encode('utf-8'),
                timeout=120
            )
            
            print(f"📊 API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                resp_json = response.json()
                if "choices" in resp_json and len(resp_json["choices"]) > 0:
                    return resp_json
                else:
                    raise ValueError("API 响应中缺少 'choices' 字段")
            else:
                print(f"❌ API 返回错误状态码: {response.status_code}")
                if response.text:
                    print(f"   响应内容: {response.text[:200]}...")
                raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            print(f"⚠️ 请求失败: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 2秒、4秒递增
                print(f"⏳ {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                print("🛑 已达到最大重试次数")
    
    return None

async def call_zhipu_mcp_api(api_key: str, query: str, max_results: int = 10) -> Dict:
    """调用智谱MCP API进行搜索"""
    try:
        # 检查是否安装了zai-sdk
        try:
            from zai import ZhipuAiClient
        except ImportError:
            error_msg = "未安装zai-sdk，请运行: pip install zai-sdk"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        
        # 创建智谱AI客户端
        client = ZhipuAiClient(api_key=api_key)
        
        # 定义工具参数
        tools = [{
            "type": "web_search",
            "web_search": {
                "enable": True,
                "search_engine": "search_pro",
                "search_result": True,
                "search_prompt": f"你是一位专业分析师。请用简洁的语言总结网络搜索结果中的关键信息，按重要性排序并引用来源日期。今天的日期是{datetime.now().strftime('%Y年%m月%d日')}。",
                "count": max_results,
                "search_recency_filter": "noLimit",
                "content_size": "high"
            }
        }]
        
        # 定义用户消息
        messages = [{
            "role": "user",
            "content": query
        }]
        
        print(f"🔍 正在调用智谱MCP API: {query}")
        
        # 调用API获取响应
        response = client.chat.completions.create(
            model="glm-4-air",
            messages=messages,
            tools=tools
        )
        
        print(f"✅ 智谱MCP API调用成功")
        
        # 解析响应数据
        search_results = []
        
        # 检查响应中是否包含工具调用结果
        if hasattr(response, 'choices') and len(response.choices) > 0:
            choice = response.choices[0]
            
            # 检查是否有工具调用
            if hasattr(choice, 'tool_calls') and choice.tool_calls:
                for tool_call in choice.tool_calls:
                    if tool_call.type == "web_search" and hasattr(tool_call, 'web_search'):
                        search_data = tool_call.web_search
                        if hasattr(search_data, 'search_results') and search_data.search_results:
                            search_results.extend(search_data.search_results)
            
            # 如果没有工具调用结果，尝试从消息内容中提取
            elif hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                # 这里可以添加从内容中提取链接和信息的逻辑
                # 为简化起见，我们创建一个包含响应内容的结果
                search_results.append({
                    "title": "智谱AI分析结果",
                    "url": "#",
                    "snippet": str(choice.message.content),
                    "source": "智谱AI"
                })
        
        return {
            "success": True,
            "data": {
                "search_results": search_results,
                "query": query,
                "total_results": len(search_results),
                "timestamp": time.time()
            }
        }
        
    except Exception as e:
        error_msg = f"智谱MCP API调用失败: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": error_msg
        }

async def generate_mock_data(topic: str) -> Dict:
    """生成模拟数据结构"""
    await asyncio.sleep(1)  # 模拟网络延迟
    
    return {
        "background": [
            {"fact": f"关于 {topic} 的背景信息1：近年来该领域发展迅速，在政策支持下得到广泛关注。", "source": "相关行业报告"},
            {"fact": f"关于 {topic} 的背景信息2：国内外企业都在积极布局，技术成熟度不断提升。", "source": "专业机构研究"},
            {"fact": f"关于 {topic} 的背景信息3：市场需求旺盛，但仍面临一些技术和法规挑战。", "source": "市场调研数据"}
        ],
        "statistics": [
            {"metric": f"{topic} 相关市场规模", "value": "约850亿元人民币", "source": "行业统计数据"},
            {"metric": f"{topic} 技术采用率", "value": "78.5%", "source": "专业调研"},
            {"metric": f"{topic} 年增长率", "value": "23.7%", "source": "国家统计局"},
            {"metric": f"{topic} 相关企业数量", "value": "超过1.2万家", "source": "工商注册数据"},
            {"metric": f"{topic} 投资规模", "value": "320亿元", "source": "投资机构统计"}
        ],
        "case_studies": [
            {"location": "北京中关村", "implementation": f"{topic} 技术在科技园区的应用实践", "outcome": "效果显著，提升效率超过40%", "source": "实地调研"},
            {"location": "上海张江", "implementation": f"{topic} 在金融中心的创新应用", "outcome": "成功降低成本25%，提升服务质量", "source": "企业案例研究"},
            {"location": "深圳南山", "implementation": f"{topic} 在高新技术产业的应用", "outcome": "带动产业升级，获得国际认可", "source": "政府报告"}
        ],
        "expert_opinions": [
            {"expert": "李明教授", "credentials": "中科院研究员，相关领域专家", "viewpoint": f"对 {topic} 的发展前景非常乐观，认为技术已经趋于成熟。", "source": "专家采访"},
            {"expert": "王红博士", "credentials": "清华大学教授，行业资深专家", "viewpoint": f"对 {topic} 持谨慎态度，认为还需要解决一些核心技术难题。", "source": "学术会议"}
        ],
        "challenges": [
            {"limitation": f"{topic} 面临的挑战1：技术标准化不统一，需要行业协调。", "source": "行业分析"},
            {"limitation": f"{topic} 面临的挑战2：人才缺口严重，需要加强教育培训。", "source": "人力资源调研"},
            {"limitation": f"{topic} 面临的挑战3：法规政策仍在完善中，需要更多政策支持。", "source": "政策研究报告"}
        ]
    }

async def generate_mock_data_with_mcp(topic: str, mcp_data: Dict) -> Dict:
    """基于MCP数据生成模拟数据结构"""
    await asyncio.sleep(1)  # 模拟网络延迟
    
    # 从MCP数据中提取相关信息
    search_results = mcp_data.get("search_results", [])
    
    # 构建背景信息
    background = []
    statistics = []
    case_studies = []
    expert_opinions = []
    challenges = []
    
    # 从MCP搜索结果中提取信息
    for i, result in enumerate(search_results[:3]):  # 只取前3个结果
        background.append({
            "fact": f"关于 {topic} 的背景信息{i+1}：{result.get('title', '相关研究')} - {result.get('snippet', '相关内容')[:100]}...", 
            "source": result.get("source", "网络搜索结果")
        })
    
    # 添加统计信息
    statistics.append({
        "metric": f"{topic} 相关搜索结果数量", 
        "value": f"{len(search_results)}条", 
        "source": "智谱MCP搜索"
    })
    
    # 添加案例研究
    for i, result in enumerate(search_results[:2]):
        case_studies.append({
            "location": result.get("source", "网络来源"), 
            "implementation": f"{topic} 相关研究: {result.get('title', '相关内容')}", 
            "outcome": result.get('snippet', '相关内容')[:100] + "...", 
            "source": result.get("source", "智谱MCP")
        })
    
    # 添加专家观点和挑战
    expert_opinions.append({
        "expert": "智谱AI分析", 
        "credentials": "基于MCP搜索结果的智能分析", 
        "viewpoint": f"对 {topic} 的分析显示该主题在网络上具有较高的关注度和讨论热度。", 
        "source": "智谱MCP智能分析"
    })
    
    challenges.append({
        "limitation": f"{topic} 面临的挑战：信息来源多样化，需要进一步筛选和验证。", 
        "source": "智谱MCP分析"
    })
    
    return {
        "background": background or [
            {"fact": f"关于 {topic} 的背景信息1：通过智谱MCP搜索获取到相关数据。", "source": "智谱MCP"}
        ],
        "statistics": statistics or [
            {"metric": f"{topic} 相关信息统计", "value": "通过MCP获取", "source": "智谱MCP"}
        ],
        "case_studies": case_studies or [
            {"location": "网络来源", "implementation": f"{topic} 研究案例", "outcome": "通过MCP获取相关信息", "source": "智谱MCP"}
        ],
        "expert_opinions": expert_opinions or [
            {"expert": "AI分析师", "credentials": "基于MCP数据的智能分析", "viewpoint": f"对 {topic} 进行了初步分析。", "source": "智谱MCP"}
        ],
        "challenges": challenges or [
            {"limitation": f"{topic} 数据处理挑战：需要进一步验证和分析获取的数据。", "source": "智谱MCP分析"}
        ]
    }

async def generate_report_with_progress(task_data: Dict, client_id: str = None, task_id: str = None, cancel_checker=None) -> Dict:
    """
    带进度显示的完整报告生成工作流（生成+评价+改进）
    
    Args:
        task_data: 任务数据
        client_id: 客户端ID，用于WebSocket通信
        task_id: 任务ID
        cancel_checker: 任务取消检查器函数
        
    Returns:
        最终报告数据
    """
    try:
        # 创建进度回调对象并设置WebSocket管理器
        from workflow import ProgressCallback, generate_single_report, evaluate_and_improve_report
        progress_callback = ProgressCallback(client_id, task_id)
        progress_callback.set_ws_manager(manager)  # 设置WebSocket管理器
        
        # 设置任务取消检查器
        if cancel_checker:
            progress_callback.set_task_cancel_checker(cancel_checker)
        
        # 1. 生成报告
        print("🚀 开始生成报告...")
        initial_report = await generate_single_report(task_data, progress_callback)
        
        # 2. 评价并改进报告
        print("🔍 开始评价和改进报告...")
        final_report = await evaluate_and_improve_report(initial_report, progress_callback)
        
        return final_report
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {str(e)}")
        # 即使工作流失败，也要确保发送错误消息到客户端
        if client_id and task_id:
            try:
                await send_error_message(client_id, task_id, str(e))
            except:
                pass
        raise

async def generate_report_with_progress_old(task_data: Dict, client_id: str = None, task_id: str = None) -> Dict:
    """
    旧版带进度显示的完整报告生成工作流（生成+评价+改进）
    
    Args:
        task_data: 任务数据
        client_id: 客户端ID，用于WebSocket通信
        task_id: 任务ID
        
    Returns:
        最终报告数据
    """
    try:
        # 直接使用workflow.py中定义的函数
        from workflow import generate_single_report
        # 创建一个简单的进度回调对象
        class SimpleProgressCallback:
            async def on_agent_start(self, agent_name: str, role_name: str, step_name: str):
                pass
            async def on_agent_retry(self, agent_name: str, role_name: str, step_name: str, attempt: int, max_retries: int):
                pass
            async def on_agent_success(self, agent_name: str, role_name: str, step_name: str, content: str, word_count: int):
                pass
            async def on_agent_error(self, agent_name: str, role_name: str, step_name: str, error: str):
                pass
            async def on_report_section_complete(self, section_name: str, word_count: int):
                pass
            async def on_evaluation_start(self, report_id: str):
                pass
            async def on_improvement_start(self, report_id: str, attempt: int, max_attempts: int):
                pass
            async def on_improvement_success(self, report_id: str, word_count: int, target_word_limit: int):
                pass
        
        progress_callback = SimpleProgressCallback()
        result = await generate_single_report(task_data, progress_callback)
        return result
    except Exception as e:
        print(f"❌ 旧版工作流执行失败: {str(e)}")
        raise

# WebSocket端点
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    # 获取客户端IP地址
    client_ip = websocket.client.host if websocket.client else "unknown"
    print(f"🔗 新的WebSocket连接请求: {client_id} (IP: {client_ip})")
    
    await manager.connect(websocket, client_id)
    # 注意：ConnectionManager.connect已经将WebSocket添加到active_connections中
    # 更新调试信息
    if client_id in client_debug_info:
        client_debug_info[client_id]["ip_address"] = client_ip
    
    try:
        while True:
            # 保持连接活跃
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 更新客户端最后活动时间
            if client_id in client_last_activity:
                client_last_activity[client_id] = datetime.now()
            
            # 处理客户端消息
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif message.get("type") == "get_status":
                task_id = message.get("task_id")
                if task_id and task_id in task_status:
                    await manager.send_personal_message(task_status[task_id], client_id)
                    
    except WebSocketDisconnect as e:
        manager.disconnect(client_id, f"WebSocketDisconnect: {e.code}")
    except Exception as e:
        print(f"❌ WebSocket错误: {e}")
        manager.disconnect(client_id, f"Exception: {e}")

# 添加一个后台任务来定期清理过期连接
async def cleanup_expired_connections():
    """定期清理过期连接"""
    while True:
        try:
            # 每30秒检查一次
            await asyncio.sleep(30)
            
            # 获取当前时间
            now = datetime.now()
            
            # 清理超过1小时未活动的连接
            expired_clients = []
            for client_id, last_activity in client_last_activity.items():
                if now - last_activity > timedelta(hours=1):
                    expired_clients.append(client_id)
            
            # 从所有相关字典中移除过期连接
            for client_id in expired_clients:
                if client_id in active_connections:
                    del active_connections[client_id]
                if client_id in client_websockets:
                    del client_websockets[client_id]
                if client_id in client_connection_times:
                    del client_connection_times[client_id]
                if client_id in client_last_activity:
                    del client_last_activity[client_id]
                if client_id in client_task_map:
                    del client_task_map[client_id]
                
                print(f"🧹 已清理过期连接: {client_id}")
                
        except Exception as e:
            print(f"❌ 清理过期连接时出错: {e}")

# 在应用启动时启动清理任务
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 启动定期清理过期连接的任务
    asyncio.create_task(cleanup_expired_connections())
    # 启动定期ping客户端的任务
    asyncio.create_task(ping_clients_periodically())
    print("✅ 已启动过期连接清理任务和客户端心跳任务")

async def ping_clients_periodically():
    """定期向所有客户端发送ping消息"""
    while True:
        try:
            # 每25秒发送一次ping
            await asyncio.sleep(25)
            await manager.ping_clients()
        except Exception as e:
            print(f"❌ 发送客户端心跳时出错: {e}")

if __name__ == "__main__":
    print("🚀 启动 ByteFlow 智能报告生成系统...")
    print("=" * 60)
    print("📋 API文档: http://localhost:8000/docs")
    print("📍 WebSocket: ws://localhost:8000/ws/{client_id}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True,
        reload_dirs=[".", "app", "agents"]
    )
