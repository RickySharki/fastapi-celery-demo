"""
结果生成任务模块
实现阶段3：生成最终结果
"""
from typing import Dict, Any, List
from celery import shared_task, states
import time
import asyncio
import json

from app.core.celery_app import celery_app
from app.simulators.result_generator import ResultGenerator
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

@shared_task(bind=True, name="tasks.generate_results")
def generate_results_task(self, task_id: str, processing_result: Dict[str, Any], 
                         dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    生成最终结果的任务
    
    Args:
        task_id: 任务ID
        processing_result: 处理结果
        dimensions: 结果维度配置
        
    Returns:
        Dict[str, Any]: 生成的最终结果
    """
    try:
        # 更新任务状态为进行中
        self.update_state(state="PROGRESS", meta={"progress": 65})
        sync_send_task_update(task_id, "PROGRESS", progress=65)
        sync_send_task_log(task_id, "开始结果生成任务", "结果生成开始", "info")
        
        # 记录维度信息
        sync_send_task_log(
            task_id, 
            f"准备生成 {len(dimensions)} 个维度的结果", 
            "结果维度", 
            "info", 
            progress=70
        )
        
        # 记录开始时间
        start_time = time.time()
        
        # 生成结果
        sync_send_task_log(task_id, "开始生成结果", "生成中", "info", progress=75)
        generator = ResultGenerator(dimensions)
        final_result = generator.generate(processing_result)
        
        # 计算生成时间
        generation_time = time.time() - start_time
        sync_send_task_log(
            task_id, 
            f"结果生成完成，耗时 {generation_time:.2f} 秒", 
            "生成完成", 
            "success", 
            progress=95
        )
        
        # 记录结果摘要
        result_summary = {
            "dimensions_count": len(final_result.get("dimensions", [])),
            "metrics_count": len(final_result.get("metrics", {})),
            "insights_count": len(final_result.get("insights", []))
        }
        sync_send_task_log(
            task_id, 
            f"生成结果摘要: {json.dumps(result_summary)}", 
            "结果摘要", 
            "info", 
            progress=98
        )
        
        # 更新任务状态为成功
        self.update_state(state=states.SUCCESS, meta={"progress": 100})
        sync_send_task_update(task_id, "SUCCESS", progress=100, result=final_result)
        sync_send_task_log(task_id, "任务全部完成", "完成", "success", progress=100)
        
        # 返回最终结果
        return final_result
        
    except Exception as e:
        # 记录错误
        error_message = f"结果生成任务失败: {str(e)}"
        sync_send_task_log(task_id, error_message, "错误", "error")
        sync_send_task_update(task_id, "FAILURE", error=error_message)
        
        # 重新抛出异常
        raise 