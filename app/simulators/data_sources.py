"""
数据源模拟器
模拟从多个数据源获取数据
"""
import time
import random
import uuid
import gevent
from typing import Dict, Any, List
from datetime import datetime

class DataSourceManager:
    """数据源管理器"""
    
    @staticmethod
    def fetch_from_sources(data_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从多个数据源并行获取数据
        
        Args:
            data_sources: 数据源配置列表
            
        Returns:
            List[Dict[str, Any]]: 收集的数据
        """
        results = []
        
        # 创建协程列表
        coroutines = []
        for source in data_sources:
            coroutines.append(gevent.spawn(DataSourceManager._fetch_source_async, source))
        
        # 使用gevent并行执行所有协程
        source_results = gevent.joinall(coroutines)
        
        # 收集结果
        for result in source_results:
            if result.value:
                results.append(result.value)
        
        return results
    
    @staticmethod
    def _fetch_source_async(source):
        """
        异步获取单个数据源的数据
        
        Args:
            source: 数据源配置
            
        Returns:
            Dict[str, Any]: 数据源结果
        """
        # 模拟数据源访问延迟
        gevent.sleep(random.uniform(0.05, 0.3))  # 减少延迟时间
        
        source_id = source.get("id", str(uuid.uuid4()))
        source_type = source.get("type", "generic")
        
        try:
            # 模拟随机错误
            if random.random() < 0.05:  # 降低错误率
                raise Exception(f"无法连接到数据源 {source_id}")
            
            # 根据数据源类型获取数据
            if source_type == "database":
                data = DataSourceManager._fetch_from_database(source)
            elif source_type == "api":
                data = DataSourceManager._fetch_from_api(source)
            elif source_type == "file":
                data = DataSourceManager._fetch_from_file(source)
            else:
                data = DataSourceManager._fetch_generic_data(source)
            
            # 添加数据源信息
            data_item = {
                "source_id": source_id,
                "source_type": source_type,
                "timestamp": datetime.now().isoformat(),
                "data": data,
                "status": "success"
            }
            
            return data_item
            
        except Exception as e:
            # 记录错误
            error_data = {
                "source_id": source_id,
                "source_type": source_type,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "error"
            }
            
            return error_data
    
    @staticmethod
    def _fetch_from_database(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从数据库获取数据
        
        Args:
            config: 数据库配置
            
        Returns:
            Dict[str, Any]: 获取的数据
        """
        db_type = config.get("db_type", "mysql")
        table = config.get("table", "data")
        
        # 模拟数据库查询延迟
        time.sleep(random.uniform(0.3, 0.7))
        
        # 模拟数据库记录
        record_count = random.randint(5, 20)
        records = []
        
        for i in range(record_count):
            record = {
                "id": f"rec_{i}",
                "value": random.uniform(0, 100),
                "category": random.choice(["A", "B", "C"]),
                "timestamp": (datetime.now().timestamp() - random.uniform(0, 86400)),
                "metadata": {
                    "source": db_type,
                    "quality": random.uniform(0, 1)
                }
            }
            records.append(record)
        
        return {
            "db_type": db_type,
            "table": table,
            "record_count": record_count,
            "records": records
        }
    
    @staticmethod
    def _fetch_from_api(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从API获取数据
        
        Args:
            config: API配置
            
        Returns:
            Dict[str, Any]: 获取的数据
        """
        api_url = config.get("url", "https://api.example.com")
        endpoint = config.get("endpoint", "/data")
        
        # 模拟API请求延迟
        time.sleep(random.uniform(0.5, 1.2))
        
        # 模拟API响应
        item_count = random.randint(3, 15)
        items = []
        
        for i in range(item_count):
            item = {
                "id": f"item_{i}",
                "name": f"Item {i}",
                "value": random.uniform(0, 100),
                "tags": random.sample(["tag1", "tag2", "tag3", "tag4", "tag5"], random.randint(1, 3))
            }
            items.append(item)
        
        return {
            "api_url": api_url,
            "endpoint": endpoint,
            "status_code": 200,
            "response_time": random.uniform(0.1, 0.8),
            "items": items
        }
    
    @staticmethod
    def _fetch_from_file(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从文件获取数据
        
        Args:
            config: 文件配置
            
        Returns:
            Dict[str, Any]: 获取的数据
        """
        file_path = config.get("path", "/path/to/file.txt")
        file_type = config.get("file_type", "text")
        
        # 模拟文件读取延迟
        time.sleep(random.uniform(0.2, 0.6))
        
        # 模拟文件内容
        if file_type == "text":
            lines = [
                "这是第一行文本数据",
                "这是第二行文本数据，包含一些信息",
                "这是第三行，有更多的细节和数据点",
                "第四行包含一些数值：123, 456, 789",
                "最后一行总结了前面的内容"
            ]
            content = "\n".join(lines)
        elif file_type == "csv":
            lines = [
                "id,name,value,category",
                "1,Item 1,45.6,A",
                "2,Item 2,78.9,B",
                "3,Item 3,12.3,A",
                "4,Item 4,34.5,C"
            ]
            content = "\n".join(lines)
        elif file_type == "json":
            content = """
            {
                "items": [
                    {"id": 1, "name": "Item 1", "value": 45.6},
                    {"id": 2, "name": "Item 2", "value": 78.9},
                    {"id": 3, "name": "Item 3", "value": 12.3}
                ],
                "metadata": {
                    "count": 3,
                    "source": "file"
                }
            }
            """
        else:
            content = f"未知文件类型: {file_type}"
        
        return {
            "file_path": file_path,
            "file_type": file_type,
            "size": len(content),
            "content": content
        }
    
    @staticmethod
    def _fetch_generic_data(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取通用数据
        
        Args:
            config: 通用配置
            
        Returns:
            Dict[str, Any]: 获取的数据
        """
        # 模拟处理延迟
        time.sleep(random.uniform(0.1, 0.5))
        
        # 生成随机数据点
        data_points = []
        point_count = random.randint(5, 15)
        
        for i in range(point_count):
            data_points.append({
                "id": f"point_{i}",
                "x": random.uniform(0, 100),
                "y": random.uniform(0, 100),
                "z": random.uniform(0, 100),
                "label": random.choice(["类别A", "类别B", "类别C", "类别D"])
            })
        
        return {
            "data_points": data_points,
            "point_count": point_count,
            "dimensions": 3,
            "categories": ["类别A", "类别B", "类别C", "类别D"]
        } 