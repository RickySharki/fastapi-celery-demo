"""
系统配置模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# API配置
API_PREFIX = "/api/v1"
PROJECT_NAME = "高性能数据处理系统"

# Celery配置
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# 并发控制配置
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "500"))
MAX_CONCURRENT_LLM_REQUESTS = int(os.getenv("MAX_CONCURRENT_LLM_REQUESTS", "100"))
MAX_CONCURRENT_DATA_SOURCES = int(os.getenv("MAX_CONCURRENT_DATA_SOURCES", "20"))
MAX_CONCURRENT_DIMENSIONS = int(os.getenv("MAX_CONCURRENT_DIMENSIONS", "10"))

# 超时配置（秒）
DATA_SOURCE_TIMEOUT = int(os.getenv("DATA_SOURCE_TIMEOUT", "30"))
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "10"))
DIMENSION_PROCESSING_TIMEOUT = int(os.getenv("DIMENSION_PROCESSING_TIMEOUT", "60"))

# 重试配置
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))  # 秒

# 模拟器配置
SIMULATE_DATA_SOURCE_DELAY_MIN = float(os.getenv("SIMULATE_DATA_SOURCE_DELAY_MIN", "0.1"))
SIMULATE_DATA_SOURCE_DELAY_MAX = float(os.getenv("SIMULATE_DATA_SOURCE_DELAY_MAX", "2.0"))
SIMULATE_LLM_DELAY_MIN = float(os.getenv("SIMULATE_LLM_DELAY_MIN", "0.2"))
SIMULATE_LLM_DELAY_MAX = float(os.getenv("SIMULATE_LLM_DELAY_MAX", "3.0"))
SIMULATE_ERROR_RATE = float(os.getenv("SIMULATE_ERROR_RATE", "0.05"))  # 5%错误率 