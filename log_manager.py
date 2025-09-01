#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理脚本
自动捕获和保存程序运行日志，只保留最近5次日志
"""

import os
import sys
import logging
import datetime
from pathlib import Path
import contextlib

class LogManager:
    """日志管理器"""
    
    def __init__(self, log_dir="logs", max_logs=5):
        """
        初始化日志管理器
        
        参数:
            log_dir: 日志目录
            max_logs: 最大保留日志数量
        """
        self.log_dir = Path(log_dir)
        self.max_logs = max_logs
        self.log_dir.mkdir(exist_ok=True)
        
        # 生成日志文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"video_processing_{timestamp}.log"
        
        # 设置日志格式
        self.setup_logging()
        
        # 清理旧日志
        self.cleanup_old_logs()
    
    def setup_logging(self):
        """设置日志配置"""
        # 创建日志格式
        log_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        
        # 获取根日志器
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        logger.handlers.clear()
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        print(f"📝 日志将保存到: {self.log_file}")
    
    def cleanup_old_logs(self):
        """清理旧日志文件，只保留最近的日志"""
        try:
            # 获取所有日志文件
            log_files = list(self.log_dir.glob("video_processing_*.log"))
            
            if len(log_files) <= self.max_logs:
                return
            
            # 按修改时间排序（最新的在前）
            log_files.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
            
            # 删除多余的日志文件
            files_to_delete = log_files[self.max_logs:]
            
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    print(f"🗑️  删除旧日志: {file_path.name}")
                except Exception as e:
                    print(f"❌ 删除日志失败: {e}")
            
            print(f"📋 保留最近 {self.max_logs} 个日志文件")
            
        except Exception as e:
            print(f"❌ 清理日志时出错: {e}")
    
    def log_system_info(self):
        """记录系统信息"""
        import platform
        import subprocess
        
        logging.info("="*60)
        logging.info("🖥️  系统信息")
        logging.info(f"操作系统: {platform.system()} {platform.release()}")
        logging.info(f"Python版本: {platform.python_version()}")
        logging.info(f"工作目录: {os.getcwd()}")
        
        # 检查FFmpeg版本
        try:
            # 在Windows上，可能需要处理编码问题
            import platform as platform_module
            if platform_module.system() == "Windows":
                # Windows上使用creationflags来避免控制台窗口闪烁
                result = subprocess.run(['ffmpeg', '-version'], 
                                      capture_output=True, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # 在其他系统上正常执行
                result = subprocess.run(['ffmpeg', '-version'], 
                                      capture_output=True, text=True)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                logging.info(f"FFmpeg版本: {version_line}")
            else:
                logging.warning("⚠️  FFmpeg未正确安装")
        except Exception as e:
            logging.warning(f"⚠️  检查FFmpeg失败: {e}")
        
        logging.info("="*60)
    
    def get_log_files(self):
        """获取所有日志文件列表"""
        log_files = list(self.log_dir.glob("video_processing_*.log"))
        # 按修改时间排序（最新的在前）
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return log_files
    
    def read_latest_log(self):
        """读取最新的日志内容"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"❌ 读取日志失败: {e}")
            return ""
    
    @contextlib.contextmanager
    def capture_output(self):
        """上下文管理器，用于捕获print输出到日志"""
        import io
        
        # 创建字符串缓冲区
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        # 保存原始的stdout和stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            # 创建组合输出流
            class TeeOutput:
                def __init__(self, original, buffer, logger_func):
                    self.original = original
                    self.buffer = buffer
                    self.logger_func = logger_func
                
                def write(self, text):
                    self.original.write(text)
                    self.buffer.write(text)
                    # 如果不是空行，记录到日志
                    if text.strip():
                        self.logger_func(text.rstrip())
                
                def flush(self):
                    self.original.flush()
                    self.buffer.flush()
            
            # 替换stdout和stderr
            sys.stdout = TeeOutput(original_stdout, stdout_buffer, logging.info)
            sys.stderr = TeeOutput(original_stderr, stderr_buffer, logging.error)
            
            yield
            
        finally:
            # 恢复原始输出流
            sys.stdout = original_stdout
            sys.stderr = original_stderr

# 全局日志管理器实例
_log_manager = None

def init_logging(log_dir="logs", max_logs=5):
    """初始化日志系统"""
    global _log_manager
    _log_manager = LogManager(log_dir, max_logs)
    _log_manager.log_system_info()
    return _log_manager

def get_log_manager():
    """获取日志管理器实例"""
    global _log_manager
    if _log_manager is None:
        _log_manager = init_logging()
    return _log_manager

def log_with_capture(func):
    """装饰器：自动捕获函数执行过程的日志"""
    def wrapper(*args, **kwargs):
        log_manager = get_log_manager()
        
        logging.info(f"🚀 开始执行: {func.__name__}")
        logging.info(f"📥 参数: args={args}, kwargs={kwargs}")
        
        try:
            with log_manager.capture_output():
                result = func(*args, **kwargs)
            
            logging.info(f"✅ 执行完成: {func.__name__}")
            logging.info(f"📤 返回结果: {result}")
            return result
            
        except Exception as e:
            logging.error(f"❌ 执行失败: {func.__name__}")
            logging.error(f"💥 错误信息: {str(e)}")
            import traceback
            logging.error(f"📋 错误堆栈:\n{traceback.format_exc()}")
            raise
        
    return wrapper

def main():
    """测试日志系统"""
    print("🧪 测试日志管理系统...")
    
    # 初始化日志
    log_manager = init_logging()
    
    # 测试日志输出
    logging.info("这是一条信息日志")
    logging.warning("这是一条警告日志")
    logging.error("这是一条错误日志")
    
    print("🔍 测试print输出捕获")
    print("这是print输出，应该被捕获到日志中")
    
    # 显示日志文件信息
    log_files = log_manager.get_log_files()
    print(f"\n📋 当前日志文件:")
    for i, log_file in enumerate(log_files, 1):
        size = log_file.stat().st_size
        mtime = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
        print(f"  {i}. {log_file.name} ({size} 字节, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    print(f"\n✅ 日志系统测试完成！")
    print(f"📁 日志目录: {log_manager.log_dir}")
    print(f"📝 当前日志: {log_manager.log_file}")

if __name__ == "__main__":
    main()