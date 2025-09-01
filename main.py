#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理应用主入口文件
自动启动GUI界面

支持跨平台运行 (Windows 和 macOS)
"""

import sys
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """主函数 - 启动GUI界面"""
    try:
        # 检查PyQt5
        from PyQt5.QtWidgets import QApplication
        
        # 导入视频处理GUI
        from video_app_gui import VideoProcessorApp
        from log_manager import init_logging
        
        # 初始化日志系统
        log_manager = init_logging()
        
        # 创建应用程序
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        # 设置应用程序信息
        app.setApplicationName("视频处理工具")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("VideoApp")
        
        # 创建并显示主窗口
        window = VideoProcessorApp()
        window.show()
        
        print("🎉 视频处理应用已启动！")
        print("📝 所有日志会自动保存到 logs/ 目录")
        print("🔧 使用指南请查看 README.md 文件")
        print("🖥️  支持在 Windows 和 macOS 上运行")
        
        # 运行应用程序
        sys.exit(app.exec_())
        
    except ImportError as e:
        print("❌ 缺少必要的依赖库!")
        print(f"错误详情: {e}")
        print("\n📦 请安装以下依赖:")
        print("pip install PyQt5 pillow pandas")
        print("\n或者运行:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()