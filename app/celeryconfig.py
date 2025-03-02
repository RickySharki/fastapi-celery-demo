# Windows平台特定配置
broker_url = 'redis://127.0.0.1:6379/0'
result_backend = 'redis://127.0.0.1:6379/0'
worker_pool_restarts = True

# 使用gevent池，适合I/O密集型任务
worker_pool = 'gevent'
worker_concurrency = 50  # 可以处理更多并发任务

# 其他通用配置
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
enable_utc = True

# 添加额外的Redis连接配置
broker_connection_retry_on_startup = True
broker_connection_max_retries = 10 