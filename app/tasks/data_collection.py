"""
数据收集任务模块
实现阶段1：从多个数据源并行收集数据
"""
from typing import Dict, Any, List
from celery import shared_task, states
import gevent
import asyncio
import time

from app.core.celery_app import celery_app
from app.simulators.data_sources import DataSourceManager
from app.tasks.data_processing import process_data_task
from app.api.sse import send_task_update, send_task_log

# 创建事件循环，用于异步调用SSE函数
def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

# 同步包装器，用于在Celery任务中调用异步函数
def sync_send_task_update(task_id, status, progress=None, result=None, error=None):
    loop = get_event_loop()
    loop.run_until_complete(
        send_task_update(task_id, status, progress, result, error)
    )

def sync_send_task_log(task_id, message, step=None, level="info", progress=None):
    loop = get_event_loop()
    loop.run_until_complete(
        send_task_log(task_id, message, step, level, progress)
    )

@shared_task(bind=True, name="tasks.collect_data")
def collect_data_task(self, task_id: str, data_sources: List[Dict[str, Any]], 
                     llm_config: Dict[str, Any], dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    从多个数据源并行收集数据的任务
    
    Args:
        task_id: 任务ID
        data_sources: 数据源配置列表
        llm_config: LLM配置
        dimensions: 结果维度配置
        
    Returns:
        Dict[str, Any]: 收集的数据
    """
    try:
        # 更新任务状态为开始
        self.update_state(state=states.STARTED)
        sync_send_task_update(task_id, "STARTED", progress=0)
        sync_send_task_log(task_id, "开始数据收集任务", "开始", "info")
        
        # 记录数据源信息
        sync_send_task_log(
            task_id, 
            f"准备从 {len(data_sources)} 个数据源收集数据", 
            "数据源", 
            "info"
        )
        
        # 记录开始时间
        start_time = time.time()
        
        # 从数据源收集数据
        sync_send_task_log(task_id, "开始并行收集数据", "收集", "info", progress=5)
        collection_result = DataSourceManager.fetch_from_sources(data_sources)
        
        # 计算收集时间
        collection_time = time.time() - start_time
        sync_send_task_log(
            task_id, 
            f"数据收集完成，耗时 {collection_time:.2f} 秒，收集了 {len(collection_result)} 条数据", 
            "收集完成", 
            "success", 
            progress=30
        )
        
        # 更新任务状态为进行中
        self.update_state(
            state="PROGRESS",
            meta={"progress": 30}
        )
        sync_send_task_update(task_id, "PROGRESS", progress=30)
        
        # 启动数据处理任务
        sync_send_task_log(task_id, "启动数据处理任务", "处理", "info")
        process_task = process_data_task.delay(task_id, collection_result, llm_config, dimensions)
        
        # 返回收集结果
        return collection_result
        
    except Exception as e:
        # 记录错误
        error_message = f"数据收集任务失败: {str(e)}"
        sync_send_task_log(task_id, error_message, "错误", "error")
        sync_send_task_update(task_id, "FAILURE", error=error_message)
        
        # 重新抛出异常
        raise 