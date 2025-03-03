# 高性能数据处理系统

基于FastAPI+Celery+Gevent的高性能数据处理系统，用于处理大量并发的数据处理任务。

## 系统架构

系统采用FastAPI+Celery+Gevent架构，具有以下特点：

- **FastAPI**：高性能异步Web框架，提供API接口
- **Celery**：分布式任务队列，处理后台任务
- **Gevent**：基于协程的并发库，提高I/O密集型操作效率
- **Redis**：作为Celery的消息代理和结果后端

系统处理流程分为三个主要阶段：

1. **数据收集**：从多个数据源并行收集数据
2. **数据处理与评估**：使用LLM对数据进行处理和评分
3. **结果生成**：基于处理结果生成多维度分析

## 目录结构

```
project/
├── app/
│   ├── api/              # API接口
│   ├── core/             # 核心配置
│   ├── tasks/            # Celery任务
│   ├── simulators/       # 模拟器
│   └── utils/            # 工具函数
├── celery_worker.py      # Celery worker启动脚本
├── main.py               # FastAPI应用入口
├── requirements.txt      # 项目依赖
└── README.md             # 项目文档
```

## 环境要求

- Python 3.8+
- Redis 5.0+

## 安装

1. 克隆仓库

```bash
git clone <repository-url>
cd high-performance-data-processor
```

2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 启动Redis（如果尚未运行）

```bash
# 使用Docker启动Redis
docker run -d -p 6379:6379 redis:alpine

# 或者使用本地安装的Redis
redis-server
```

## 运行

1. 启动FastAPI应用

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. 启动Celery worker

```bash
python celery_worker.py
```

3. （可选）启动Flower监控

```bash
celery -A app.core.celery_app flower
```

## API接口

系统提供以下API接口：

- `POST /api/v1/tasks`：提交新任务
- `GET /api/v1/tasks/{task_id}`：查询任务状态
- `DELETE /api/v1/tasks/{task_id}`：取消任务

### 提交任务示例

```bash
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "data_sources": [
      {"id": "db1", "type": "database", "connection": "..."},
      {"id": "api1", "type": "api", "url": "..."}
    ],
    "llm_config": {
      "model": "gpt-3.5-turbo",
      "temperature": 0.7
    },
    "dimensions": [
      {"id": "dim1", "name": "质量评估", "threshold": 0.6},
      {"id": "dim2", "name": "相关性分析", "threshold": 0.5}
    ]
  }'
```

## 性能特点

- 支持500-1000个并发任务
- 使用Gevent处理I/O密集型操作，避免阻塞
- 通过Celery实现任务分发和负载均衡
- 实现自适应限流和错误重试机制

## 开发指南

### 添加新的数据源

在`app/simulators/data_sources.py`中扩展`DataSourceSimulator`类。

### 添加新的结果维度

在任务提交时配置新的维度参数，系统会自动处理。

### 自定义LLM处理逻辑

修改`app/simulators/llm_service.py`中的处理逻辑。

## 许可证

[MIT License](LICENSE)