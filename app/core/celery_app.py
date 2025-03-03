"""
Celery应用配置
"""
from celery import Celery
from app.core.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# 创建Celery实例
celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.data_collection",
        "app.tasks.data_processing",
        "app.tasks.result_generation"
    ]
)

# 配置Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_concurrency=8,  # 可根据CPU核心数调整
    worker_prefetch_multiplier=4,  # 预取任务数
    task_acks_late=True,  # 任务完成后再确认
    task_reject_on_worker_lost=True,  # worker丢失时拒绝任务
    task_time_limit=3600,  # 任务超时时间（秒）
    broker_connection_retry=True,  # 连接断开时重试
    broker_connection_retry_on_startup=True,  # 启动时连接断开重试
)

# 使用gevent作为worker池
celery_app.conf.worker_pool = "gevent"

# 导出Celery实例
__all__ = ["celery_app"] 