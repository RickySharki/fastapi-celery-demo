"""
FastAPI应用入口
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import API_PREFIX, PROJECT_NAME
from app.api.routes import router as api_router
from app.api.sse import router as sse_router

# 创建FastAPI应用
app = FastAPI(
    title=PROJECT_NAME,
    description="高性能数据处理系统API",
    version="0.1.0",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=API_PREFIX)
app.include_router(sse_router, prefix=API_PREFIX)

# 健康检查接口
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 