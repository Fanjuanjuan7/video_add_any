#!/bin/bash
# 视频处理应用GUI启动脚本
# 解决macOS上Qt平台插件问题的完整启动脚本

echo "正在启动视频处理应用GUI..."

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 切换到应用目录
cd "$SCRIPT_DIR"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "警告: 虚拟环境不存在，将直接使用系统Python环境"
fi

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查PyQt5是否安装
if ! python3 -c "import PyQt5" 2>/dev/null; then
    echo "错误: PyQt5未安装，请运行 pip install PyQt5"
    exit 1
fi

# 设置Qt插件路径 - 解决macOS上cocoa插件找不到的问题
export QT_QPA_PLATFORM_PLUGIN_PATH="$(python3 -c "import PyQt5; import os; print(os.path.join(PyQt5.__path__[0], 'Qt5', 'plugins'))")"

# 验证插件路径是否存在
if [ ! -d "$QT_QPA_PLATFORM_PLUGIN_PATH" ]; then
    echo "警告: Qt插件路径不存在: $QT_QPA_PLATFORM_PLUGIN_PATH"
    echo "尝试查找插件路径..."
    
    # 尝试查找插件路径
    PLUGIN_PATH=$(find "$(python3 -c "import PyQt5; print(PyQt5.__path__[0])")" -name "libqcocoa.dylib" -type f 2>/dev/null | head -1 | xargs dirname 2>/dev/null)
    
    if [ -n "$PLUGIN_PATH" ]; then
        export QT_QPA_PLATFORM_PLUGIN_PATH="$(dirname "$PLUGIN_PATH")"
        echo "找到插件路径: $QT_QPA_PLATFORM_PLUGIN_PATH"
    else
        echo "错误: 无法找到Qt插件路径"
        exit 1
    fi
fi

echo "Qt插件路径: $QT_QPA_PLATFORM_PLUGIN_PATH"
echo "启动GUI界面..."

# 启动应用程序
python3 main.py

echo "应用程序已退出"