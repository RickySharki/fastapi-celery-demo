import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def start_redis():
    """启动Redis服务"""
    try:
        # 检查Redis是否已经运行
        redis_check = subprocess.run(['redis-cli', 'ping'], capture_output=True)
        if redis_check.returncode != 0:
            print("正在启动Redis服务...")
            redis_process = subprocess.Popen(['redis-server'], 
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
            time.sleep(2)  # 等待Redis启动
            return redis_process
        else:
            print("Redis服务已经在运行")
            return None
    except Exception as e:
        print(f"启动Redis时出错: {e}")
        sys.exit(1)

def start_celery():
    """启动Celery Worker"""
    cmd = [
        "celery", 
        "-A", "app.worker", 
        "worker", 
        "--pool=gevent",  # 使用gevent池，与start.bat一致
        "--concurrency=50",  # 设置并发数为50，与start.bat一致
        "--loglevel=info"
    ]
    print(f"启动Celery Worker: {' '.join(cmd)}")
    return subprocess.Popen(cmd)

def start_flower():
    """启动Flower监控"""
    cmd = [
        "celery",
        "-A", "app.worker",
        "flower",
        "--port=5555",
        "--basic_auth="  # 不使用认证
    ]
    print(f"启动Flower监控: {' '.join(cmd)}")
    return subprocess.Popen(cmd)

def start_fastapi():
    """启动FastAPI服务"""
    print("正在启动FastAPI服务...")
    fastapi_process = subprocess.Popen(
        ['uvicorn', 'app.main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return fastapi_process

def setup_debug_logging(process, name):
    """设置进程输出的日志记录"""
    def log_output(stream, prefix):
        for line in stream:
            if line:
                print(f"[{name}] {line.decode().strip()}")
    
    from threading import Thread
    Thread(target=log_output, args=(process.stdout, name), daemon=True).start()
    Thread(target=log_output, args=(process.stderr, name), daemon=True).start()

def cleanup_processes(processes):
    """清理所有进程"""
    for name, process in processes.items():
        if process and process.poll() is None:
            print(f"正在停止 {name}...")
            if sys.platform == 'win32':
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)

def main():
    # 存储所有进程
    processes = {}
    
    try:
        # 确保项目目录结构正确
        project_dir = Path(__file__).parent
        if not (project_dir / 'app').exists():
            print("错误：找不到app目录")
            sys.exit(1)
        
        processes['celery'] = start_celery()
        time.sleep(2)  # 等待Celery启动
        
        processes['flower'] = start_flower()  # 添加Flower启动
        time.sleep(1)
        
        processes['fastapi'] = start_fastapi()

        print("\n所有服务已启动。访问 http://localhost:8000 查看任务监控界面")
        print("按 Ctrl+C 停止所有服务\n")

        # 等待用户中断
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n正在停止所有服务...")
    finally:
        cleanup_processes(processes)
        print("所有服务已停止")

if __name__ == "__main__":
    main() 