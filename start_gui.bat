@echo off
REM 视频处理应用GUI启动脚本 (Windows版本)
REM 解决Windows上Qt平台插件问题的完整启动脚本

echo 正在启动视频处理应用GUI...

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0

REM 切换到应用目录
cd /d "%SCRIPT_DIR%"

REM 检查虚拟环境是否存在
if not exist "venv" (
    echo 错误: 虚拟环境不存在，请先运行 python -m venv venv 创建虚拟环境
    pause
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查PyQt5是否安装
python -c "import PyQt5" 2>nul
if errorlevel 1 (
    echo 错误: PyQt5未安装，请运行 pip install PyQt5
    pause
    exit /b 1
)

REM 设置Qt插件路径 - 解决Windows上平台插件找不到的问题
for /f "delims=" %%i in ('python -c "import PyQt5; import os; print(os.path.join(PyQt5.__path__[0], 'Qt5', 'plugins'))"') do set QT_QPA_PLATFORM_PLUGIN_PATH=%%i

REM 验证插件路径是否存在
if not exist "%QT_QPA_PLATFORM_PLUGIN_PATH%" (
    echo 警告: Qt插件路径不存在: %QT_QPA_PLATFORM_PLUGIN_PATH%
    echo 尝试查找插件路径...
    
    REM 尝试查找插件路径
    for /f "delims=" %%i in ('python -c "import PyQt5; import os; plugin_path = os.path.join(PyQt5.__path__[0], 'Qt', 'plugins'); print(plugin_path) if os.path.exists(plugin_path) else ''" 2^>nul') do set QT_QPA_PLATFORM_PLUGIN_PATH=%%i
    
    if not defined QT_QPA_PLATFORM_PLUGIN_PATH (
        echo 错误: 无法找到Qt插件路径
        pause
        exit /b 1
    )
)

echo Qt插件路径: %QT_QPA_PLATFORM_PLUGIN_PATH%
echo 启动GUI界面...

REM 启动应用程序
python video_app_gui.py

echo 应用程序已退出
pause