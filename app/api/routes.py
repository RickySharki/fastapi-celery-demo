"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from uuid import uuid4

from app.core.celery_app import celery_app
from app.tasks.data_collection import collect_data_task
from app.api.sse import send_task_update, send_task_log, send_system_message

# 创建路由
router = APIRouter()

# 请求模型
class TaskRequest(BaseModel):
    """任务请求模型"""
    data_sources: List[Dict[str, Any]]  # 数据源配置列表
    llm_config: Dict[str, Any]  # LLM配置
    dimensions: List[Dict[str, Any]]  # 结果维度配置

# 响应模型
class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    """任务状态响应模型"""
    task_id: str
    status: str
    progress: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# 任务提交接口
@router.post("/tasks", response_model=TaskResponse)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """
    创建新任务
    
    Args:
        task_request: 任务请求数据
        background_tasks: 后台任务
        
    Returns:
        TaskResponse: 任务响应
    """
    # 生成任务ID
    task_id = str(uuid4())
    
    # 记录任务创建
    background_tasks.add_task(
        send_task_log,
        task_id=task_id,
        message=f"任务已创建，数据源数量: {len(task_request.data_sources)}, 维度数量: {len(task_request.dimensions)}",
        step="创建",
        level="info"
    )
    
    # 启动Celery任务
    celery_task = collect_data_task.delay(
        task_id,
        task_request.data_sources,
        task_request.llm_config,
        task_request.dimensions
    )
    
    # 记录任务状态
    background_tasks.add_task(
        send_task_update,
        task_id=task_id,
        status="PENDING",
        progress=0
    )
    
    return TaskResponse(
        task_id=task_id,
        status="submitted",
        message="任务已提交"
    )

# 任务状态查询接口
@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        TaskStatusResponse: 任务状态响应
    """
    # 查询Celery任务状态
    celery_task = celery_app.AsyncResult(task_id)
    
    # 准备响应
    response = TaskStatusResponse(
        task_id=task_id,
        status=celery_task.status
    )
    
    # 如果任务成功完成，返回结果
    if celery_task.successful():
        response.result = celery_task.result
        response.progress = 100.0
    
    # 如果任务失败，返回错误信息
    elif celery_task.failed():
        response.error = str(celery_task.result)
    
    # 如果任务正在进行中，返回进度信息
    elif celery_task.status == 'PROGRESS':
        if isinstance(celery_task.info, dict):
            response.progress = celery_task.info.get('progress', 0)
    
    return response

# 任务取消接口
@router.delete("/tasks/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str):
    """
    取消任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        TaskResponse: 任务响应
    """
    # 查询Celery任务
    celery_task = celery_app.AsyncResult(task_id)
    
    # 检查任务是否存在
    if not celery_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查任务是否已完成
    if celery_task.ready():
        raise HTTPException(status_code=400, detail="任务已完成，无法取消")
    
    # 取消任务
    celery_task.revoke(terminate=True)
    
    # 记录任务取消
    await send_task_log(
        task_id=task_id,
        message="任务已被用户取消",
        step="取消",
        level="warning"
    )
    
    # 更新任务状态
    await send_task_update(
        task_id=task_id,
        status="REVOKED",
        error="任务已被用户取消"
    )
    
    return TaskResponse(
        task_id=task_id,
        status="revoked",
        message="任务已取消"
    ) 