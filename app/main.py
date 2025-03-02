from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, Response, Request
from celery import Celery
from .models import Task, TaskStatus
from uuid import uuid4
from typing import List
import asyncio
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
import json
import redis
from fastapi.responses import RedirectResponse
import httpx
import time

app = FastAPI()

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 添加根路由返回监控页面
@app.get("/")
async def get_monitor():
    return FileResponse("static/index.html")

# 初始化Celery
celery_app = Celery(
    "app",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0"
)

# 导入Celery配置
celery_app.config_from_object('app.celeryconfig')

# 内存中存储任务
tasks = {}

@app.post("/tasks/concurrent/{num_tasks}")
async def create_concurrent_tasks(num_tasks: int):
    """创建多个并发任务"""
    if num_tasks > 50:  # 限制最大任务数
        raise HTTPException(status_code=400, detail="最大支持50个并发任务")
    
    task_ids = []
    for i in range(num_tasks):
        # 创建任务
        celery_task = celery_app.send_task(
            "execute_task",
            args=[{"task_index": i}],
        )
        task_id = celery_task.id
        
        # 保存任务信息
        task = Task(
            id=task_id,
            name=f"AI任务-{i+1}",
            status=TaskStatus.PENDING,
            result=None,
            progress=0  # 确保设置初始进度
        )
        tasks[task_id] = task
        task_ids.append(task_id)
        print(f"创建任务: {task_id}")
    
    # 创建完所有任务后发布一次更新
    publish_task_update()
    
    return {
        "message": f"已创建{num_tasks}个并发任务",
        "task_ids": task_ids
    }

@app.post("/tasks/sequential/{execution_time}")
async def create_sequential_task(execution_time: int):
    """创建一个指定执行时间的任务"""
    # 提交到Celery
    celery_task = celery_app.send_task("long_running_task", args=[execution_time])
    task_id = celery_task.id  # 使用Celery的任务ID
    
    task = Task(
        id=task_id,
        name=f"顺序任务-{execution_time}秒",
        status=TaskStatus.PENDING,
        result=None
    )
    tasks[task_id] = task
    
    return {"task_id": task_id, "message": f"已创建执行时间为{execution_time}秒的任务"}

@app.get("/tasks/status/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 从Celery获取最新状态
    celery_task = celery_app.AsyncResult(task_id)
    current_status = celery_task.status
    
    if celery_task.ready():
        tasks[task_id].status = TaskStatus.COMPLETED
        tasks[task_id].result = str(celery_task.result)
    
    return {
        "task_id": task_id,
        "status": current_status,
        "result": celery_task.result if celery_task.ready() else None
    }

@app.get("/tasks/stream")
async def task_stream(request: Request):
    """任务状态流，使用SSE实时推送任务状态更新"""
    print(f"新的SSE连接已建立，客户端IP: {request.client.host}")
    
    async def event_generator():
        # 发送连接成功事件
        yield {
            "event": "connected",
            "data": json.dumps({"status": "connected"})
        }
        
        # 持续发送任务更新
        while True:
            if await request.is_disconnected():
                print(f"客户端断开连接: {request.client.host}")
                break
            
            # 获取所有任务的最新状态
            task_updates = []
            for task_id in list(tasks.keys()):
                try:
                    # 获取Celery任务
                    celery_task = celery_app.AsyncResult(task_id)
                    
                    # 更新任务状态
                    task = tasks[task_id]
                    
                    # 根据Celery任务状态更新本地任务状态
                    if celery_task.state == 'PENDING':
                        task.status = TaskStatus.PENDING
                    elif celery_task.state == 'STARTED' or celery_task.state == 'PROGRESS':
                        task.status = TaskStatus.RUNNING
                        # 如果有进度信息，更新进度
                        if celery_task.info and isinstance(celery_task.info, dict) and 'progress' in celery_task.info:
                            task.progress = celery_task.info['progress']
                    elif celery_task.state == 'SUCCESS':
                        task.status = TaskStatus.SUCCESS
                        task.progress = 100
                        # 更新结果
                        if celery_task.result and isinstance(celery_task.result, dict):
                            task.result = celery_task.result.get('result', '任务完成')
                    elif celery_task.state == 'FAILURE':
                        task.status = TaskStatus.FAILED
                        task.result = str(celery_task.result)
                    
                    # 添加到更新列表
                    task_updates.append(task.dict())
                except Exception as e:
                    print(f"处理任务 {task_id} 状态时出错: {e}")
            
            # 发送更新
            if task_updates:
                print(f"发送任务更新，共 {len(task_updates)} 个任务")
                yield {
                    "event": "update",
                    "data": json.dumps({"tasks": task_updates})
                }
            
            # 等待一段时间再发送下一次更新
            await asyncio.sleep(1)
    
    return EventSourceResponse(event_generator())

@app.get("/test-sse")
async def test_sse():
    """测试SSE连接"""
    async def event_generator():
        for i in range(10):
            yield {
                "event": "test",
                "data": json.dumps({"count": i, "message": "测试消息"})
            }
            await asyncio.sleep(1)
    
    return EventSourceResponse(event_generator())

@app.get("/test")
async def get_test_page():
    return FileResponse("static/test-sse.html")

@app.post("/tasks/clear")
async def clear_tasks():
    """清除所有任务并尝试终止正在执行的任务"""
    task_count = len(tasks)
    
    # 尝试终止Celery中的任务
    terminated_count = 0
    for task_id in list(tasks.keys()):
        try:
            # 获取任务
            celery_task = celery_app.AsyncResult(task_id)
            
            # 尝试终止任务（如果还在执行）
            if celery_task.state in ['PENDING', 'STARTED', 'RETRY']:
                celery_task.revoke(terminate=True, signal='SIGTERM')
                terminated_count += 1
                print(f"已终止任务: {task_id}")
        except Exception as e:
            print(f"终止任务 {task_id} 失败: {e}")
    
    # 清除内存中的任务记录
    tasks.clear()
    
    message = f"已清除所有任务记录，共{task_count}个，成功终止{terminated_count}个正在执行的任务"
    print(message)
    return {"message": message}

@app.post("/tasks/reset-queue")
async def reset_queue():
    """完全重置Celery队列（危险操作）"""
    try:
        # 清除所有任务记录
        tasks.clear()
        
        # 清空Redis中的Celery队列
        redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)
        redis_client.flushdb()
        
        return {"message": "已完全重置Celery队列和任务记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置队列失败: {str(e)}")

@app.post("/tasks/control")
async def control_workers():
    """控制Celery workers"""
    try:
        # 发送控制命令到所有worker
        # 1. 取消所有排队任务
        celery_app.control.purge()
        
        # 2. 撤销所有正在执行的任务
        celery_app.control.revoke(tasks.keys(), terminate=True, signal='SIGTERM')
        
        # 3. 可选：重启workers (谨慎使用)
        # celery_app.control.broadcast('pool_restart', arguments={'reload': True})
        
        # 清除内存中的任务记录
        tasks.clear()
        
        return {"message": "已成功清除所有任务并重置worker状态"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"控制worker失败: {str(e)}")

@app.get("/flower")
async def redirect_to_flower():
    """重定向到Flower监控界面"""
    return RedirectResponse(url="http://localhost:5555")

@app.get("/flower-proxy/")
@app.get("/flower-proxy/{path:path}")
async def flower_proxy(request: Request, path: str = ""):
    """代理Flower请求，避免跨域问题"""
    # 构建完整URL
    flower_url = f"http://localhost:5555/{path}"
    if request.query_params:
        query_string = str(request.query_params)
        flower_url = f"{flower_url}?{query_string}"
    
    print(f"代理请求到: {flower_url}")
    
    try:
        # 转发请求到Flower
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=flower_url,
                headers={k: v for k, v in request.headers.items() 
                         if k.lower() not in ["host", "content-length"]},
                content=await request.body(),
                cookies=request.cookies,
                follow_redirects=True
            )
        
        # 返回Flower的响应
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items()
                    if k.lower() not in ["content-encoding", "transfer-encoding"]},
            media_type=response.headers.get("content-type", "text/html")
        )
    except Exception as e:
        print(f"代理请求失败: {str(e)}")
        return Response(
            content=f"代理请求失败: {str(e)}",
            status_code=500,
            media_type="text/plain"
        )

@app.get("/worker-status")
async def get_worker_status():
    """获取Worker状态摘要"""
    try:
        # 获取worker状态
        stats = celery_app.control.inspect().stats() or {}
        active = celery_app.control.inspect().active() or {}
        
        workers = []
        for worker_name, stats_data in stats.items():
            worker_info = {
                "name": worker_name,
                "status": "在线",
                "active_tasks": len(active.get(worker_name, [])),
                "processed": stats_data.get("total", {}).get("task-received", 0)
            }
            workers.append(worker_info)
        
        return {"workers": workers}
    except Exception as e:
        print(f"获取Worker状态失败: {str(e)}")
        return {"workers": [], "error": str(e)}

@app.get("/flower-status")
async def get_flower_status_page():
    """返回简单的Flower状态页面"""
    return FileResponse("static/flower-status.html")

# 修改publish_task_update函数
def publish_task_update():
    """发布任务更新到Redis"""
    try:
        # 获取所有任务
        task_list = [task.dict() for task in tasks.values()]
        data = json.dumps({"tasks": task_list})
        
        # 连接Redis并发布
        redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)
        result = redis_client.publish("task-updates", data)
        print(f"任务更新已发布到Redis，接收者数量: {result}, 数据长度: {len(data)}")
        
        # 如果没有接收者，可能是SSE连接有问题
        if result == 0:
            print("警告: 没有接收者接收任务更新")
        
        return True
    except Exception as e:
        print(f"发布任务更新失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 修改任务状态更新的地方，确保调用publish_task_update
@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """获取单个任务的状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 获取Celery任务
    celery_task = celery_app.AsyncResult(task_id)
    
    # 更新任务状态
    task = tasks[task_id]
    old_status = task.status
    
    # 根据Celery任务状态更新本地任务状态
    if celery_task.state == 'PENDING':
        task.status = TaskStatus.PENDING
    elif celery_task.state == 'STARTED' or celery_task.state == 'PROGRESS':
        task.status = TaskStatus.RUNNING
        # 如果有进度信息，更新进度
        if celery_task.info and isinstance(celery_task.info, dict) and 'progress' in celery_task.info:
            task.progress = celery_task.info['progress']
    elif celery_task.state == 'SUCCESS':
        task.status = TaskStatus.SUCCESS
        task.progress = 100
        # 更新结果
        if celery_task.result and isinstance(celery_task.result, dict):
            task.result = celery_task.result.get('result', '任务完成')
    elif celery_task.state == 'FAILURE':
        task.status = TaskStatus.FAILED
        task.result = str(celery_task.result)
    
    # 如果状态有变化，发布更新
    if old_status != task.status or task.progress != getattr(task, 'old_progress', None):
        task.old_progress = task.progress  # 记录旧进度
        print(f"任务 {task_id} 状态变化: {old_status} -> {task.status}, 进度: {task.progress}%")
        publish_task_update()
    
    return task.dict()

@app.post("/tasks/refresh")
async def refresh_tasks():
    """手动刷新所有任务状态并推送更新"""
    updated_count = 0
    
    for task_id in list(tasks.keys()):
        try:
            # 获取Celery任务
            celery_task = celery_app.AsyncResult(task_id)
            
            # 更新任务状态
            task = tasks[task_id]
            old_status = task.status
            
            # 根据Celery任务状态更新本地任务状态
            if celery_task.state == 'PENDING':
                task.status = TaskStatus.PENDING
            elif celery_task.state == 'STARTED' or celery_task.state == 'PROGRESS':
                task.status = TaskStatus.RUNNING
                # 如果有进度信息，更新进度
                if celery_task.info and isinstance(celery_task.info, dict) and 'progress' in celery_task.info:
                    task.progress = celery_task.info['progress']
            elif celery_task.state == 'SUCCESS':
                task.status = TaskStatus.SUCCESS
                task.progress = 100
                # 更新结果
                if celery_task.result and isinstance(celery_task.result, dict):
                    task.result = celery_task.result.get('result', '任务完成')
            elif celery_task.state == 'FAILURE':
                task.status = TaskStatus.FAILED
                task.result = str(celery_task.result)
            
            # 如果状态有变化，计数
            if old_status != task.status:
                updated_count += 1
        except Exception as e:
            print(f"刷新任务 {task_id} 状态失败: {e}")
    
    # 无论是否有更新，都发布一次
    publish_task_update()
    
    return {"message": f"已刷新所有任务状态，{updated_count}个任务有状态变化"}

# 添加一个后台任务来定期刷新任务状态
@app.on_event("startup")
async def setup_periodic_tasks():
    """设置定期任务"""
    asyncio.create_task(periodic_task_refresh())

async def periodic_task_refresh():
    """定期刷新任务状态"""
    while True:
        try:
            # 每秒刷新一次任务状态
            for task_id in list(tasks.keys()):
                try:
                    # 获取Celery任务
                    celery_task = celery_app.AsyncResult(task_id)
                    
                    # 更新任务状态
                    task = tasks[task_id]
                    old_status = task.status
                    old_progress = getattr(task, 'progress', 0)
                    
                    # 根据Celery任务状态更新本地任务状态
                    if celery_task.state == 'PENDING':
                        task.status = TaskStatus.PENDING
                    elif celery_task.state == 'STARTED' or celery_task.state == 'PROGRESS':
                        task.status = TaskStatus.RUNNING
                        # 如果有进度信息，更新进度
                        if celery_task.info and isinstance(celery_task.info, dict) and 'progress' in celery_task.info:
                            task.progress = celery_task.info['progress']
                    elif celery_task.state == 'SUCCESS':
                        task.status = TaskStatus.SUCCESS
                        task.progress = 100
                        # 更新结果
                        if celery_task.result and isinstance(celery_task.result, dict):
                            task.result = celery_task.result.get('result', '任务完成')
                    elif celery_task.state == 'FAILURE':
                        task.status = TaskStatus.FAILED
                        task.result = str(celery_task.result)
                    
                    # 如果状态或进度有变化，记录日志
                    if old_status != task.status or old_progress != getattr(task, 'progress', 0):
                        print(f"任务 {task_id} 状态变化: {old_status} -> {task.status}, 进度: {getattr(task, 'progress', 0)}%")
                except Exception as e:
                    print(f"刷新任务 {task_id} 状态失败: {e}")
            
            # 发布更新
            if tasks:
                publish_task_update()
                
        except Exception as e:
            print(f"定期刷新任务出错: {e}")
        
        # 等待下一次刷新
        await asyncio.sleep(1) 

@app.get("/test-redis")
async def test_redis():
    """测试Redis发布/订阅功能"""
    try:
        # 连接Redis
        redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)
        
        # 发布测试消息
        test_data = json.dumps({"test": "message", "timestamp": time.time()})
        result = redis_client.publish("test-channel", test_data)
        
        return {
            "status": "success",
            "receivers": result,
            "message": "测试消息已发布到Redis"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Redis测试失败"
        } 