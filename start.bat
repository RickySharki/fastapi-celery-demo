@echo off
echo 正在启动Redis服务...
start /wait redis-server.exe

REM 等待Redis完全启动
timeout /t 5
echo Redis服务已启动

echo 正在启动Celery Worker...
REM 使用gevent池和50个并发worker
start celery -A app.worker worker --pool=gevent --concurrency=50 --loglevel=info

REM 等待Celery启动
timeout /t 5
echo Celery Worker已启动

echo 正在启动FastAPI服务...
start uvicorn app.main:app --reload

REM 启动Flower监控（不使用认证，简化配置）
start celery -A app.worker flower --port=5555 --basic_auth=

echo 所有服务已启动完成！ 