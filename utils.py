#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块 - 提供基础工具函数支持
包含文件操作、路径处理、配置加载等功能
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import time
import ast
import pandas as pd


# 路径相关函数
def get_app_path():
    """
    获取应用程序根目录的绝对路径
    支持直接运行和打包成App后运行
    """
    if getattr(sys, 'frozen', False):
        # 如果应用被打包
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller
            return Path(getattr(sys, '_MEIPASS'))
        else:
            # py2app或其他
            return Path(sys.executable).parent
    else:
        # 普通Python脚本
        return Path(__file__).parent


def get_data_path(sub_dir=""):
    """
    获取数据目录路径
    
    参数:
        sub_dir: 子目录，如 "input/videos"
    
    返回:
        data目录下指定子目录的路径
    """
    data_path = get_app_path() / "data"
    
    # 如果sub_dir为空，确保data目录存在
    if not sub_dir:
        os.makedirs(data_path, exist_ok=True)
        return data_path
    
    # 分离路径和可能的文件名
    parts = Path(sub_dir).parts
    if '.' in parts[-1]:  # 最后一部分包含点，可能是文件
        dir_path = data_path.joinpath(*parts[:-1])  # 目录部分
        full_path = data_path / sub_dir  # 完整路径（包括可能的文件）
        
        # 只确保目录存在
        os.makedirs(dir_path, exist_ok=True)
        return full_path
    else:
        # 是纯目录路径
        full_path = data_path / sub_dir
        os.makedirs(full_path, exist_ok=True)
        return full_path


# 配置文件处理
def load_subtitle_config():
    """
    加载字幕配置文件(subtitle_utf-8.csv)
    
    返回:
        pandas.DataFrame: 包含name、title、style等列的DataFrame
    """
    config_path = get_data_path("config") / "subtitle_utf-8.csv"
    
    if not config_path.exists():
        # 如果配置文件不存在，尝试加载subtitle.csv
        old_config_path = get_data_path("config") / "subtitle.csv"
        if old_config_path.exists():
            try:
                # 尝试读取旧配置文件
                df = pd.read_csv(old_config_path, encoding="utf-8")
                # 保存为新文件名
                df.to_csv(config_path, index=False, encoding="utf-8")
                print(f"已将旧配置文件转换为新格式: {config_path}")
                return df
            except Exception as e:
                print(f"读取旧配置文件失败: {e}")
        
        # 如果旧配置文件也不存在，创建一个空的
        # 创建一个新的示例配置文件，明确区分静态字幕和动态字幕列
        sample_data = {
            "name": ["video1", "video2", "video3"],
            "style": ["style1", "style2", "style3"],
            "zn": ["特价促销\n现在下单立即享受优惠", "限时优惠\n错过不再有", "品质保证\n售后无忧"],
            "malay_title": ["Grab cepat\nStok laris seperti roti canai", "Promosi masa terhad\nJangan lepaskan peluang ini", "Jaminan kualiti\nPerkhidmatan selepas jualan"],
            "title_thai": ["ราคาพิเศษ\nซื้อเลยอย่ารอช้า", "โปรโมชั่นพิเศษ\nของแถมมากมาย", "รับประกันคุณภาพ\nบริการหลังการขาย"],
            "cn_prompt": ["特价促销\n现在下单立即เข้าร่วม", "限时优惠\n错过不再有", "品质保证\n售后无忧"],
            "malay_prompt": ["Grab cepat\nStok laris seperti roti canai", "Promosi masa terhad\nJangan lepaskan peluang ini", "Jaminan kualiti\nPerkhidmatan selepas jualan"],
            "thai_prompt": ["ราคาพิเศษ\nซื้อเลยอย่ารอช้า", "โปรโมชั่นพิเศษ\nของแถมมากมาย", "รับประกันคุณภาพ\nบริการหลังการขาย"]
        }
        df = pd.DataFrame(sample_data)
        df.to_csv(config_path, index=False, encoding="utf-8")
        print(f"创建了新的示例配置文件: {config_path}")
        return df
    
    try:
        # 尝试读取配置文件，确保使用UTF-8编码
        df = pd.read_csv(config_path, encoding="utf-8")
        print(f"成功加载配置: {config_path}")
        
        # 确保所有必要的列都存在
        required_columns = ["name", "style", "zn", "malay_title", "title_thai", "cn_prompt", "malay_prompt", "thai_prompt"]
        for col in required_columns:
            if col not in df.columns:
                if col in ["zn", "malay_title", "title_thai"]:
                    # 静态字幕列
                    df[col] = ""
                elif col in ["cn_prompt", "malay_prompt", "thai_prompt"]:
                    # 动态字幕列
                    df[col] = ""
                else:
                    df[col] = ""
        
        # 确保向后兼容性，如果缺少title列则添加
        if "title" not in df.columns:
            df["title"] = df["zn"]  # 默认使用中文静态字幕作为title
                
        return df
    except UnicodeDecodeError:
        # 如果UTF-8解码失败，尝试其他编码
        try:
            df = pd.read_csv(config_path, encoding="ISO-8859-1")
            # 将数据转换为UTF-8
            df.to_csv(config_path, index=False, encoding="utf-8")
            print(f"配置文件已从其他编码转换为UTF-8: {config_path}")
            return df
        except Exception as e:
            print(f"读取配置文件失败(尝试其他编码): {e}")
            return pd.DataFrame(columns=pd.Index(["name", "title", "title_thai", "style"]))
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        # 返回一个空的DataFrame
        return pd.DataFrame(columns=pd.Index(["name", "title", "title_thai", "style"]))


def load_style_config(style=None):
    """
    加载样式配置文件(subtitle_styles.ini)
    
    参数:
        style: 样式名称，如果提供则返回特定样式的配置，否则返回整个配置对象
        
    返回:
        如果提供了style，返回该样式的配置字典；否则返回整个ConfigParser对象
    """
    import configparser
    
    # 尝试不同位置查找配置文件
    config_paths = [
        get_data_path("config") / "subtitle_styles.ini",
        Path("VideoApp/config") / "subtitle_styles.ini",
        Path("config") / "subtitle_styles.ini",
        Path(os.getcwd()) / "config" / "subtitle_styles.ini"
    ]
    
    config = configparser.ConfigParser()
    
    # 尝试读取配置文件
    config_found = False
    for config_path in config_paths:
        if config_path.exists():
            try:
                config.read(str(config_path), encoding='utf-8')
                print(f"成功加载样式配置: {config_path}")
                config_found = True
                break
            except Exception as e:
                print(f"读取样式配置文件 {config_path} 失败: {e}")
    
    if not config_found:
        print("未找到样式配置文件，将使用默认样式")
        return {} if style else config
    
    # 如果提供了style参数，返回该样式的配置
    if style:
        style_section = f"styles.{style}"
        if config.has_section(style_section):
            # 将配置项转换为字典
            style_dict = {}
            for key, value in config.items(style_section):
                # 尝试解析列表类型的值
                if key in ['text_color', 'stroke_color', 'shadow_color', 'shadow_offset']:
                    try:
                        style_dict[key] = ast.literal_eval(value)
                    except:
                        style_dict[key] = value
                # 尝试解析数值类型的值
                elif key in ['font_size', 'stroke_width', 'white_stroke_ratio']:
                    try:
                        if '.' in value:
                            style_dict[key] = float(value)
                        else:
                            style_dict[key] = int(value)
                    except:
                        style_dict[key] = value
                # 尝试解析布尔类型的值
                elif key == 'shadow':
                    style_dict[key] = value.lower() in ['true', 'yes', '1']
                else:
                    style_dict[key] = value
            
            return style_dict
        else:
            print(f"样式 {style} 在配置文件中不存在，将使用默认样式")
            return {}
    
    return config


# 文件操作
def find_matching_image(video_name, image_dir="input/images", custom_image_path=None):
    """
    查找与视频名称匹配的图片
    
    参数:
        video_name: 视频文件名（不含扩展名）
        image_dir: 图片目录
        custom_image_path: 自定义图片路径（可选）
        
    返回:
        匹配的图片路径，如果没找到则返回None
    """
    try:
        print(f"查找匹配图片: 视频名={video_name}, 图片目录={image_dir}")
        
        # 如果提供了自定义图片路径，直接使用
        if custom_image_path and Path(custom_image_path).exists():
            print(f"使用自定义图片路径: {custom_image_path}")
            full_image_dir = custom_image_path
        else:
            # 尝试不同的图片目录路径
            videoapp_dir_path = Path.cwd() / "VideoApp/input/images"
            current_dir_path = Path.cwd() / "input/images"
            
            if videoapp_dir_path.exists():
                full_image_dir = str(videoapp_dir_path)
                print(f"使用VideoApp图片目录: {full_image_dir}")
            elif current_dir_path.exists():
                full_image_dir = str(current_dir_path)
                print(f"使用当前目录图片目录: {full_image_dir}")
            else:
                # 尝试data/image目录（实际图片存放位置）
                data_image_dir = get_data_path("image")
                if Path(data_image_dir).exists():
                    full_image_dir = str(data_image_dir)
                    print(f"使用data/image目录: {full_image_dir}")
                else:
                    full_image_dir = get_data_path("input/images")
                    print(f"使用默认图片目录: {full_image_dir}")
        
        print(f"最终图片目录路径: {full_image_dir}")
            
        if not Path(full_image_dir).exists():
            try:
                Path(full_image_dir).mkdir(parents=True, exist_ok=True)
                print(f"已创建图片目录: {full_image_dir}")
            except Exception as e:
                print(f"创建图片目录失败: {e}")
                return None
        
        # 列出目录中所有文件
        all_files = [f.name for f in Path(full_image_dir).iterdir() if f.is_file()]
        print(f"目录中的文件数量: {len(all_files)}")
        print(f"目录中的所有文件: {all_files}")
            
        # 支持的图片扩展名
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        
        # 查找完全匹配的图片
        for ext in image_extensions:
            image_path = Path(full_image_dir) / f"{video_name}{ext}"
            if image_path.exists():
                print(f"找到完全匹配的图片: {image_path}")
                return str(image_path)
        
        # 如果没有完全匹配，查找包含视频名称的图片
        matched_images = []
        for file in all_files:
            file_path = Path(full_image_dir) / file
            if file_path.is_file() and any(file.lower().endswith(ext.lower()) for ext in image_extensions):
                print(f"检查文件: {file}")
                # 提取视频名称的关键部分（例如M2-romer_003）
                video_key = video_name.split('_')[0] if '_' in video_name else video_name
                if video_key.lower() in file.lower():
                    print(f"  - 匹配成功: {file} (关键词: {video_key})")
                    matched_images.append((str(file_path), len(file)))
                else:
                    print(f"  - 不匹配: {file}")
        
        # 按文件名长度排序，选择最短的（通常是最接近的匹配）
        if matched_images:
            matched_images.sort(key=lambda x: x[1])
            best_match = matched_images[0][0]
            print(f"找到最佳匹配的图片: {best_match}")
            return best_match
        
        # 如果没有匹配，返回目录中的第一张图片（如果有）
        for file in all_files:
            file_path = Path(full_image_dir) / file
            if file_path.is_file() and any(file.lower().endswith(ext.lower()) for ext in image_extensions):
                print(f"没有匹配，使用目录中的第一张图片: {file_path}")
                return str(file_path)
                    
        print(f"未找到与 {video_name} 匹配的图片，也没有找到任何可用图片")
        return None
    except Exception as e:
        print(f"查找匹配图片时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def find_matching_file(base_name, directory, extensions=[".jpg", ".png", ".jpeg"]):
    """
    在指定目录中查找与base_name匹配的文件
    
    参数:
        base_name: 文件名基础部分(不含扩展名)
        directory: 要搜索的目录
        extensions: 要匹配的文件扩展名列表
    
    返回:
        找到的文件路径，如果没找到则返回None
    """
    directory_path = Path(directory)
    if not directory_path.exists():
        return None
    
    # 首先尝试完全匹配
    for ext in extensions:
        file_path = directory_path / f"{base_name}{ext}"
        if file_path.exists():
            return file_path
    
    # 如果没有完全匹配，尝试部分匹配
    for file in directory_path.iterdir():
        if file.is_file():
            file_base = file.stem.lower()
            if base_name.lower() in file_base or file_base in base_name.lower():
                if file.suffix.lower() in [ext.lower() for ext in extensions]:
                    return file
    
    return None


# FFMPEG命令执行
def run_ffmpeg_command(command, quiet=False):
    """
    执行FFMPEG命令
    
    参数:
        command: 命令列表，如 ["ffmpeg", "-i", "input.mp4", "output.mp4"]
        quiet: 是否静默执行
    
    返回:
        成功返回True，失败返回False
    """
    import logging
    import platform
    
    if not quiet:
        print(f"执行命令: {' '.join(command)}")
        logging.info(f"🎥 执行FFmpeg命令: {' '.join(command[:10])}...")
    
    try:
        # 在Windows上，可能需要处理编码问题
        if platform.system() == "Windows":
            # Windows上使用creationflags来避免控制台窗口闪烁
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # 在其他系统上正常执行
            result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            if not quiet:
                logging.info(f"✅ FFmpeg命令执行成功")
            return True
        else:
            # 记录错误信息
            error_msg = result.stderr.strip() if result.stderr else "未知错误"
            print(f"❌ FFmpeg命令执行失败 (返回码: {result.returncode})")
            print(f"错误信息: {error_msg}")
            
            logging.error(f"❌ FFmpeg命令执行失败")
            logging.error(f"  返回码: {result.returncode}")
            logging.error(f"  错误信息: {error_msg}")
            
            # 分析常见错误
            if "No such file" in error_msg:
                logging.error(f"  ⚙️ 可能的原因: 输入文件不存在")
                print(f"  ⚙️ 可能的原因: 输入文件不存在")
            elif "Invalid data" in error_msg:
                logging.error(f"  ⚙️ 可能的原因: 文件格式错误或损坏")
                print(f"  ⚙️ 可能的原因: 文件格式错误或损坏")
            elif "filter" in error_msg.lower():
                logging.error(f"  ⚙️ 可能的原因: 过滤器语法错误")
                print(f"  ⚙️ 可能的原因: 过滤器语法错误")
            elif "Permission denied" in error_msg:
                logging.error(f"  ⚙️ 可能的原因: 文件权限问题")
                print(f"  ⚙️ 可能的原因: 文件权限问题")
            
            return False
            
    except Exception as e:
        error_msg = str(e)
        print(f"执行命令异常: {error_msg}")
        logging.error(f"❌ 执行命令异常: {error_msg}")
        return False


def get_audio_duration(audio_path):
    """
    获取音频时长
    
    参数:
        audio_path: 音频文件路径
    
    返回:
        float: 音频时长（秒），失败返回None
    """
    try:
        # 获取音频时长
        duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
        ]
        duration_str = subprocess.check_output(duration_cmd).decode("utf-8").strip()
        
        # 确保获取到有效的时长值
        try:
            duration = float(duration_str)
            if duration <= 0:
                print(f"警告: 检测到无效的音频时长 ({duration}秒)")
                return None
            return duration
        except ValueError:
            print(f"无法解析音频时长字符串: '{duration_str}'")
            return None
            
    except Exception as e:
        print(f"获取音频时长失败: {e}")
        return None


def get_video_info(video_path):
    """
    获取视频信息(宽度、高度、时长)
    
    参数:
        video_path: 视频文件路径
    
    返回:
        (width, height, duration) 元组，失败返回None
    """
    try:
        # 获取视频尺寸
        size_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
            str(video_path)
        ]
        video_size = subprocess.check_output(size_cmd).decode("utf-8").strip()
        width, height = map(int, video_size.split("x"))
        
        # 获取视频时长
        duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        duration_str = subprocess.check_output(duration_cmd).decode("utf-8").strip()
        
        # 确保获取到有效的时长值
        try:
            duration = float(duration_str)
            if duration <= 0.1:  # 如果时长异常短，尝试使用另一种方法
                print(f"警告: 检测到异常短的视频时长 ({duration}秒)，尝试使用另一种方法获取...")
                # 使用另一种方法获取时长
                alt_duration_cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                    str(video_path)
                ]
                alt_duration_str = subprocess.check_output(alt_duration_cmd).decode("utf-8").strip()
                if alt_duration_str and float(alt_duration_str) > 0.1:
                    duration = float(alt_duration_str)
                    print(f"使用流时长: {duration}秒")
                else:
                    # 如果流时长也不可用，使用帧数和帧率计算
                    frame_cmd = [
                        "ffprobe", "-v", "error", "-count_frames",
                        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
                    ]
                    fps_cmd = [
                        "ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1",
                        str(video_path)
                    ]
                    
                    try:
                        frames = int(subprocess.check_output(frame_cmd).decode("utf-8").strip())
                        fps_str = subprocess.check_output(fps_cmd).decode("utf-8").strip()
                        fps_parts = fps_str.split('/')
                        if len(fps_parts) == 2:
                            fps = float(fps_parts[0]) / float(fps_parts[1])
                        else:
                            fps = float(fps_str)
                        
                        if frames > 0 and fps > 0:
                            duration = frames / fps
                            print(f"使用帧数计算时长: {frames}帧 / {fps}fps = {duration}秒")
                    except Exception as e:
                        print(f"帧数计算失败: {e}")
                        # 使用默认值
                        duration = 10.0
                        print(f"无法获取准确时长，使用默认值: {duration}秒")
        except ValueError:
            print(f"无法解析时长字符串: '{duration_str}'")
            duration = 10.0  # 使用默认值
            
        print(f"视频信息: {width}x{height}, {duration}秒")
        return width, height, duration
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        # 返回默认值
        return 1080, 1920, 10.0  # 默认值


def ensure_dir(directory):
    """确保目录存在，不存在则创建"""
    os.makedirs(directory, exist_ok=True)


def find_font_file(font_path):
    """
    查找字体文件
    
    参数:
        font_path: 字体路径，可以是相对路径或绝对路径
        
    返回:
        找到的字体文件路径，如果没找到则返回None
    """
    # 如果是绝对路径且文件存在，直接返回
    font_path_obj = Path(font_path)
    if font_path_obj.is_absolute() and font_path_obj.exists():
        return font_path
    
    # 尝试不同的基础路径
    possible_paths = [
        font_path_obj,  # 原始路径
        get_app_path() / font_path,  # 相对于应用程序路径
        Path.cwd() / font_path,  # 相对于当前工作目录
        Path(get_data_path()) / font_path,  # 相对于数据目录
        get_app_path() / "VideoApp" / font_path,  # VideoApp子目录
        Path.cwd() / "VideoApp" / font_path,  # 当前目录下的VideoApp子目录
        Path(__file__).parent.parent / font_path,  # 相对于utils.py的上级目录
        Path(__file__).parent / font_path,  # 相对于utils.py目录
    ]
    
    # 检查可能的路径
    for path in possible_paths:
        if path.exists():
            print(f"找到字体文件: {path}")
            return str(path)
    
    # 如果指定的字体文件找不到，尝试在fonts目录中查找任何可用的字体
    fonts_dirs = [
        Path(get_data_path()) / "fonts",
        Path(get_data_path()) / "fonts/new",  # 新增字体目录
        get_app_path() / "data/fonts",
        get_app_path() / "data/fonts/new",  # 新增字体目录
        Path.cwd() / "data/fonts",
        Path.cwd() / "data/fonts/new",  # 新增字体目录
        Path.cwd() / "VideoApp/data/fonts",
        Path.cwd() / "VideoApp/data/fonts/new",  # 新增字体目录
    ]
    
    # 获取字体文件名（不含路径）
    font_filename = font_path_obj.name
    
    # 在fonts目录中查找匹配的字体
    for fonts_dir in fonts_dirs:
        if fonts_dir.exists():
            print(f"检查字体目录: {fonts_dir}")
            # 首先尝试精确匹配
            exact_match = fonts_dir / font_filename
            if exact_match.exists():
                print(f"找到精确匹配的字体文件: {exact_match}")
                return str(exact_match)
                
            # 如果没有精确匹配，尝试查找任何可用的字体
            try:
                font_files = [f.name for f in fonts_dir.iterdir() if f.is_file() and f.suffix.lower() in ('.ttf', '.otf')]
                if font_files:
                    # 优先选择名称中包含Bold的字体
                    bold_fonts = [f for f in font_files if 'bold' in f.lower()]
                    if bold_fonts:
                        selected_font = fonts_dir / bold_fonts[0]
                        print(f"找不到指定字体，使用粗体字体: {selected_font}")
                        return str(selected_font)
                    
                    # 如果没有粗体字体，使用任何可用字体
                    selected_font = fonts_dir / font_files[0]
                    print(f"找不到指定字体，使用可用字体: {selected_font}")
                    return str(selected_font)
            except Exception as e:
                print(f"在字体目录中查找字体时出错: {e}")
    
    # 尝试系统字体目录
    system_font_dirs = []
    
    # macOS 系统字体目录
    if sys.platform == 'darwin':
        system_font_dirs.extend([
            Path('/System/Library/Fonts'),
            Path('/Library/Fonts'),
            Path.home() / 'Library/Fonts'
        ])
    
    # Windows 系统字体目录
    elif sys.platform == 'win32':
        windir = Path(os.environ.get('WINDIR', 'C:\\Windows'))
        fonts_dir = windir / 'Fonts'
        if fonts_dir.exists():
            system_font_dirs.extend([fonts_dir])
        else:
            # 备用Windows字体目录
            system_font_dirs.extend([
                Path('C:\\Windows\\Fonts'),
            ])
    
    # Linux 系统字体目录
    else:
        system_font_dirs.extend([
            Path('/usr/share/fonts'),
            Path('/usr/local/share/fonts'),
            Path.home() / '.fonts'
        ])
    
    # 常见字体名称
    common_fonts = [
        'Arial.ttf', 
        'Helvetica.ttf', 
        'DejaVuSans.ttf', 
        'FreeSans.ttf',
        'NotoSans-Regular.ttf',
        'OpenSans-Regular.ttf',
        'LiberationSans-Regular.ttf',
        'Times.ttf',
        'TimesNewRoman.ttf',
        'Georgia.ttf',
        'Verdana.ttf',
        'Tahoma.ttf',
        'Calibri.ttf',
        'SFPro.ttf',
        'SFProText-Regular.ttf',
        'SFProDisplay-Regular.ttf',
        'PingFang.ttc',
        'PingFangSC-Regular.ttf',
        'STHeiti-Light.ttc',
        'STHeiti-Regular.ttc',
        'Menlo-Regular.ttf',
        'Monaco.ttf',
        'Consolas.ttf',
        'CourierNew.ttf'
    ]
    
    # 在系统字体目录中查找常见字体
    for font_dir in system_font_dirs:
        if font_dir.exists():
            print(f"检查系统字体目录: {font_dir}")
            for font_name in common_fonts:
                font_path = font_dir / font_name
                if font_path.exists():
                    print(f"找到系统字体: {font_path}")
                    
                    # 尝试复制字体到应用程序字体目录
                    try:
                        app_fonts_dir = Path(get_data_path()) / "fonts"
                        ensure_dir(str(app_fonts_dir))
                        dest_path = app_fonts_dir / font_name
                        if not dest_path.exists():
                            import shutil
                            shutil.copy2(str(font_path), str(dest_path))
                            print(f"已将系统字体复制到应用程序目录: {dest_path}")
                        return str(dest_path)
                    except Exception as e:
                        print(f"复制字体失败: {e}")
                        return str(font_path)
            
            # 如果没有找到常见字体，尝试列出目录中的所有字体文件
            try:
                all_files = [f for f in font_dir.iterdir() if f.is_file()]
                font_files = [f for f in all_files if f.suffix.lower() in ('.ttf', '.otf', '.ttc')]
                if font_files:
                    font_path = font_files[0]
                    print(f"使用系统中找到的第一个字体: {font_path}")
                    
                    # 尝试复制字体到应用程序字体目录
                    try:
                        app_fonts_dir = Path(get_data_path()) / "fonts"
                        ensure_dir(str(app_fonts_dir))
                        dest_path = app_fonts_dir / font_path.name
                        if not dest_path.exists():
                            import shutil
                            shutil.copy2(str(font_path), str(dest_path))
                            print(f"已将系统字体复制到应用程序目录: {dest_path}")
                        return str(dest_path)
                    except Exception as e:
                        print(f"复制字体失败: {e}")
                        return str(font_path)
            except Exception as e:
                print(f"列出系统字体目录时出错: {e}")
    
    print(f"找不到字体文件: {font_path}")
    return None


# TTS相关函数
async def generate_tts_audio(text, voice, output_file):
    """
    使用Edge-TTS生成音频文件
    
    参数:
        text: 要转换为语音的文本
        voice: 语音名称（如zh-CN-XiaoxiaoNeural）
        output_file: 输出音频文件路径
        
    返回:
        bool: 是否成功生成音频
    """
    try:
        import edge_tts
        
        # 使用Edge-TTS生成音频
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        print(f"TTS音频已生成: {output_file}")
        return True
    except Exception as e:
        print(f"生成TTS音频失败: {e}")
        return False


def get_edge_tts_voices():
    """
    获取Edge-TTS支持的语音列表
    
    返回:
        list: 语音信息列表
    """
    try:
        import edge_tts
        import asyncio
        
        async def _get_voices():
            return await edge_tts.list_voices()
        
        voices = asyncio.run(_get_voices())
        return voices
    except Exception as e:
        print(f"获取TTS语音列表失败: {e}")
        return []


def get_voices_by_language(voices, language_code):
    """
    根据语言代码筛选语音
    
    参数:
        voices: 语音列表
        language_code: 语言代码（如zh-CN）
        
    返回:
        list: 指定语言的语音列表
    """
    try:
        filtered_voices = [voice for voice in voices if voice["Locale"].startswith(language_code)]
        return filtered_voices
    except Exception as e:
        print(f"筛选语音列表失败: {e}")
        return []


# TTS相关函数
# 注意：create_subtitle_image函数现在统一在video_core.py中定义
