#!/usr/bin/env python
import requests
import time
import json
import matplotlib.pyplot as plt
import numpy as np
import psutil
import threading
import argparse
from datetime import datetime
import os
import sys

class PerformanceTest:
    """系统性能测试工具"""
    
    def __init__(self, base_url="http://localhost:8000", max_tasks=100, step=10, 
                 wait_time=10, output_dir="test_results"):
        self.base_url = base_url
        self.max_tasks = max_tasks
        self.step = step
        self.wait_time = wait_time
        self.output_dir = output_dir
        self.results = []
        self.monitoring = False
        self.system_metrics = []
        
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # 测试时间戳（用于文件名）
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def monitor_system(self, interval=1.0):
        """监控系统资源使用情况"""
        self.monitoring = True
        while self.monitoring:
            # 收集CPU、内存、网络使用情况
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            
            # 查找Celery进程
            celery_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = " ".join(proc.info['cmdline'] or [])
                    if 'celery' in cmdline and 'worker' in cmdline:
                        celery_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 计算Celery进程的资源使用
            celery_cpu = sum([p.cpu_percent(interval=0.1) for p in celery_processes]) if celery_processes else 0
            celery_memory = sum([p.memory_info().rss for p in celery_processes]) if celery_processes else 0
            
            # 记录指标
            self.system_metrics.append({
                'timestamp': time.time(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'celery_cpu': celery_cpu,
                'celery_memory': celery_memory / (1024 * 1024)  # MB
            })
            
            time.sleep(interval)
    
    def check_api_compatibility(self):
        """检查API兼容性"""
        print("检查API兼容性...")
        
        try:
            # 测试任务列表API
            response = requests.get(f"{self.base_url}/tasks")
            tasks_data = response.json()
            print(f"任务列表API返回类型: {type(tasks_data)}")
            if isinstance(tasks_data, dict):
                print(f"任务列表API返回键: {list(tasks_data.keys())}")
            elif isinstance(tasks_data, list):
                if tasks_data:
                    print(f"任务列表API返回第一项类型: {type(tasks_data[0])}")
                    if isinstance(tasks_data[0], dict):
                        print(f"任务项键: {list(tasks_data[0].keys())}")
            
            # 测试Worker状态API
            response = requests.get(f"{self.base_url}/worker-status")
            worker_data = response.json()
            print(f"Worker状态API返回类型: {type(worker_data)}")
            if isinstance(worker_data, dict):
                print(f"Worker状态API返回键: {list(worker_data.keys())}")
            
            print("API兼容性检查完成")
            return True
        except Exception as e:
            print(f"API兼容性检查失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_test(self):
        """运行性能测试"""
        print(f"开始性能测试，最大任务数: {self.max_tasks}，步长: {self.step}")
        
        # 检查API兼容性
        if not self.check_api_compatibility():
            print("API兼容性检查失败，测试中止")
            return
        
        # 启动系统监控线程
        monitor_thread = threading.Thread(target=self.monitor_system)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        try:
            # 逐步增加并发任务数
            for num_tasks in range(self.step, self.max_tasks + 1, self.step):
                print(f"\n测试 {num_tasks} 个并发任务...")
                
                # 清除之前的任务
                self.clear_tasks()
                time.sleep(2)  # 等待系统清理
                
                # 记录开始时间
                start_time = time.time()
                
                # 创建并发任务
                try:
                    response = requests.post(f"{self.base_url}/tasks/concurrent/{num_tasks}")
                    response.raise_for_status()
                    task_data = response.json()
                    task_ids = task_data.get("task_ids", [])
                    
                    if not task_ids:
                        print(f"错误: 未能创建任务")
                        continue
                        
                    print(f"已创建 {len(task_ids)} 个任务")
                except Exception as e:
                    print(f"创建任务失败: {e}")
                    # 如果创建任务失败，可能已经达到系统极限
                    break
                
                # 等待所有任务完成或超时
                completed = self.wait_for_tasks(task_ids)
                end_time = time.time()
                
                # 计算统计数据
                duration = end_time - start_time
                success_rate = len(completed) / len(task_ids) if task_ids else 0
                
                # 获取任务详细信息
                task_details = self.get_task_details(task_ids)
                
                # 获取Worker状态
                worker_stats = self.get_worker_stats()
                
                # 记录结果
                result = {
                    'num_tasks': num_tasks,
                    'duration': duration,
                    'success_rate': success_rate,
                    'completed_tasks': len(completed),
                    'task_details': task_details,
                    'worker_stats': worker_stats
                }
                self.results.append(result)
                
                print(f"测试结果: {num_tasks} 个任务, 耗时 {duration:.2f} 秒, 成功率 {success_rate*100:.1f}%")
                
                # 如果成功率低于80%，可能已经达到系统极限
                if success_rate < 0.8:
                    print(f"警告: 成功率低于80%，可能已达到系统极限")
                    if num_tasks > self.step:  # 如果不是第一次测试
                        print(f"建议的最大并发任务数: {num_tasks - self.step}")
                        break
                
                # 等待系统恢复
                print(f"等待系统恢复 {self.wait_time} 秒...")
                time.sleep(self.wait_time)
        
        finally:
            # 停止监控
            self.monitoring = False
            monitor_thread.join(timeout=2)
            
            # 保存结果
            self.save_results()
            
            # 生成报告
            self.generate_report()
    
    def wait_for_tasks(self, task_ids, timeout=60):
        """等待任务完成或超时"""
        print(f"等待 {len(task_ids)} 个任务完成...")
        completed = set()
        start_time = time.time()
        
        while time.time() - start_time < timeout and len(completed) < len(task_ids):
            try:
                # 获取所有任务状态
                response = requests.get(f"{self.base_url}/tasks")
                tasks = response.json()
                
                # 检查API返回的格式
                if not isinstance(tasks, list):
                    print(f"警告: API返回的任务格式不是列表: {type(tasks)}")
                    # 尝试适应不同的API返回格式
                    if isinstance(tasks, dict) and 'tasks' in tasks:
                        tasks = tasks['tasks']
                    else:
                        print(f"无法解析任务数据: {tasks}")
                        time.sleep(1)
                        continue
                
                # 检查每个任务
                for task in tasks:
                    # 确保task是字典类型
                    if not isinstance(task, dict):
                        print(f"警告: 任务不是字典类型: {type(task)}")
                        continue
                        
                    # 安全地获取任务ID和状态
                    task_id = task.get('id')
                    task_status = task.get('status')
                    
                    if task_id in task_ids and task_status in ['SUCCESS', 'FAILURE'] and task_id not in completed:
                        completed.add(task_id)
                
                # 显示进度
                print(f"已完成: {len(completed)}/{len(task_ids)}", end='\r')
                
                # 如果所有任务都完成了，就退出
                if len(completed) == len(task_ids):
                    break
                    
                time.sleep(1)
            except Exception as e:
                print(f"检查任务状态时出错: {e}")
                # 打印更详细的错误信息
                import traceback
                traceback.print_exc()
                time.sleep(1)
        
        print(f"\n{len(completed)}/{len(task_ids)} 个任务在 {time.time() - start_time:.1f} 秒内完成")
        print(f"任务数据示例: {tasks[:1] if tasks else 'empty'}")
        return completed
    
    def get_task_details(self, task_ids):
        """获取任务详细信息"""
        try:
            response = requests.get(f"{self.base_url}/tasks")
            all_tasks = response.json()
            
            # 检查API返回的格式
            if not isinstance(all_tasks, list):
                if isinstance(all_tasks, dict) and 'tasks' in all_tasks:
                    all_tasks = all_tasks['tasks']
                else:
                    print(f"无法解析任务数据: {all_tasks}")
                    return []
            
            # 过滤出我们关心的任务
            result = []
            for task in all_tasks:
                if isinstance(task, dict) and task.get('id') in task_ids:
                    result.append(task)
            return result
        except Exception as e:
            print(f"获取任务详情失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_worker_stats(self):
        """获取Worker状态"""
        try:
            response = requests.get(f"{self.base_url}/worker-status")
            return response.json()
        except Exception as e:
            print(f"获取Worker状态失败: {e}")
            return {"workers": []}
    
    def clear_tasks(self):
        """清除所有任务"""
        try:
            response = requests.post(f"{self.base_url}/tasks/clear")
            print(response.json().get("message", "已清除所有任务"))
            return True
        except Exception as e:
            print(f"清除任务失败: {e}")
            return False
    
    def save_results(self):
        """保存测试结果"""
        # 保存详细结果
        results_file = os.path.join(self.output_dir, f"performance_test_{self.timestamp}.json")
        with open(results_file, 'w') as f:
            json.dump({
                'results': self.results,
                'system_metrics': self.system_metrics
            }, f, indent=2)
        
        print(f"详细结果已保存到: {results_file}")
    
    def generate_report(self):
        """生成测试报告"""
        if not self.results:
            print("没有测试结果可供分析")
            return
        
        # 提取数据
        num_tasks = [r['num_tasks'] for r in self.results]
        durations = [r['duration'] for r in self.results]
        success_rates = [r['success_rate'] * 100 for r in self.results]
        
        # 计算每个任务的平均处理时间
        avg_task_times = [d / n if n > 0 else 0 for d, n in zip(durations, num_tasks)]
        
        # 创建图表
        plt.figure(figsize=(15, 10))
        
        # 1. 总执行时间
        plt.subplot(2, 2, 1)
        plt.plot(num_tasks, durations, 'o-', color='blue')
        plt.title('总执行时间')
        plt.xlabel('并发任务数')
        plt.ylabel('时间 (秒)')
        plt.grid(True)
        
        # 2. 成功率
        plt.subplot(2, 2, 2)
        plt.plot(num_tasks, success_rates, 'o-', color='green')
        plt.title('任务成功率')
        plt.xlabel('并发任务数')
        plt.ylabel('成功率 (%)')
        plt.ylim(0, 105)
        plt.grid(True)
        
        # 3. 平均任务处理时间
        plt.subplot(2, 2, 3)
        plt.plot(num_tasks, avg_task_times, 'o-', color='red')
        plt.title('平均任务处理时间')
        plt.xlabel('并发任务数')
        plt.ylabel('时间 (秒/任务)')
        plt.grid(True)
        
        # 4. 系统资源使用
        if self.system_metrics:
            plt.subplot(2, 2, 4)
            
            # 提取时间轴（相对于开始时间）
            start_time = self.system_metrics[0]['timestamp']
            times = [(m['timestamp'] - start_time) for m in self.system_metrics]
            
            # 提取CPU和内存使用率
            cpu_usage = [m['cpu_percent'] for m in self.system_metrics]
            memory_usage = [m['memory_percent'] for m in self.system_metrics]
            
            # 绘制CPU和内存使用率
            plt.plot(times, cpu_usage, 'b-', label='CPU使用率 (%)')
            plt.plot(times, memory_usage, 'r-', label='内存使用率 (%)')
            plt.title('系统资源使用')
            plt.xlabel('时间 (秒)')
            plt.ylabel('使用率 (%)')
            plt.legend()
            plt.grid(True)
        
        # 保存图表
        plt.tight_layout()
        chart_file = os.path.join(self.output_dir, f"performance_chart_{self.timestamp}.png")
        plt.savefig(chart_file)
        print(f"性能图表已保存到: {chart_file}")
        
        # 生成文本报告
        report_file = os.path.join(self.output_dir, f"performance_report_{self.timestamp}.txt")
        with open(report_file, 'w') as f:
            f.write("=== 性能测试报告 ===\n\n")
            f.write(f"测试时间: {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"最大任务数: {self.max_tasks}\n")
            f.write(f"步长: {self.step}\n\n")
            
            f.write("测试结果:\n")
            for r in self.results:
                f.write(f"- {r['num_tasks']} 个任务: 耗时 {r['duration']:.2f} 秒, 成功率 {r['success_rate']*100:.1f}%, "
                        f"平均每任务 {r['duration']/r['num_tasks']:.2f} 秒\n")
            
            # 找出最佳并发数
            best_throughput = 0
            best_concurrency = 0
            for r in self.results:
                if r['success_rate'] >= 0.95:  # 至少95%成功率
                    throughput = r['num_tasks'] / r['duration']
                    if throughput > best_throughput:
                        best_throughput = throughput
                        best_concurrency = r['num_tasks']
            
            if best_concurrency > 0:
                f.write(f"\n推荐的最佳并发任务数: {best_concurrency} (吞吐量: {best_throughput:.2f} 任务/秒)\n")
            else:
                f.write("\n无法确定最佳并发任务数，所有测试的成功率都低于95%\n")
            
            # 系统瓶颈分析
            if self.system_metrics:
                max_cpu = max([m['cpu_percent'] for m in self.system_metrics])
                max_memory = max([m['memory_percent'] for m in self.system_metrics])
                max_celery_cpu = max([m['celery_cpu'] for m in self.system_metrics])
                max_celery_memory = max([m['celery_memory'] for m in self.system_metrics])
                
                f.write("\n系统资源使用峰值:\n")
                f.write(f"- CPU使用率: {max_cpu:.1f}%\n")
                f.write(f"- 内存使用率: {max_memory:.1f}%\n")
                f.write(f"- Celery CPU使用: {max_celery_cpu:.1f}%\n")
                f.write(f"- Celery内存使用: {max_celery_memory:.1f} MB\n")
                
                # 瓶颈分析
                f.write("\n可能的系统瓶颈:\n")
                if max_cpu > 80:
                    f.write("- CPU资源不足，考虑增加CPU核心或优化任务处理逻辑\n")
                if max_memory > 80:
                    f.write("- 内存资源不足，考虑增加系统内存\n")
                if max_celery_cpu > 80:
                    f.write("- Celery进程CPU使用率高，考虑优化任务处理逻辑\n")
                if max_celery_memory > 1000:  # 1GB
                    f.write("- Celery进程内存使用率高，检查是否存在内存泄漏\n")
        
        print(f"性能报告已保存到: {report_file}")

def main():
    parser = argparse.ArgumentParser(description='系统性能测试工具')
    parser.add_argument('--url', default='http://localhost:8000', help='API基础URL')
    parser.add_argument('--max', type=int, default=100, help='最大并发任务数')
    parser.add_argument('--step', type=int, default=10, help='每次增加的任务数')
    parser.add_argument('--wait', type=int, default=10, help='每次测试后等待时间(秒)')
    parser.add_argument('--output', default='test_results', help='输出目录')
    
    args = parser.parse_args()
    
    tester = PerformanceTest(
        base_url=args.url,
        max_tasks=args.max,
        step=args.step,
        wait_time=args.wait,
        output_dir=args.output
    )
    
    tester.run_test()

if __name__ == "__main__":
    main() 