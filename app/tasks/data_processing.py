"""
数据处理任务模块
实现阶段2：处理收集到的数据
"""
from typing import Dict, Any, List
from celery import shared_task, states
import time
import asyncio

from app.core.celery_app import celery_app
from app.simulators.data_processor import DataProcessor
from app.tasks.result_generation import generate_results_task
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

@shared_task(bind=True, name="tasks.process_data")
def process_data_task(self, task_id: str, collection_result: Dict[str, Any], 
                     llm_config: Dict[str, Any], dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    处理收集到的数据的任务
    
    Args:
        task_id: 任务ID
        collection_result: 收集的数据
        llm_config: LLM配置
        dimensions: 结果维度配置
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    try:
        # 更新任务状态为进行中
        self.update_state(state="PROGRESS", meta={"progress": 35})
        sync_send_task_update(task_id, "PROGRESS", progress=35)
        sync_send_task_log(task_id, "开始数据处理任务", "处理开始", "info")
        
        # 记录数据处理信息
        data_count = len(collection_result) if isinstance(collection_result, list) else 0
        sync_send_task_log(
            task_id, 
            f"准备处理 {data_count} 条数据", 
            "数据处理", 
            "info", 
            progress=40
        )
        
        # 记录开始时间
        start_time = time.time()
        
        # 处理数据
        sync_send_task_log(task_id, "开始处理数据", "处理中", "info", progress=45)
        processor = DataProcessor(llm_config)
        processing_result = processor.process(collection_result)
        
        # 计算处理时间
        processing_time = time.time() - start_time
        sync_send_task_log(
            task_id, 
            f"数据处理完成，耗时 {processing_time:.2f} 秒", 
            "处理完成", 
            "success", 
            progress=60
        )
        
        # 更新任务状态
        self.update_state(state="PROGRESS", meta={"progress": 60})
        sync_send_task_update(task_id, "PROGRESS", progress=60)
        
        # 启动结果生成任务
        sync_send_task_log(task_id, "启动结果生成任务", "结果生成", "info")
        generate_task = generate_results_task.delay(task_id, processing_result, dimensions)
        
        # 返回处理结果
        return processing_result
        
    except Exception as e:
        # 记录错误
        error_message = f"数据处理任务失败: {str(e)}"
        sync_send_task_log(task_id, error_message, "错误", "error")
        sync_send_task_update(task_id, "FAILURE", error=error_message)
        
        # 重新抛出异常
        raise 