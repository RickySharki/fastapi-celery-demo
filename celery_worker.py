"""
Celery worker启动脚本
"""
import os
import gevent.monkey

# 在导入任何其他库之前应用猴子补丁
gevent.monkey.patch_all()

from app.core.celery_app import celery_app

if __name__ == "__main__":
    # 启动Celery worker
    celery_app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            "--pool=gevent",
            "--concurrency=8",  # 可根据CPU核心数调整
            "--hostname=worker@%h"
        ]
    )