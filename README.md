# FastAPI 异步任务处理系统

一个基于FastAPI的异步任务处理系统，支持多任务并行处理和实时状态推送。

## 系统架构 
Client <-> FastAPI Server <-> Task Queue <-> Task Workers
<-> WebSocket <-> Task Status Updates

### 核心组件

- **FastAPI Server**: 处理HTTP请求和WebSocket连接
- **Celery**: 分布式任务队列
- **Redis**: 消息代理和结果存储
- **WebSocket**: 实时任务状态推送

## 技术栈

- Python 3.8+
- FastAPI
- Celery
- Redis
- WebSocket

## 依赖要求
fastapi==0.103.1
uvicorn==0.23.2
celery==5.3.1
redis==5.0.0
websockets==11.0.3

## 项目结构
app/
├── init.py
├── main.py # FastAPI应用主入口
├── models.py # 数据模型定义
└── worker.py # Celery Worker实现

## 功能特性

- 异步任务提交和处理
- 实时任务状态推送
- 多任务并行处理
- 任务结果持久化
- WebSocket实时通信

## 快速开始

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 启动Redis服务:

Windows环境:
```bash
# 方法1：通过Windows服务启动
net start redis

# 或方法2：直接运行Redis服务器
redis-server.exe
```

Linux/Mac环境:
```bash
redis-server
```

3. 启动Celery Worker:

Windows环境:
```bash
# 使用 -P solo 参数启动
celery -A app.worker worker --pool=solo --loglevel=info
```

Linux/Mac环境:
```bash
celery -A app.worker worker --loglevel=info
```

4. 启动FastAPI服务:
```bash
uvicorn app.main:app --reload
```

## API接口

### HTTP接口

- `POST /tasks/`: 创建新任务
  ```json
  {
    "id": "task-001",
    "name": "示例任务",
    "status": "pending"
  }
  ```

### WebSocket接口

- `ws://localhost:8000/ws/{client_id}`: 任务状态推送

## 开发说明

### 任务状态流转

```
PENDING -> RUNNING -> COMPLETED/FAILED
```

### 数据模型

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: str
    name: str
    status: TaskStatus
    result: Optional[str] = None
```

## 扩展性

- 支持水平扩展Worker数量
- 可配置任务优先级
- 支持失败任务重试机制

## 注意事项

- 确保Redis服务正常运行
- Worker进程需要足够的系统资源
- 建议在生产环境配置适当的并发数