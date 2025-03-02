#!/usr/bin/env python
import redis
import requests
import time
import os
import signal
import psutil
import sys

def shutdown_system():
    """优雅关闭整个系统"""
    print("开始优雅关闭系统...")
    
    # 1. 停止接受新任务
    try:
        print("停止接受新任务...")
        requests.post("http://localhost:8000/tasks/control", 
                     json={"action": "stop_accepting"})
    except Exception as e:
        print(f"停止接受新任务失败: {e}")
    
    # 2. 等待正在执行的任务完成或超时
    print("等待正在执行的任务完成...")
    timeout = 30  # 30秒超时
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get("http://localhost:8000/tasks/active-count")
            active_tasks = response.json().get("active_tasks", 0)
            if active_tasks == 0:
                print("所有任务已完成")
                break
            print(f"还有 {active_tasks} 个任务正在执行...")
            time.sleep(2)
        except Exception:
            break
    
    # 3. 强制终止剩余任务
    print("终止剩余任务...")
    try:
        requests.post("http://localhost:8000/tasks/reset-queue")
    except Exception as e:
        print(f"终止剩余任务失败: {e}")
    
    # 4. 关闭各个服务
    print("关闭服务...")
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            if 'celery' in cmdline or 'uvicorn' in cmdline or 'redis-server' in cmdline:
                print(f"终止进程: {proc.info['pid']} - {cmdline}")
                os.kill(proc.info['pid'], signal.SIGTERM)
        except Exception as e:
            print(f"终止进程失败: {e}")
    
    print("系统已关闭")

if __name__ == "__main__":
    shutdown_system()
    sys.exit(0) 