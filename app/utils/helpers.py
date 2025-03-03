"""
工具函数模块
提供各种辅助函数
"""
import time
import functools
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

T = TypeVar('T')

def retry(max_retries: int = 3, delay: float = 1.0, 
          backoff: float = 2.0, exceptions: tuple = (Exception,)) -> Callable:
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避系数
        exceptions: 需要重试的异常类型
        
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retry_count = 0
            current_delay = delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        raise
                    
                    # 等待一段时间后重试
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        return wrapper
    
    return decorator


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """
    将嵌套字典扁平化
    
    Args:
        d: 要扁平化的字典
        parent_key: 父键
        sep: 键分隔符
        
    Returns:
        Dict[str, Any]: 扁平化后的字典
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def safe_get(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    安全地从嵌套字典中获取值
    
    Args:
        data: 数据字典
        path: 键路径，使用.分隔
        default: 默认值
        
    Returns:
        Any: 获取的值或默认值
    """
    keys = path.split('.')
    result = data
    
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    
    return result


def group_by(items: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    按键对字典列表进行分组
    
    Args:
        items: 字典列表
        key: 分组键
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: 分组结果
    """
    result = {}
    
    for item in items:
        key_value = safe_get(item, key)
        if key_value is None:
            continue
            
        key_str = str(key_value)
        if key_str not in result:
            result[key_str] = []
            
        result[key_str].append(item)
    
    return result


def format_time_delta(seconds: float) -> str:
    """
    格式化时间差
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化后的时间差
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}毫秒"
    elif seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时" 