# VideoApp 视频处理工具

## 项目概述
VideoApp是一个功能强大的视频处理应用程序，支持在Windows和macOS平台上运行。该应用集成了视频处理、字幕添加、背景图片、背景音乐等多种功能。

## 功能特性
- 🎬 视频处理和格式转换
- 📝 自动添加字幕（支持多语言）
- 🖼️ 添加背景图片和水印
- 🎵 添加背景音乐
- 🎨 多种字幕样式和效果
- 📊 批量处理多个视频文件
- 🌐 跨平台支持（Windows和macOS）
- 🗣️ 智能配音功能（支持Microsoft Edge TTS）
- 🎵 音频分析和处理（使用librosa库）

## 系统要求
- Python 3.7或更高版本
- 支持的操作系统：Windows 10/11, macOS 10.15或更高版本
- FFmpeg和FFprobe（用于视频处理）

## 安装指南

### 1. 克隆或下载项目
```bash
git clone <repository-url>
# 或者下载ZIP文件并解压
```

### 2. 创建虚拟环境（推荐）
```bash
cd VideoApp
python3 -m venv new_venv
source new_venv/bin/activate  # macOS/Linux
# 或者在Windows上: new_venv\Scripts\activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 安装FFmpeg（如果尚未安装）
#### macOS:
```bash
brew install ffmpeg
```

#### Windows:
从 https://ffmpeg.org/download.html 下载并安装FFmpeg

### 5. 安装额外依赖（可选，用于音频分析功能）
某些高级音频分析功能需要额外的依赖项：
```bash
pip install librosa
```

## 使用方法

### 启动应用
- **在macOS/Linux上**：
  ```bash
  ./start_gui.sh
  ```
  
- **在Windows上**：
  ```cmd
  start_gui.bat
  ```

- **直接运行**：
  ```bash
  python main.py
  ```

### 基本操作流程
1. 选择要处理的视频文件
2. 配置字幕、背景、音乐等参数
3. 在"智能配音设置"中配置TTS参数（可选）
4. 点击"开始处理"按钮
5. 查看输出目录中的处理结果

### 智能配音功能
VideoApp支持使用Microsoft Edge TTS（文本转语音）技术为视频添加配音：
1. 在"智能配音设置"区域选择"OpenAI-Edge-TTS"作为API平台
2. 选择合适的语言和音色
3. 在"TTS文本"框中输入要转换为语音的文本内容
4. 调整TTS音量滑块控制配音音量
5. 处理视频时将自动生成配音并添加到视频中

## 项目结构
```
VideoApp/
├── main.py                 # 应用程序入口
├── video_app_gui.py        # GUI界面实现
├── video/                  # 视频处理模块目录
│   ├── __init__.py         # 模块初始化文件
│   ├── video.py            # 视频处理主协调模块
│   ├── video_background.py # 背景和图像处理模块
│   ├── video_audio.py      # 音频处理模块
│   ├── video_subtitle_processor.py   # 字幕处理模块（重构后的版本）
│   └── video_preprocessing.py # 视频预处理模块
├── utils.py                # 工具函数
├── log_manager.py          # 日志管理
├── backup_manager.py       # 备份管理
├── requirements.txt        # 依赖列表
├── start_gui.sh            # macOS启动脚本
├── start_gui.bat           # Windows启动脚本
├── README.md               # 项目说明文档
├── FINAL_FIX_REPORT.md     # 最终修复报告
├── FINAL_SUMMARY_REPORT.md # 最终总结报告
├── CODE_OPTIMIZATION_REPORT.md # 代码优化报告
├── FINAL_OPTIMIZATION_REPORT.md # 最终优化报告
├── code_checker.py         # 代码检查工具
├── config/                 # 配置文件目录
├── data/                   # 数据目录
├── logs/                   # 日志目录
├── output/                 # 输出目录
└── video/                  # 视频文件目录
```

## 配置文件说明

### 字幕样式配置 (config/subtitle_styles.ini)
定义了不同的字幕样式，包括字体、颜色、大小等参数。

### 字幕内容配置 (data/config/subtitle.csv)
定义了视频文件名与字幕内容的映射关系。

## 故障排除

### 常见问题
1. **缺少依赖库**：
   确保已正确安装所有依赖：`pip install -r requirements.txt`

2. **FFmpeg未找到**：
   确保FFmpeg已正确安装并添加到系统PATH中

3. **权限问题**：
   在macOS上可能需要授予应用程序访问文件的权限

### 日志查看
所有操作日志都保存在`logs/`目录中，可以查看日志文件来诊断问题。

## 开发指南

### 代码质量
- 项目遵循PEP 8编码规范
- 使用了代码检查工具确保代码质量
- 所有关键错误都已修复

### 跨平台兼容性
- 使用pathlib.Path处理文件路径
- 在Windows上特殊处理FFmpeg命令执行
- 正确处理不同操作系统的字体目录

## 贡献
欢迎提交Issue和Pull Request来改进项目。

## 许可证
本项目仅供学习和研究使用。

## 联系方式
如有问题，请联系项目维护者。