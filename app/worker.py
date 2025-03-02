import time
from celery import Celery, current_task
import os
from random import randint
import httpx
import asyncio
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

# 设置环境变量
os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

app = Celery('app')
app.config_from_object('app.celeryconfig')

@app.task(name='execute_task', bind=True, soft_time_limit=30, time_limit=60)
def execute_task(self, task_data):
    """模拟AI任务执行，带超时控制"""
    task_id = self.request.id
    print(f"开始执行任务 {task_id}")
    
    try:
        # 定期发送心跳
        self.update_state(state='PROGRESS', meta={'progress': 0})
        
        # 模拟HTTP请求延迟
        process_time = randint(3, 8)
        
        # 模拟HTTP请求
        with httpx.Client(timeout=30.0) as client:
            # 不再检查是否被撤销，简化逻辑
            
            # 模拟处理
            time.sleep(process_time)
            self.update_state(state='PROGRESS', meta={'progress': 50})
            
            # 模拟任务结果
            result = f"AI处理完成，API调用耗时{process_time}秒，任务ID: {task_id}"
            print(f"任务完成: {result}")
            
            return {
                "status": "SUCCESS",
                "result": result
            }
    except SoftTimeLimitExceeded:
        print(f"任务 {task_id} 超过软时间限制，正在优雅退出")
        return {"status": "TIMEOUT", "error": "任务执行时间过长"}
    except TimeLimitExceeded:
        print(f"任务 {task_id} 超过硬时间限制，被强制终止")
        # 这个异常会导致任务被终止，不会返回
    except Exception as e:
        print(f"任务失败: {str(e)}")
        return {
            "status": "FAILURE",
            "error": str(e)
        }

@app.task(name='long_running_task')
def long_running_task(seconds: int):
    """可配置执行时间的任务"""
    time.sleep(seconds)
    return f"任务执行了{seconds}秒" 