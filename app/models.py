from pydantic import BaseModel
from enum import Enum
from typing import Optional

class TaskStatus(str, Enum):
    PENDING = "PENDING"    # 使用大写以匹配Celery状态
    RUNNING = "STARTED"    # 匹配Celery的STARTED状态
    COMPLETED = "SUCCESS"  # 匹配Celery的SUCCESS状态
    FAILED = "FAILURE"     # 匹配Celery的FAILURE状态

class Task(BaseModel):
    id: str
    name: str
    status: TaskStatus
    result: Optional[str] = None 