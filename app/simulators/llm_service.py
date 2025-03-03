"""
LLM服务模拟器
模拟大语言模型API的响应
"""
import random
import gevent
from typing import Dict, Any, List, Optional

from app.core.config import (
    SIMULATE_LLM_DELAY_MIN,
    SIMULATE_LLM_DELAY_MAX,
    SIMULATE_ERROR_RATE,
    MAX_CONCURRENT_LLM_REQUESTS
)

class LLMServiceSimulator:
    """LLM服务模拟器"""
    
    def __init__(self, llm_config: Dict[str, Any]):
        """
        初始化LLM服务模拟器
        
        Args:
            llm_config: LLM配置
        """
        self.llm_config = llm_config
        self.model = llm_config.get("model", "default-model")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 100)
        
        # 创建并发控制信号量
        self.semaphore = gevent.lock.BoundedSemaphore(MAX_CONCURRENT_LLM_REQUESTS)
    
    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个数据项
        
        Args:
            item: 要处理的数据项
            
        Returns:
            Dict[str, Any]: 处理结果
            
        Raises:
            Exception: 模拟LLM处理错误
        """
        # 使用信号量控制并发
        with self.semaphore:
            # 模拟延迟
            delay = random.uniform(
                SIMULATE_LLM_DELAY_MIN,
                SIMULATE_LLM_DELAY_MAX
            )
            gevent.sleep(delay)
            
            # 模拟错误
            if random.random() < SIMULATE_ERROR_RATE:
                raise Exception(f"模拟LLM处理错误: {item.get('id', 'unknown')}")
            
            # 生成模拟评分和分析
            score = random.uniform(0, 1)
            analysis = self._generate_analysis(item, score)
            
            return {
                "item_id": item.get("id", "unknown"),
                "score": score,
                "analysis": analysis,
                "metadata": {
                    "model": self.model,
                    "processing_time_ms": int(delay * 1000),
                    "tokens_used": random.randint(50, self.max_tokens)
                }
            }
    
    def _generate_analysis(self, item: Dict[str, Any], score: float) -> str:
        """
        生成模拟分析文本
        
        Args:
            item: 数据项
            score: 评分
            
        Returns:
            str: 分析文本
        """
        quality_terms = ["低质量", "一般", "良好", "优质", "卓越"]
        quality_index = min(int(score * 5), 4)
        quality = quality_terms[quality_index]
        
        return f"该数据项评估为{quality}，得分{score:.2f}。" + \
               f"数据完整性评估：{random.uniform(0.5, 1.0):.2f}。" + \
               f"数据相关性评估：{random.uniform(0.5, 1.0):.2f}。" + \
               "建议：" + random.choice([
                   "进一步完善数据",
                   "数据可以直接使用",
                   "需要额外验证",
                   "建议与其他数据源交叉验证"
               ])
    
    def process_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        并行处理一批数据项
        
        Args:
            items: 要处理的数据项列表
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        results = []
        errors = []
        
        def _process_item(item):
            try:
                result = self.process_item(item)
                return result, None
            except Exception as e:
                return None, {"item_id": item.get("id", "unknown"), "error": str(e)}
        
        # 使用gevent并行处理
        jobs = [gevent.spawn(_process_item, item) for item in items]
        gevent.joinall(jobs)
        
        # 收集结果
        for job in jobs:
            result, error = job.value
            if error:
                errors.append(error)
            else:
                results.append(result)
        
        return {
            "results": results,
            "errors": errors,
            "success_count": len(results),
            "error_count": len(errors),
            "total_count": len(items)
        } 