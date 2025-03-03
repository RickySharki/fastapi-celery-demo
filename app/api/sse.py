"""
服务器发送事件(SSE)模块
提供实时任务状态和日志更新
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Set
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from datetime import datetime

# 创建路由
router = APIRouter()

# 活跃的SSE连接集合
active_connections: Set[asyncio.Queue] = set()

# 事件历史记录，用于新连接时发送最近的事件
event_history: List[Dict[str, Any]] = []
MAX_HISTORY_SIZE = 100  # 最大历史记录数量

# 任务状态缓存，用于新连接时发送当前任务状态
task_status_cache: Dict[str, Dict[str, Any]] = {}


async def add_connection() -> asyncio.Queue:
    """
    添加新的SSE连接
    
    Returns:
        asyncio.Queue: 事件队列
    """
    queue = asyncio.Queue()
    active_connections.add(queue)
    
    # 发送历史事件
    for event in event_history:
        await queue.put(event)
    
    # 发送当前任务状态
    for task_id, status in task_status_cache.items():
        await queue.put({
            "event": "task_update",
            "data": json.dumps(status)  # 确保使用json.dumps序列化数据
        })
    
    return queue


async def remove_connection(queue: asyncio.Queue) -> None:
    """
    移除SSE连接
    
    Args:
        queue: 要移除的事件队列
    """
    if queue in active_connections:
        active_connections.remove(queue)


async def send_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    向所有活跃连接发送事件
    
    Args:
        event_type: 事件类型
        data: 事件数据
    """
    # 确保数据是字符串格式
    data_str = json.dumps(data)
    
    event = {
        "event": event_type,
        "data": data_str
    }
    
    # 添加到历史记录
    event_history.append(event)
    if len(event_history) > MAX_HISTORY_SIZE:
        event_history.pop(0)
    
    # 如果是任务状态更新，则更新缓存
    if event_type == "task_update" and "task_id" in data:
        task_status_cache[data["task_id"]] = data
        
        # 如果任务已完成，设置定时器在一段时间后清除缓存
        if data.get("status") in ["SUCCESS", "FAILURE", "REVOKED"]:
            asyncio.create_task(remove_from_cache_after_delay(data["task_id"], 300))
    
    # 发送到所有活跃连接
    for queue in list(active_connections):
        try:
            await queue.put(event)
        except Exception as e:
            print(f"Error sending event to connection: {str(e)}")
            # 如果发送失败，移除连接
            await remove_connection(queue)


async def remove_from_cache_after_delay(task_id: str, delay: int = 3600) -> None:
    """
    在指定延迟后从缓存中移除任务状态
    
    Args:
        task_id: 任务ID
        delay: 延迟时间（秒）
    """
    await asyncio.sleep(delay)
    if task_id in task_status_cache:
        del task_status_cache[task_id]


@router.get("/events")
async def events(request: Request) -> EventSourceResponse:
    """
    SSE事件流端点
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        EventSourceResponse: SSE响应
    """
    queue = await add_connection()
    
    # 发送连接成功消息
    await send_event("system_message", {
        "message": "SSE连接已建立",
        "type": "success",
        "timestamp": datetime.now().isoformat()
    })
    
    async def event_generator():
        try:
            # 发送初始消息
            yield {
                "event": "system_message",
                "data": json.dumps({
                    "message": "开始接收事件流",
                    "type": "info",
                    "timestamp": datetime.now().isoformat()
                })
            }
            
            # 保持连接活跃的心跳
            ping_task = asyncio.create_task(send_ping(queue))
            
            # 等待并发送事件
            while True:
                if await request.is_disconnected():
                    break
                
                # 等待队列中的下一个事件，设置超时以检查连接状态
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event
                except asyncio.TimeoutError:
                    # 超时，继续循环并检查连接状态
                    continue
                except Exception as e:
                    # 其他错误，记录并继续
                    print(f"Error in SSE event stream: {str(e)}")
                    continue
            
            # 取消心跳任务
            ping_task.cancel()
            
        except Exception as e:
            print(f"SSE connection error: {str(e)}")
        finally:
            # 清理连接
            await remove_connection(queue)
    
    return EventSourceResponse(event_generator())


async def send_ping(queue: asyncio.Queue, interval: int = 30) -> None:
    """
    定期发送ping事件以保持连接活跃
    
    Args:
        queue: 事件队列
        interval: 心跳间隔（秒）
    """
    try:
        while True:
            await asyncio.sleep(interval)
            await queue.put({
                "event": "ping",
                "data": json.dumps({
                    "timestamp": datetime.now().isoformat()
                })
            })
    except asyncio.CancelledError:
        # 任务被取消，正常退出
        pass
    except Exception as e:
        print(f"Error in ping task: {str(e)}")


# 辅助函数：发送任务状态更新
async def send_task_update(
    task_id: str, 
    status: str, 
    progress: Optional[float] = None, 
    result: Optional[Dict[str, Any]] = None, 
    error: Optional[str] = None
) -> None:
    """
    发送任务状态更新事件
    
    Args:
        task_id: 任务ID
        status: 任务状态
        progress: 任务进度（0-100）
        result: 任务结果
        error: 错误信息
    """
    data = {
        "task_id": task_id,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    
    if progress is not None:
        data["progress"] = progress
    
    if result is not None:
        data["result"] = result
    
    if error is not None:
        data["error"] = error
    
    await send_event("task_update", data)


# 辅助函数：发送任务日志
async def send_task_log(
    task_id: str, 
    message: str, 
    step: Optional[str] = None, 
    level: str = "info", 
    progress: Optional[float] = None
) -> None:
    """
    发送任务日志事件
    
    Args:
        task_id: 任务ID
        message: 日志消息
        step: 执行步骤
        level: 日志级别（info, warning, error, success）
        progress: 任务进度（0-100）
    """
    data = {
        "task_id": task_id,
        "message": message,
        "level": level,
        "timestamp": datetime.now().isoformat()
    }
    
    if step is not None:
        data["step"] = step
    
    if progress is not None:
        data["progress"] = progress
    
    await send_event("task_log", data)


# 辅助函数：发送系统消息
async def send_system_message(message: str, message_type: str = "info") -> None:
    """
    发送系统消息事件
    
    Args:
        message: 系统消息
        message_type: 消息类型（info, warning, error, success）
    """
    data = {
        "message": message,
        "type": message_type,
        "timestamp": datetime.now().isoformat()
    }
    
    await send_event("system_message", data) 