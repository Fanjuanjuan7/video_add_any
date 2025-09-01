#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频核心处理模块
负责视频处理的主要逻辑，包括视频长度判断、放大裁剪、添加字幕等功能
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path
import tempfile
import random
import pandas as pd
from PIL import Image, ImageDraw, ImageOps, ImageFont
import time
import logging

# 导入工具函数
from utils import get_video_info, run_ffmpeg_command, get_data_path, find_matching_file, ensure_dir, load_subtitle_config, load_style_config, find_font_file

# 导入日志管理器
from log_manager import init_logging, get_log_manager, log_with_capture

# 初始化日志系统
log_manager = init_logging()


def create_rounded_rect_background(width, height, radius, output_path, bg_color=(0, 0, 0, 128), sample_frame=None):
    """
    创建圆角矩形透明背景
    
    参数:
        width: 背景宽度
        height: 背景高度
        radius: 圆角半径
        output_path: 输出路径
        bg_color: 背景颜色和透明度，默认为半透明黑色
        sample_frame: 视频帧样本，用于取色
        
    返回:
        背景图片路径
    """
    try:
        # 如果提供了视频帧，从中取色
        if sample_frame is not None:
            try:
                # 从视频中间位置取色
                frame_width, frame_height = sample_frame.size
                # 取视频中心点的颜色
                sample_color = sample_frame.getpixel((frame_width // 2, frame_height // 2))
                
                # 如果是RGB图像，添加透明度
                if len(sample_color) == 3:
                    bg_color = (sample_color[0], sample_color[1], sample_color[2], 128)  # 半透明
                else:
                    # 已经是RGBA，只修改透明度
                    bg_color = (sample_color[0], sample_color[1], sample_color[2], 128)
                    
                # 检测是否为黑色或接近黑色
                is_dark = all(c < 30 for c in sample_color[:3])  # RGB值都小于30认为是黑色
                if is_dark:
                    print(f"检测到视频中心是黑色或接近黑色: {sample_color}，使用白色作为背景")
                    bg_color = (255, 255, 255, 128)  # 半透明白色
                
                print(f"从视频中取色: {sample_color}，最终背景色: {bg_color}")
            except Exception as e:
                print(f"从视频取色失败，使用默认颜色: {e}")
                
        # 创建透明背景
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 绘制圆角矩形
        draw.rounded_rectangle([(0, 0), (width-1, height-1)], radius=radius, fill=bg_color)
        
        # 保存图片
        image.save(output_path)
        print(f"圆角矩形背景已保存: {output_path}")
        return output_path
    except Exception as e:
        print(f"创建圆角矩形背景失败: {e}")
        return None


@log_with_capture
def process_video(video_path, output_path=None, style=None, subtitle_lang=None, 
                 quicktime_compatible=False, img_position_x=100, img_position_y=0,
                 font_size=70, subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                 subtitle_text_x=0, subtitle_text_y=1190, random_position=False, enable_subtitle=True,
                 enable_background=True, enable_image=True, enable_music=False, music_path="",
                 music_mode="single", music_volume=50, document_path=None, enable_gif=False, 
                 gif_path="", gif_loop_count=-1, gif_scale=1.0, gif_x=800, gif_y=100, scale_factor=1.1, 
                 image_path=None, subtitle_width=800, quality_settings=None):
    """
    处理视频的主函数
    
    参数:
        video_path: 视频文件路径
        output_path: 输出文件路径，默认为None（自动生成）
        style: 字幕样式，如果为None则随机选择
        subtitle_lang: 字幕语言，如果为None则随机选择
        quicktime_compatible: 是否生成QuickTime兼容的视频
        img_position_x: 图片水平位置系数（视频宽度的百分比，默认0.15，即15%）
        img_position_y: 图片垂直位置偏移（相对于背景位置，默认120像素向下偏移）
        font_size: 字体大小（像素，默认70）
        subtitle_x: 字幕X轴位置（像素，默认43）
        subtitle_y: 字幕Y轴位置（像素，默认1248）
        bg_width: 背景宽度（像素，默认1000）
        bg_height: 背景高度（像素，默认180）
        img_size: 图片大小（像素，默认420）
        
    返回:
        处理后的视频路径，失败返回None
    """
    print(f"开始处理视频: {video_path}")
    print(f"图片位置设置: 水平={img_position_x}（宽度比例）, 垂直={img_position_y}（像素偏移）")
    
    # 如果未指定输出路径，则生成一个
    if not output_path:
        video_name = Path(video_path).stem
        # 使用相对路径的output目录
        output_dir = Path("output")
        # 确保输出路径的目录存在
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{video_name}_processed.mp4"

    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())
    print(f"使用临时目录: {temp_dir}")
    
    try:
        # 1. 获取视频信息
        video_info = get_video_info(video_path)
        if not video_info:
            print("无法获取视频信息，处理失败")
            return None
            
        width, height, duration = video_info
        print(f"视频信息: {width}x{height}, {duration}秒")
        
        # 所有视频都使用相同方法进行水印处理
        print(f"视频 ({duration}秒): 进行水印处理，缩放系数: {scale_factor}")
        processed_path = process_normal_video(video_path, temp_dir, scale_factor)
        
        # 如果是短视频，需要进行正放+倒放处理
        if duration < 9.0 and processed_path:
            print(f"短视频: 将进行正放+倒放处理")
            # 将已处理过水印的视频进行正放+倒放处理
            reversed_path = temp_dir / "forward_reverse.mp4"
            if process_short_video(processed_path, reversed_path):
                processed_path = reversed_path
            
        if not processed_path:
            print("视频预处理失败")
            return None
            
        # 3. 添加字幕和其他效果，传递所有参数
        final_path = add_subtitle_to_video(
            processed_path, 
            output_path, 
            style, 
            subtitle_lang, 
            video_path, 
            quicktime_compatible=quicktime_compatible,
            img_position_x=img_position_x,
            img_position_y=img_position_y,
            font_size=font_size,
            subtitle_x=subtitle_x,
            subtitle_y=subtitle_y,
            bg_width=bg_width,
            bg_height=bg_height,
            img_size=img_size,
            subtitle_text_x=subtitle_text_x,
            subtitle_text_y=subtitle_text_y,
            random_position=random_position,
            enable_subtitle=enable_subtitle,
            enable_background=enable_background,
            enable_image=enable_image,
            enable_music=enable_music,
            music_path=music_path,
            music_mode=music_mode,
            music_volume=music_volume,
            document_path=document_path,
            enable_gif=enable_gif,
            gif_path=gif_path,
            gif_loop_count=gif_loop_count,
            gif_scale=gif_scale,
            gif_x=gif_x,
            gif_y=gif_y,
            scale_factor=scale_factor,
            image_path=image_path,
            subtitle_width=subtitle_width,
            quality_settings=quality_settings
        )
        
        if not final_path:
            print("添加字幕失败")
            return None
            
        print(f"视频处理完成: {final_path}")
        return final_path
        
    except Exception as e:
        print(f"处理视频时出错: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass


def process_short_video(video_path, temp_dir):
    """
    处理短视频（5秒以下），进行正放+倒放拼接
    
    参数:
        video_path: 输入视频路径
        temp_dir: 临时目录
        
    返回:
        处理后的视频路径
    """
    output_path = temp_dir / "forward_reverse.mp4"
    
    # 使用一条命令完成正放+倒放+拼接
    cmd = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-filter_complex',
        f'[0:v]trim=duration=5,setpts=PTS-STARTPTS[forward];'
        f'[0:v]trim=duration=5,setpts=PTS-STARTPTS,reverse[reversed];'
        f'[forward][reversed]concat=n=2:v=1:a=0[v]',
        '-map', '[v]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-crf', "23",  
        '-b:v', "4M",       
        '-movflags', '+faststart',
        '-brand', 'mp42',  # 设置兼容的品牌标记
        '-tag:v', 'avc1',  # 使用标准AVC标记
        '-an',  # 不要音频
        str(output_path)
    ]
    
    if run_ffmpeg_command(cmd):
        return output_path
    
    # 如果上面的命令失败，尝试传统方法
    print("使用备用方法处理短视频")
    
    # 1. 提取前5秒
    forward_path = temp_dir / "forward.mp4"
    cmd_forward = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-t', '5',  # 截取前5秒
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast', 
        '-brand', 'mp42',  # 设置兼容的品牌标记
        '-tag:v', 'avc1',  # 使用标准AVC标记
        '-an',  # 不要音频
        str(forward_path)
    ]
    if not run_ffmpeg_command(cmd_forward):
        return None
        
    # 2. 创建倒放视频
    reverse_path = temp_dir / "reverse.mp4"
    cmd_reverse = [
        'ffmpeg', '-y', '-i', str(forward_path),
        '-vf', 'reverse',  # 倒放滤镜
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-brand', 'mp42',  # 设置兼容的品牌标记
        '-tag:v', 'avc1',  # 使用标准AVC标记
        '-an',  # 不要音频
        str(reverse_path)
    ]
    if not run_ffmpeg_command(cmd_reverse):
        return None
        
    # 3. 拼接视频
    concat_file = temp_dir / "concat.txt"
    with open(concat_file, 'w') as f:
        f.write(f"file '{forward_path}'\n")
        f.write(f"file '{reverse_path}'\n")
    
    cmd_concat = [
        'ffmpeg', '-y', 
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_file),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-brand', 'mp42',  # 设置兼容的品牌标记
        '-tag:v', 'avc1',  # 使用标准AVC标记
        '-an',  # 不要音频
        str(output_path)
    ]
    
    if run_ffmpeg_command(cmd_concat):
        return output_path
    
    return None


def process_normal_video(video_path, temp_dir, scale_factor=1.1):
    """
    处理普通长度视频（无需正倒放）
    
    参数:
        video_path: 输入视频路径
        temp_dir: 临时目录
        scale_factor: 缩放系数，用于去水印（默认1.1）
        
    返回:
        处理后的视频路径
    """
    # 获取视频信息
    video_info = get_video_info(video_path)
    if not video_info:
        return None
        
    width, height, duration = video_info
    
    # 创建转换后的临时文件
    resized_path = temp_dir / "resized.mp4"
    
    # 目标尺寸
    target_width = 1080
    target_height = 1920
    
    print(f"【去水印】原始视频尺寸: {width}x{height}")
    print(f"【去水印】缩放系数: {scale_factor}")
    
    # 新的去水印逻辑：先铺满画布，再缩放裁剪
    # 1. 计算铺满画布的缩放比例
    scale_to_fit_width = target_width / width
    scale_to_fit_height = target_height / height
    scale_to_fit = max(scale_to_fit_width, scale_to_fit_height)  # 使用较大值确保完全铺满
    
    # 2. 在铺满的基础上再应用用户设置的缩放系数
    final_scale = scale_to_fit * scale_factor
    
    # 3. 计算缩放后的尺寸
    scaled_width = int(width * final_scale)
    scaled_height = int(height * final_scale)
    
    # 确保为偶数
    scaled_width = scaled_width - (scaled_width % 2)
    scaled_height = scaled_height - (scaled_height % 2)
    
    # 4. 计算裁剪位置（居中裁剪）
    crop_x = max(0, (scaled_width - target_width) // 2)
    crop_y = max(0, (scaled_height - target_height) // 2)
    
    print(f"【去水印】铺满缩放比例: {scale_to_fit:.3f}")
    print(f"【去水印】最终缩放比例: {final_scale:.3f}")
    print(f"【去水印】缩放后尺寸: {scaled_width}x{scaled_height}")
    print(f"【去水印】裁剪位置: ({crop_x}, {crop_y})")
    print(f"【去水印】裁剪尺寸: {target_width}x{target_height}")
    
    # 5. 构建FFmpeg命令
    resize_cmd = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-vf', f'scale={scaled_width}:{scaled_height},crop={target_width}:{target_height}:{crop_x}:{crop_y}',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-brand', 'mp42',
        '-tag:v', 'avc1',
        '-an',  # 不要音频
        str(resized_path)
    ]
    
    print(f"【去水印】执行命令: {' '.join(resize_cmd)}")
    if not run_ffmpeg_command(resize_cmd):
        print("去水印处理失败，使用原始视频")
        return video_path
    
    print(f"【去水印】处理成功: {resized_path}")
    return resized_path


@log_with_capture
def add_subtitle_to_video(video_path, output_path, style=None, subtitle_lang=None, 
                        original_video_path=None, quicktime_compatible=False, 
                        img_position_x=100, img_position_y=0, font_size=70, 
                        subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                        subtitle_text_x=0, subtitle_text_y=1190, random_position=False, enable_subtitle=True,
                        enable_background=True, enable_image=True, enable_music=False, music_path="",
                        music_mode="single", music_volume=50, document_path=None, enable_gif=False, 
                        gif_path="", gif_loop_count=-1, gif_scale=1.0, gif_x=800, gif_y=100, scale_factor=1.1, 
                        image_path=None, subtitle_width=800, quality_settings=None):
    """
    添加字幕到视频
    
    参数:
        video_path: 输入视频路径
        output_path: 输出视频路径
        style: 字幕样式，如果为None则随机选择
        subtitle_lang: 字幕语言，如果为None则随机选择
        original_video_path: 原始视频路径（用于查找匹配的图片）
        quicktime_compatible: 是否生成QuickTime兼容的视频
        img_position_x: 图片水平位置系数（视频宽度的百分比，默认0.15，即15%）
        img_position_y: 图片垂直位置偏移（相对于背景位置，默认120像素向下偏移）
        font_size: 字体大小（像素，默认70）
        subtitle_x: 字幕X轴位置（像素，默认43）
        subtitle_y: 字幕Y轴位置（像素，默认1248）
        bg_width: 背景宽度（像素，默认1000）
        bg_height: 背景高度（像素，默认180）
        img_size: 图片大小（像素，默认420）
        enable_music: 是否启用背景音乐
        music_path: 音乐文件或文件夹路径
        music_mode: 音乐匹配模式（single/order/random）
        music_volume: 音量百分比（0-100）
        document_path: 用户选择的文档文件路径，如果为None则使用默认的subtitle.csv
        
    返回:
        处理后的视频路径
    """
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())
    print(f"使用临时目录: {temp_dir}")
    
    try:
        # 1. 获取视频信息
        video_info = get_video_info(video_path)
        if not video_info:
            print("无法获取视频信息")
            return None
            
        width, height, duration = video_info
        print(f"视频信息: {width}x{height}, {duration}秒")
        
        # 2. 加载字幕配置
        subtitle_df = None
        
        # 优先使用用户选择的文档文件
        if document_path and Path(document_path).exists():
            print(f"使用用户选择的文档文件: {document_path}")

            try:
                file_ext = Path(document_path).suffix.lower()
                if file_ext == '.csv':
                    subtitle_df = pd.read_csv(document_path)
                elif file_ext in ['.xlsx', '.xls']:
                    subtitle_df = pd.read_excel(document_path)
                elif file_ext == '.md':
                    # 简单的Markdown表格解析
                    with open(document_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 尝试解析Markdown表格
                    lines = content.strip().split('\n')
                    # 查找表格开始
                    table_started = False
                    headers = []
                    data_rows = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if '|' in line and not table_started:
                            # 表头行
                            headers = [h.strip() for h in line.split('|') if h.strip()]
                            table_started = True
                        elif '|' in line and table_started and not line.startswith('|---'):
                            # 数据行（跳过分隔符行）
                            if not all(c in '-|: ' for c in line):  # 不是分隔符行
                                row_data = [d.strip() for d in line.split('|') if d.strip() or d.strip() == '']
                                if len(row_data) >= len(headers):  # 确保数据列数够
                                    data_rows.append(row_data[:len(headers)])
                    
                    if headers and data_rows:
                        subtitle_df = pd.DataFrame(data_rows, columns=pd.Index(headers))
                        print(f"成功解析Markdown表格: {len(subtitle_df)} 条记录")
                    else:
                        print("Markdown文件中未找到有效的表格格式")
                elif file_ext == '.txt':
                    # 尝试作为CSV或制表符分隔的文件读取
                    try:
                        subtitle_df = pd.read_csv(document_path, delimiter='\t')  # 先尝试制表符
                    except:
                        subtitle_df = pd.read_csv(document_path)  # 再尝试逗号
                
                if subtitle_df is not None:
                    print(f"成功加载用户文档: {len(subtitle_df)} 条记录")
                    print(f"文档列名: {list(subtitle_df.columns)}")
                else:
                    print("无法解析用户选择的文档文件")
                    
            except Exception as e:
                print(f"加载用户文档失败: {e}")
                subtitle_df = None
        
        # 如果用户文档加载失败或未指定，使用默认配置文件
        if subtitle_df is None:
            subtitle_config_path = get_data_path("config/subtitle.csv")
            if not Path(subtitle_config_path).exists():
                print(f"默认字幕配置文件不存在: {subtitle_config_path}")
                return None
                
            try:
                subtitle_df = pd.read_csv(subtitle_config_path)
                print(f"使用默认字幕配置: {len(subtitle_df)} 条记录")
            except Exception as e:
                print(f"加载默认字幕配置失败: {e}")
                return None
            
        # 3. 随机选择样式和语言（如果未指定或者是"random"）
        if style is None or style == "random":
            # 从配置文件中动态获取所有可用的样式
            style_config = load_style_config()
            available_styles = []
            
            # 检查 load_style_config 返回的类型
            try:
                # 检查返回的对象类型
                if isinstance(style_config, dict):
                    # 如果是字典，说明没有找到配置文件，使用默认样式
                    print("配置文件加载失败，使用默认样式列表")
                    available_styles = []
                elif hasattr(style_config, 'sections') and callable(getattr(style_config, 'sections', None)):
                    # ConfigParser 对象
                    for section in style_config.sections():
                        if section.startswith("styles."):
                            style_name = section.replace("styles.", "")
                            available_styles.append(style_name)
                else:
                    # 其他情况，使用默认样式列表
                    print("配置文件加载失败，使用默认样式列表")
                    available_styles = []
            except Exception as e:
                print(f"处理样式配置时出错: {e}，使用默认样式列表")
                available_styles = []
            
            # 如果没有找到任何样式，使用默认样式列表
            if not available_styles:
                available_styles = ["style1", "style2", "style3", "style4", "style5", "style6", 
                                    "style7", "style8", "style9", "style10", "style11"]
            
            # 如果选择的是中文语言，优先使用中文样式
            if subtitle_lang == "chinese":
                chinese_styles = [s for s in available_styles if 'chinese' in s]
                if chinese_styles:
                    style = random.choice(chinese_styles)
                    print(f"中文语言，优先选择中文样式: {style}")
                else:
                    # 如果没有中文样式，使用常规样式
                    style = random.choice(available_styles)
                    print(f"中文语言但无中文样式，使用常规样式: {style}")
            else:
                # 非中文语言，优先使用非中文样式
                regular_styles = [s for s in available_styles if 'chinese' not in s]
                if regular_styles:
                    style = random.choice(regular_styles)
                    print(f"非中文语言，选择非中文样式: {style}")
                else:
                    # 如果没有非中文样式，使用默认样式
                    style = random.choice(available_styles)
                    print(f"非中文语言但无非中文样式，使用常规样式: {style}")
        
        if subtitle_lang is None:
            available_langs = ["chinese", "malay", "thai"]
            subtitle_lang = random.choice(available_langs)
            print(f"随机选择语言: {subtitle_lang}")
        # 如果是"random"样式，先随机选择一个实际样式
        if style == "random":
            # 从配置文件中动态获取所有可用的样式
            style_config_parser = load_style_config()
            available_styles = []
            
            try:
                # 检查返回的对象类型
                if isinstance(style_config_parser, dict):
                    # 如果是字典，说明没有找到配置文件，使用默认样式
                    print("配置文件加载失败，使用默认样式列表")
                    available_styles = []
                elif hasattr(style_config_parser, 'sections') and callable(getattr(style_config_parser, 'sections', None)):
                    # ConfigParser 对象
                    for section in style_config_parser.sections():
                        if section.startswith("styles."):
                            style_name = section.replace("styles.", "")
                            available_styles.append(style_name)
                else:
                    # 其他情况，使用默认样式列表
                    print("配置文件加载失败，使用默认样式列表")
                    available_styles = []
            except Exception as e:
                print(f"处理样式配置时出错: {e}，使用默认样式列表")
                available_styles = []
            
            # 如果没有找到任何样式，使用默认样式列表
            if not available_styles:
                available_styles = ["style1", "style2", "style3", "style4", "style5", "style6", 
                                    "style7", "style8", "style9", "style10", "style11"]
            
            style = random.choice(available_styles)
            print(f"在create_subtitle_image中随机选择样式: {style} (从 {len(available_styles)} 种样式中选择)")

        # 4. 处理随机位置逻辑
        if random_position:
            # 定义随机区域边界（考虑字幕尺寸）
            # 用户指定的固定字幕区域：左上角(50,200)到右下角(920,1200)
            region_left = 50     # 区域左边界
            region_top = 200     # 区域上边界  
            region_right = 920   # 区域右边界
            region_bottom = 1200 # 区域下边界
            
            # 字幕实际宽度智能估算（用于边界计算）
            if subtitle_width > 700:
                estimated_subtitle_width = 500  # 大字幕使用保守估算
            elif subtitle_width > 500:
                estimated_subtitle_width = 400  # 中等字幕
            else:
                estimated_subtitle_width = subtitle_width * 0.8  # 小字幕使用80%
            
            # 计算字幕位置范围（确保整个字幕完整显示在区域内）
            # X坐标范围：从区域左边界到（区域右边界 - 字幕宽度）
            min_x = region_left
            max_x = region_right - estimated_subtitle_width
            # Y坐标范围：从区域上边界到区域下边界
            min_y = region_top  
            max_y = region_bottom
            
            # 边界合理性检查
            if max_x <= min_x:
                # 如果字幕太宽无法放在指定区域内，使用区域中心策略
                print(f"⚠️ 字幕宽度({estimated_subtitle_width})超出区域宽度({region_right - region_left})，使用中心位置")
                center_x = (region_left + region_right) // 2
                available_range = min(100, (region_right - region_left) // 2)  # 给出一个安全的浮动范围
                min_x = max(region_left, center_x - available_range // 2)
                max_x = min(region_right - 10, center_x + available_range // 2)  # 保留10px边距
                print(f"🎯 使用中心位置策略: X范围[{min_x}, {max_x}]")
                
            if max_y <= min_y:
                # 理论上Y坐标不会有这个问题，但为了安全起见保留检查
                print(f"⚠️ Y坐标范围异常，使用默认值")
                min_y = region_top
                max_y = region_bottom
            
            # 生成随机位置
            new_subtitle_text_x = random.randint(min_x, max_x)
            new_subtitle_text_y = random.randint(min_y, max_y)
            
            print(f"🎲 随机字幕位置: 原始({subtitle_text_x}, {subtitle_text_y}) -> 随机({new_subtitle_text_x}, {new_subtitle_text_y})")
            print(f"📎 边界检查: X范围[{min_x}, {max_x}], Y范围[{min_y}, {max_y}]")
            print(f"📐 字幕区域: 左上角({region_left}, {region_top}) -> 右下角({region_right}, {region_bottom})")
            print(f"📏 字幕宽度: 设定={subtitle_width}, 估算={estimated_subtitle_width}")
            print(f"🖥️ 区域尺寸: {region_right - region_left}x{region_bottom - region_top}, 可用X范围: {max_x - min_x}")
            logging.info(f"🎲 随机字幕位置: 原始({subtitle_text_x}, {subtitle_text_y}) -> 随机({new_subtitle_text_x}, {new_subtitle_text_y})")
            logging.info(f"📎 边界检查: X范围[{min_x}, {max_x}], Y范围[{min_y}, {max_y}]")
            logging.info(f"📐 字幕区域: 左上角({region_left}, {region_top}) -> 右下角({region_right}, {region_bottom})")
            logging.info(f"📏 字幕宽度: 设定={subtitle_width}, 估算={estimated_subtitle_width}")
            logging.info(f"🖥️ 区域尺寸: {region_right - region_left}x{region_bottom - region_top}, 可用X范围: {max_x - min_x}")
            
            # 更新位置参数
            subtitle_text_x = new_subtitle_text_x
            subtitle_text_y = new_subtitle_text_y
        else:
            print(f"📍 使用固定字幕位置: ({subtitle_text_x}, {subtitle_text_y})")
            logging.info(f"📍 使用固定字幕位置: ({subtitle_text_x}, {subtitle_text_y})")
        
        # 5. 查找匹配的图片（仅在启用图片时）
        has_image = False
        matched_image_path = None
        final_image_path = None  # 初始化final_image_path变量
        processed_img_path = None  # 初始化processed_img_path变量
        
        print(f"🎬 【素材状态调试】图片功能启用状态: {enable_image}")
        
        if enable_image:
            print("📁 图片功能已启用，开始查找匹配图片...")
            
            # 使用原始视频路径查找匹配图片（如果有）
            if original_video_path:
                original_video_name = Path(original_video_path).stem
                print(f"📁 使用原始视频名查找图片: {original_video_name}")
                matched_image_path = find_matching_image(original_video_name, custom_image_path=image_path)
                
            # 如果没有找到，使用当前视频路径
            if not matched_image_path:
                video_name = Path(video_path).stem
                print(f"📁 使用当前视频名查找图片: {video_name}")
                matched_image_path = find_matching_image(video_name, custom_image_path=image_path)
                
            # 使用匹配的图片路径
            final_image_path = matched_image_path
            
            if final_image_path:
                print(f"✅ 找到匹配的图片: {final_image_path}")
            else:
                print("⚠️ 没有找到匹配的图片")
        else:
            print("❌ 图片功能已禁用，跳过图片查找")
            
        if final_image_path and enable_image:
            print(f"✅ 找到匹配的图片: {final_image_path}")
            # 6. 处理图片
            print(f"【图片流程】处理图片 {final_image_path}，大小设置为 {img_size}x{img_size}")
            processed_img_path = temp_dir / "processed_image.png"
            processed_img = process_image_for_overlay(
                final_image_path,
                str(processed_img_path),
                size=(img_size, img_size)  # 使用传入的img_size参数
            )
            
            if not processed_img:
                print("❌ 处理图片失败，跳过图片叠加")
                has_image = False
            else:
                print(f"✅ 【图片流程】图片处理成功: {processed_img}")
                has_image = True
        elif enable_image and not final_image_path:
            print("⚠️ 图片功能已启用但没有找到匹配的图片")
            print("📁 尝试使用默认图片...")
            
            # 检查图片目录是否存在
            image_dir = get_data_path("input/images")
            if enable_gif and gif_path and Path(gif_path).exists():
                print(f"GIF文件存在: {gif_path}")
            if enable_image and Path(image_dir).exists():
                print(f"图片目录存在: {image_dir}")
            
            # 尝试从图片目录获取任意图片
            try:
                image_dir = get_data_path("input/images")
                if Path(image_dir).exists():
                    image_files = []
                    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        image_files.extend(list(Path(image_dir).glob(f"*{ext}")))
                        image_files.extend(list(Path(image_dir).glob(f"*{ext.upper()}")))
                    
                    if image_files:
                        default_image = str(image_files[0])
                        print(f"📁 使用默认图片: {default_image}")
                        
                        processed_img_path = temp_dir / "processed_image.png"
                        processed_img = process_image_for_overlay(
                            default_image,
                            str(processed_img_path),
                            size=(img_size, img_size)
                        )
                        
                        if processed_img:
                            print(f"✅ 【图片流程】默认图片处理成功: {processed_img}")
                            has_image = True
                            final_image_path = default_image  # 更新final_image_path
                        else:
                            print("❌ 默认图片处理失败")
                            has_image = False
                    else:
                        print("❌ 图片目录中没有可用图片")
                        has_image = False
                else:
                    print(f"❌ 图片目录不存在: {image_dir}")
                    has_image = False
            except Exception as e:
                print(f"❌ 获取默认图片失败: {e}")
                has_image = False
        else:
            if not enable_image:
                print("图片功能已禁用")
            has_image = False
        
        # 6. 处理GIF（仅在启用GIF时）
        has_gif = False
        processed_gif_path = None
        
        if enable_gif and gif_path and Path(gif_path).exists():
            print(f"【GIF流程】处理GIF {gif_path}，缩放系数: {gif_scale}，位置: ({gif_x}, {gif_y})，循环次数: {gif_loop_count}")
            
            # 检查文件格式
            file_ext = Path(gif_path).suffix.lower()
            if file_ext in ['.gif', '.webp']:
                processed_gif_path = temp_dir / "processed_gif.gif"
                
                # 使用FFmpeg处理GIF，调整大小和循环次数
                gif_filters = []
                
                # 缩放过滤器
                if gif_scale != 1.0:
                    gif_filters.append(f"scale=iw*{gif_scale}:ih*{gif_scale}")
                
                # 构建过滤器字符串
                filter_str = ",".join(gif_filters) if gif_filters else "copy"
                
                # 构建 FFmpeg 命令，保持透明度并设置循环次数
                gif_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(gif_path)
                ]
                
                # 添加过滤器，专门处理带透明背景的GIF
                if gif_filters:
                    # 有缩放过滤器时，使用更强的透明背景处理
                    gif_cmd.extend([
                        '-vf', f'{filter_str},split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128',
                        '-f', 'gif'
                    ])
                else:
                    # 无缩放时，直接使用强化的透明背景处理
                    gif_cmd.extend([
                        '-vf', 'split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128',
                        '-f', 'gif'
                    ])
                
                # 添加循环次数控制
                if gif_loop_count == -1:
                    # -1 表示无限循环，使用 FFmpeg 默认值
                    gif_cmd.extend(['-loop', '0'])  # 0 在 FFmpeg 中表示无限循环
                elif gif_loop_count == 0:
                    # 0 表示不循环，只播放一次
                    gif_cmd.extend(['-loop', '-1'])  # -1 在 FFmpeg 中表示不循环
                else:
                    # 具体的循环次数
                    gif_cmd.extend(['-loop', str(gif_loop_count)])
                
                print(f"【GIF流程】使用强化透明背景处理: palettegen + paletteuse")
                logging.info(f"【GIF流程】使用强化透明背景处理: palettegen + paletteuse")
                
                gif_cmd.append(str(processed_gif_path))
                
                try:
                    print(f"【GIF流程】执行命令: {' '.join(gif_cmd)}")
                    result = subprocess.run(gif_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"【GIF流程】GIF处理成功: {processed_gif_path}")
                    has_gif = True
                except subprocess.CalledProcessError as e:
                    print(f"【GIF流程】GIF处理失败: {e}")
                    print(f"stderr: {e.stderr.decode()}")
                    has_gif = False
            else:
                print(f"【GIF流程】不支持的文件格式: {file_ext}")
        else:
            if not enable_gif:
                print("GIF功能已禁用")
            elif not gif_path:
                print("未指定GIF路径")
            else:
                print(f"GIF文件不存在: {gif_path}")
            
        # 8. 处理字幕（仅在启用字幕时）
        subtitle_text = None
        subtitle_img = None
        
        if enable_subtitle:
            # 检查文档中的可用列
            available_columns = list(subtitle_df.columns)
            
            # 🔍 调试信息：显示语言映射关系
            print(f"\n=== 语言映射调试信息 ===")
            print(f"GUI选择的语言: {subtitle_lang}")
            print(f"用户期望的映射关系:")
            print(f"  中文 (chinese) → zn列")
            print(f"  马来语 (malay) → malay_title列")
            print(f"  泰语 (thai) → title_thai列")
            print(f"当前文档可用列: {available_columns}")
            print(f"=========================\n")
            
            # 根据语言随机选择一条字幕
            subtitle_text = None
            
            print(f"可用的文档列: {available_columns}")
            
            if subtitle_lang == "chinese":
                # 中文：明确指定使用zn列
                chinese_col = 'zn'
                
                if chinese_col in available_columns:
                    available_subtitles = subtitle_df[subtitle_df[chinese_col].notna() & (subtitle_df[chinese_col] != "")][chinese_col].tolist()
                    if available_subtitles:
                        subtitle_text = str(random.choice(available_subtitles))
                        print(f"✅ 中文映射成功：从 '{chinese_col}' 列随机选择字幕: {subtitle_text}")
                    else:
                        print(f"❌ '{chinese_col}' 列中没有有效数据")
                        subtitle_text = "特价促销\n现在下单立即享受优惠"
                        print("使用默认中文字幕")
                else:
                    print(f"❌ 文档中未找到中文列: {chinese_col}")
                    subtitle_text = "特价促销\n现在下单立即享受优惠"
                    print("使用默认中文字幕")
                    
            elif subtitle_lang == "malay":
                # 马来语：明确指定使用malay_title列
                malay_col = 'malay_title'
                
                if malay_col in available_columns:
                    available_subtitles = subtitle_df[subtitle_df[malay_col].notna() & (subtitle_df[malay_col] != "")][malay_col].tolist()
                    if available_subtitles:
                        subtitle_text = str(random.choice(available_subtitles))
                        print(f"✅ 马来语映射成功：从 '{malay_col}' 列随机选择字幕: {subtitle_text}")
                    else:
                        print(f"❌ '{malay_col}' 列中没有有效数据")
                        subtitle_text = "Grab cepat\nStok laris seperti roti canai"
                        print("使用默认马来语字幕")
                else:
                    print(f"❌ 文档中未找到马来语列: {malay_col}")
                    subtitle_text = "Grab cepat\nStok laris seperti roti canai"
                    print("使用默认马来语字幕")
                    
            else:  # thai
                # 泰语：明确指定使用title_thai列
                thai_col = 'title_thai'
                
                if thai_col in available_columns:
                    available_subtitles = subtitle_df[subtitle_df[thai_col].notna() & (subtitle_df[thai_col] != "")][thai_col].tolist()
                    if available_subtitles:
                        subtitle_text = str(random.choice(available_subtitles))
                        # 替换下划线为空格（如果泰文使用下划线占位）
                        if "_" in subtitle_text:
                            subtitle_text = subtitle_text.replace("_", " ")
                        print(f"✅ 泰语映射成功：从 '{thai_col}' 列随机选择字幕: {subtitle_text}")
                    else:
                        print(f"❌ '{thai_col}' 列中没有有效数据")
                        subtitle_text = "ราคาพิเศษ\nซื้อเลยอย่ารอช้า"  # 泰文示例
                        print("使用默认泰语字幕")
                else:
                    print(f"❌ 文档中未找到泰语列: {thai_col}")
                    subtitle_text = "ราคาพิเศษ\nซื้อเลยอย่ารอช้า"  # 泰文示例
                    print("使用默认泰语字幕")
            
            # 创建字幕图片
            subtitle_height = 500  # 字幕高度
            subtitle_img_path = temp_dir / "subtitle.png"
            
            # 调试信息：打印字体大小
            print(f"传递给create_subtitle_image的字体大小: {font_size}")
            
            # 使用传入的字体大小参数，而不是硬编码
            subtitle_img = create_subtitle_image(
                text=subtitle_text,
                style=style,
                width=width + 200,  # 增加字幕宽度，防止文字被截断
                height=subtitle_height,
                font_size=font_size,
                output_path=str(subtitle_img_path),
                subtitle_width=subtitle_width  # 传递字幕宽度参数
            )
            
            # 检查字幕生成结果
            if subtitle_img:
                print(f"字幕图片生成成功，路径: {subtitle_img}")
            else:
                print("警告：字幕图片生成失败")
                return None
        else:
            print("字幕功能已禁用，跳过字幕生成")
        
        # 9. 处理背景（仅在启用背景时）
        sample_frame = None
        bg_img = None
        
        if enable_background:
            # 提取视频帧用于取色
            sample_frame_path = temp_dir / "sample_frame.jpg"
            
            # 从视频中间位置提取帧，确保在视频长度范围内
            middle_time = min(duration / 2, 5.0)  # 取视频中间位置或最多5秒处
            
            sample_frame_cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-ss', str(middle_time),  # 使用秒数格式，而不是时:分:秒格式
                '-vframes', '1',
                '-q:v', '1',
                str(sample_frame_path)
            ]
            
            try:
                print(f"【背景颜色】从视频 {middle_time:.2f} 秒位置提取帧用于取色")
                subprocess.run(sample_frame_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                sample_frame = Image.open(str(sample_frame_path))
                print(f"【背景颜色】成功提取视频帧用于取色: {sample_frame_path}")
            except Exception as e:
                print(f"【背景颜色】提取视频帧失败: {e}")
            
            # 创建圆角矩形透明背景，使用自定义尺寸
            bg_img_path = temp_dir / "background.png"
            bg_radius = 20   # 圆角半径
            
            # 使用视频帧取色创建背景
            print("【背景颜色】开始创建圆角矩形背景，使用视频帧取色")
            if sample_frame:
                # 获取视频中心点的颜色用于调试
                try:
                    frame_width, frame_height = sample_frame.size
                    center_color = sample_frame.getpixel((frame_width // 2, frame_height // 2))
                    print(f"【背景颜色】视频中心点颜色: {center_color}")
                except Exception as e:
                    print(f"【背景颜色】无法获取视频中心点颜色: {e}")
            else:
                print("【背景颜色】没有可用的视频帧，将使用默认颜色")
                
            bg_img = create_rounded_rect_background(
                width=bg_width,
                height=bg_height,
                radius=bg_radius,
                output_path=str(bg_img_path),
                sample_frame=sample_frame  # 传入提取的视频帧进行取色
            )
            
            if not bg_img:
                print("创建圆角矩形背景失败")
                return None
        else:
            print("背景功能已禁用，跳过背景生成")
        
        # 10. 添加字幕和背景到视频（带动画效果）
        
        # 动画参数设置
        entrance_duration = 3.0  # 入场动画持续3秒
        fps = 30  # 帧率
        
        # 字幕X坐标 - 直接使用传入的绝对坐标
        x_position = int(subtitle_text_x)  # 字幕X轴绝对坐标
        
        # 首先确定背景位置 - 这是基础位置，其他元素都以此为基准
        bg_y_position = int(subtitle_y)  # 背景垂直位置直接使用传入的subtitle_y参数
        
        # 背景动画 - 水平方向
        bg_start_x = -bg_width
        bg_final_x = int(subtitle_x)  # 背景水平位置使用传入的subtitle_x参数
        
        # 字幕垂直位置 - 直接使用传入的绝对坐标（可能已被随机位置修改）
        # 字幕位置由subtitle_text_y参数直接指定
        final_y_position = int(subtitle_text_y)  # 使用可能已经随机化的Y坐标
        
        # 文字入场动画起始位置
        start_y_position = height + 50  # 动画起始位置（屏幕下方）
        
        # 图片水平位置参数
        img_x_position = int(img_position_x)  # 图片X轴绝对坐标
        
        # 图片垂直位置 - 直接使用传入的绝对坐标
        # 图片位置由img_position_y参数直接指定
        img_final_position = int(img_position_y)  # 图片Y轴绝对坐标
        
        img_start_x = -img_size  # 图片动画起始位置
        
        # 字幕X坐标 - 直接使用传入的绝对坐标（可能已被随机位置修改）
        subtitle_absolute_x = int(subtitle_text_x)  # 使用可能已经随机化的X坐标
        
        print(f"【位置调试】背景位置: x={bg_final_x}, y={bg_y_position}, 宽={bg_width}, 高={bg_height}")
        print(f"【位置调试】字幕位置: x={subtitle_absolute_x}, y={final_y_position}, 字体大小={font_size}")
        print(f"【位置调试】图片位置: x={img_x_position}, y={img_final_position}, 大小={img_size}")
        print(f"【位置调试】传入的参数: img_position_x={img_position_x}, img_position_y={img_position_y}")
        print(f"【位置调试】字幕动画参数: 入场时间={entrance_duration}秒, 起始位置=({subtitle_absolute_x}, {start_y_position}), 最终位置=({subtitle_absolute_x}, {final_y_position})")
        print(f"【位置调试】背景动画参数: 入场时间={entrance_duration}秒, 起始位置=({bg_start_x}, {bg_y_position}), 最终位置=({bg_final_x}, {bg_y_position})")
        print(f"【位置调试】图片动画参数: 入场时间={entrance_duration}秒, 起始位置=({img_start_x}, {img_final_position}), 最终位置=({img_x_position}, {img_final_position})")
        
        # 记录到日志
        logging.info(f"📍 最终位置参数: 字幕=({subtitle_absolute_x}, {final_y_position}), 背景=({bg_final_x}, {bg_y_position}), 图片=({img_x_position}, {img_final_position})")
        
        # 构建FFmpeg命令来叠加字幕、背景和图片
        output_with_subtitle = temp_dir / "with_subtitle.mp4"
        
        # 添加QuickTime兼容性参数
        if quicktime_compatible:
            print("应用QuickTime兼容性参数")
        
        ffmpeg_command = [
            'ffmpeg', '-y',
            '-i', str(video_path)
        ]
        
        # 动态添加输入文件
        logging.info("🔨 开始添加输入文件")
        input_index = 1
        subtitle_index = None
        bg_index = None
        img_index = None
        gif_index = None
        
        if enable_subtitle and subtitle_img:
            ffmpeg_command.extend(['-i', str(subtitle_img)])
            subtitle_index = input_index
            input_index += 1
            logging.info(f"  📝 添加字幕输入: 索引{subtitle_index}, 文件{subtitle_img}")
            
        if enable_background and bg_img:
            ffmpeg_command.extend(['-i', str(bg_img)])
            bg_index = input_index
            input_index += 1
            logging.info(f"  🎨 添加背景输入: 索引{bg_index}, 文件{bg_img}")
            
        if enable_image and has_image:
            if 'processed_img_path' in locals() and processed_img_path:
                ffmpeg_command.extend(['-i', str(processed_img_path)])
                img_index = input_index
                input_index += 1
                logging.info(f"  📸 添加图片输入: 索引{img_index}, 文件{processed_img_path}")
            else:
                logging.warning(f"  ⚠️ 图片启用但processed_img_path未定义")
            
        if enable_gif and has_gif:
            ffmpeg_command.extend(['-i', str(processed_gif_path)])
            gif_index = input_index
            input_index += 1
            logging.info(f"  🎞️ 添加GIF输入: 索引{gif_index}, 文件{processed_gif_path}")
        
        logging.info(f"  📊 总输入文件数: {input_index} (包括主视频)")
            
        # 构建复杂过滤器
        logging.info("🔍 开始构建过滤器链")
        filter_complex = f"[0:v]trim=duration={duration}[v1];"
        current_video = "v1"
        next_video_index = 2
        logging.info(f"  🎬 基础视频流: [0:v] -> [v1]")
        
        # 格式化图层
        logging.info("🎨 格式化图层")
        if enable_subtitle and subtitle_index is not None:
            filter_complex += f"[{subtitle_index}:v]format=rgba[s1];"
            logging.info(f"  📝 字幕图层: [{subtitle_index}:v] -> [s1]")
            
        if enable_background and bg_index is not None:
            filter_complex += f"[{bg_index}:v]format=rgba[bg];"
            logging.info(f"  🎨 背景图层: [{bg_index}:v] -> [bg]")
            
        if enable_image and img_index is not None:
            filter_complex += f"[{img_index}:v]format=rgba[img];"
            logging.info(f"  📸 图片图层: [{img_index}:v] -> [img]")
            
        if enable_gif and gif_index is not None:
            filter_complex += f"[{gif_index}:v]format=rgba[gif];"
            logging.info(f"  🎞️ GIF图层: [{gif_index}:v] -> [gif]")
            
        # 叠加背景（如果启用）
        logging.info("🔄 开始叠加层处理")
        if enable_background and bg_index is not None:
            overlay_cmd = f"[{current_video}][bg]overlay=x='if(lt(t,{entrance_duration}),{bg_start_x}+({bg_final_x}-({bg_start_x}))*t/{entrance_duration},{bg_final_x})':y={bg_y_position}:shortest=0:format=auto[v{next_video_index}];"
            filter_complex += overlay_cmd
            logging.info(f"  🎨 添加背景叠加: {current_video} + bg -> v{next_video_index}")
            logging.info(f"    位置: x={bg_final_x}, y={bg_y_position}")
            current_video = f"v{next_video_index}"
            next_video_index += 1
        else:
            if enable_background:
                logging.warning(f"  ⚠️ 背景启用但bg_index为None")
        
        # 叠加图片（如果启用）
        if enable_image and img_index is not None:
            overlay_cmd = f"[{current_video}][img]overlay=x='if(lt(t,{entrance_duration}),{img_start_x}+({img_x_position}-({img_start_x}))*t/{entrance_duration},{img_x_position})':y={img_final_position}:shortest=0:format=auto[v{next_video_index}];"
            filter_complex += overlay_cmd
            logging.info(f"  📸 添加图片叠加: {current_video} + img -> v{next_video_index}")
            logging.info(f"    位置: x={img_x_position}, y={img_final_position}")
            current_video = f"v{next_video_index}"
            next_video_index += 1
        else:
            if enable_image:
                logging.warning(f"  ⚠️ 图片启用但img_index为None或has_image为False")
            
        if enable_gif and gif_index is not None:
            # 修复：使用正确的overlay语法，移除不兼容的format参数
            # 简化为基本的overlay语法，FFmpeg会自动处理透明度
            overlay_cmd = f"[{current_video}][gif]overlay=x={gif_x}:y={gif_y}[v{next_video_index}];"
            filter_complex += overlay_cmd
            logging.info(f"  🎞️ 添加GIF叠加: {current_video} + gif -> v{next_video_index}")
            logging.info(f"    位置: x={gif_x}, y={gif_y}")
            logging.info(f"    修复说明: 使用兼容的overlay语法，移除format参数")
            current_video = f"v{next_video_index}"
            next_video_index += 1
        else:
            if enable_gif:
                logging.warning(f"  ⚠️ GIF启用但gif_index为None或has_gif为False")
            
        # 叠加字幕（如果启用）
        if enable_subtitle and subtitle_index is not None:
            overlay_cmd = f"[{current_video}][s1]overlay=x={subtitle_absolute_x}:y='if(lt(t,{entrance_duration}),{start_y_position}-({start_y_position}-{final_y_position})*t/{entrance_duration},{final_y_position})':shortest=0:format=auto"
            filter_complex += overlay_cmd
            logging.info(f"  📝 添加字幕叠加: {current_video} + s1 -> 最终输出")
            logging.info(f"    位置: x={subtitle_absolute_x}, y={final_y_position}")
            logging.info(f"    随机位置: {random_position}")
        else:
            # 如果没有字幕，移除最后的分号
            filter_complex = filter_complex.rstrip(';')
            if enable_subtitle:
                logging.warning(f"  ⚠️ 字幕启用但subtitle_index为None或subtitle_img为None")
            
        logging.info(f"  🔗 最终过滤器链: {filter_complex}")
        
        # 检查是否有任何素材需要处理
        has_any_overlay = (enable_subtitle and subtitle_img) or (enable_background and bg_img) or (enable_image and has_image) or (enable_gif and has_gif)
        
        # 添加详细的调试信息
        logging.info(f"🚿 【素材状态调试】完整状态检查")
        logging.info(f"  enable_subtitle: {enable_subtitle}, subtitle_img: {subtitle_img is not None}")
        logging.info(f"  enable_background: {enable_background}, bg_img: {bg_img is not None}")
        logging.info(f"  enable_image: {enable_image}, has_image: {has_image}")
        logging.info(f"  enable_gif: {enable_gif}, has_gif: {has_gif}")
        logging.info(f"  enable_music: {enable_music}, music_path: {music_path}")
        logging.info(f"  has_any_overlay: {has_any_overlay}")
        
        print(f"🚿 【素材状态调试】")
        print(f"  enable_subtitle: {enable_subtitle}, subtitle_img: {subtitle_img is not None}")
        print(f"  enable_background: {enable_background}, bg_img: {bg_img is not None}")
        print(f"  enable_image: {enable_image}, has_image: {has_image}")
        print(f"  enable_gif: {enable_gif}, has_gif: {has_gif}")
        print(f"  has_any_overlay: {has_any_overlay}")
        
        # 添加更详细的素材状态检查
        if enable_image:
            logging.info(f"  📸 图片详细状态: final_image_path={final_image_path}")
            if final_image_path:
                logging.info(f"  📸 图片文件存在: {Path(final_image_path).exists()}")
                if Path(final_image_path).exists():
                logging.info(f"  📸 图片文件存在: {Path(final_image_path).exists()}")
                    
        if enable_background:
            logging.info(f"  🎨 背景详细状态: bg_img={bg_img}")
            if bg_img:
                logging.info(f"  🎨 背景文件存在: {Path(bg_img).exists()}")
                
        if enable_gif:
            logging.info(f"  🎞️ GIF详细状态: processed_gif_path={processed_gif_path}")
            if processed_gif_path:
                logging.info(f"  🎞️ GIF文件存在: {Path(processed_gif_path).exists()}")
                
        if enable_music:
            logging.info(f"  🎵 音乐详细状态: music_path={music_path}")
            if music_path:
                logging.info(f"  🎵 音乐路径存在: {Path(music_path).exists()}")
        
        if enable_image and not has_image:
            logging.warning(f"  ⚠️ 图片功能已启用但has_image为False")
            logging.warning(f"  final_image_path: {final_image_path}")
            print(f"  ⚠️ 图片功能已启用但has_image为False")
            print(f"  final_image_path: {final_image_path}")
            if final_image_path:
                exists = Path(final_image_path).exists()
                logging.warning(f"  图片文件存在: {exists}")
                print(f"  图片文件存在: {exists}")
                
        if enable_background and not bg_img:
            logging.warning(f"  ⚠️ 背景功能已启用但bg_img为None")
            print(f"  ⚠️ 背景功能已启用但bg_img为None")
        
        # 处理音乐逻辑
        selected_music_path = None
        if enable_music and music_path:
            print(f"【音乐处理】启用背景音乐: {music_path}, 模式: {music_mode}, 音量: {music_volume}%")
            
            # 根据不同模式选择音乐文件
            if Path(music_path).is_file():
                # 单个音乐文件
                selected_music_path = music_path
                print(f"【音乐处理】使用单个音乐文件: {selected_music_path}")
            elif Path(music_path).is_dir():
                # 音乐文件夹
                music_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.flac']
                music_files = []
                for ext in music_extensions:
                    music_files.extend(list(Path(music_path).glob(f"*{ext}")))
                    music_files.extend(list(Path(music_path).glob(f"*{ext.upper()}")))
                
                if music_files:
                    if music_mode == "random":
                        selected_music_path = str(random.choice(music_files))
                        print(f"【音乐处理】随机选择音乐: {selected_music_path}")
                    elif music_mode == "order":
                        # 按文件名排序，选择第一个（可以根据视频索引选择）
                        music_files.sort(key=lambda x: x.name)
                        selected_music_path = str(music_files[0])
                        print(f"【音乐处理】按顺序选择音乐: {selected_music_path}")
                    else:  # single模式，选择第一个
                        selected_music_path = str(music_files[0])
                        print(f"【音乐处理】选择第一个音乐: {selected_music_path}")
                else:
                    print(f"【音乐处理】音乐文件夹中没有找到音乐文件: {music_path}")
            else:
                print(f"【音乐处理】音乐路径无效: {music_path}")
        
        if has_any_overlay or selected_music_path:
            # 构建FFmpeg命令
            input_index = 1  # 视频输入为0，从1开始计算其他输入
            
            # 音乐输入
            if selected_music_path:
                ffmpeg_command.extend(['-i', selected_music_path])
                music_index = input_index
                input_index += 1
                print(f"【音乐处理】添加音乐输入，索引: {music_index}")
            
            if has_any_overlay:
                # 完成视频处理的filter_complex
                ffmpeg_command.extend(['-filter_complex', filter_complex])
            
            # 解析质量设置参数
            if quality_settings:
                crf_value = quality_settings.get('crf_value', 18)
                preset_value = quality_settings.get('preset_value', 'slow')
                profile_value = quality_settings.get('profile_value', 'high')
                level_value = quality_settings.get('level_value', '4.1')
                maxrate_value = quality_settings.get('maxrate_value', 8000)
                bufsize_value = quality_settings.get('bufsize_value', 16000)
                gop_value = quality_settings.get('gop_value', 30)
                tune_value = quality_settings.get('tune_value', 'film')
                pixfmt_value = quality_settings.get('pixfmt_value', 'yuv420p')
                
                print(f"🎨 使用自定义质量设置: CRF={crf_value}, Preset={preset_value}, Profile={profile_value}")
                print(f"🎨 质量参数: Level={level_value}, MaxRate={maxrate_value}kbps, BufSize={bufsize_value}kbps")
                print(f"🎨 高级参数: GOP={gop_value}, Tune={tune_value}, PixFmt={pixfmt_value}")
            else:
                # 默认参数 (针对TikTok优化)
                crf_value = 18
                preset_value = 'slow'
                profile_value = 'high'
                level_value = '4.1'
                maxrate_value = 8000
                bufsize_value = 16000
                gop_value = 30
                tune_value = 'film'
                pixfmt_value = 'yuv420p'
                
                print(f"🎨 使用默认质量设置: CRF={crf_value}, Preset={preset_value}, Profile={profile_value}")
            
            # 视频编码参数（使用动态质量设置）
            ffmpeg_command.extend([
                '-c:v', 'libx264',
                '-pix_fmt', pixfmt_value,
                '-profile:v', profile_value,
                '-level', level_value,
                '-crf', str(crf_value),
                '-preset', preset_value,
                '-movflags', '+faststart',
                '-brand', 'mp42',
                '-tag:v', 'avc1',
                # TikTok推荐的高清参数
                '-maxrate', f'{maxrate_value}k',
                '-bufsize', f'{bufsize_value}k',
                '-g', str(gop_value),
                '-keyint_min', str(gop_value // 2),
                '-sc_threshold', '40',
            ])
            
            # 添加tune参数（如果不是'none'）
            if tune_value and tune_value != 'none':
                ffmpeg_command.extend(['-tune', tune_value])
            
            # 音频处理
            if selected_music_path:
                # 计算音量调节值（50% = 0.5）
                volume_ratio = music_volume / 100.0
                print(f"【音乐处理】音量比例: {volume_ratio}")
                
                ffmpeg_command.extend([
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-af', f'volume={volume_ratio}',  # 调节音量
                    '-shortest'  # 以最短的流为准（视频结束时音频也结束）
                ])
                print(f"【音乐处理】添加音频编码参数，音量: {music_volume}%")
            else:
                # 如果没有音乐，不包含音频
                ffmpeg_command.extend(['-an'])
            
            ffmpeg_command.append(str(output_with_subtitle))
            
            # 执行命令
            logging.info(f"🎥 执行最终FFmpeg命令")
            logging.info(f"  命令长度: {len(ffmpeg_command)} 个参数")
            logging.info(f"  输入文件数: {input_index}")
            logging.info(f"  输出文件: {output_with_subtitle}")
            logging.info(f"  完整命令: {' '.join(ffmpeg_command)}")
            print(f"执行命令: {' '.join(ffmpeg_command)}")
            result = run_ffmpeg_command(ffmpeg_command)
                
            if not result:
                print("添加素材失败，尝试使用备用方法")
                if enable_subtitle and subtitle_img:
                    return fallback_static_subtitle(video_path, subtitle_img, output_path, temp_dir, quicktime_compatible)
                else:
                    print("没有字幕可用于备用方法，直接复制原视频")
                    # 直接复制原视频
                    copy_cmd = [
                        'ffmpeg', '-y',
                        '-i', str(video_path),
                        '-c', 'copy',
                        str(output_with_subtitle)
                    ]
                    if not run_ffmpeg_command(copy_cmd):
                        return None
        else:
            print("所有素材功能都已禁用，但需要处理音乐")
            # 如果只有音乐，直接复制视频并添加音乐
            if selected_music_path:
                volume_ratio = music_volume / 100.0
                print(f"【音乐处理】只添加音乐，不添加其他素材")
                copy_with_music_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-i', selected_music_path,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-af', f'volume={volume_ratio}',
import subprocess
from pathlib import Path


def run_ffmpeg_command(command):
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def add_music_to_video(video_path, music_path, output_path=None):
    # 确保输出路径的目录存在
    if output_path:
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    else:
        print("输出路径为空")
        return None
                    str(output_with_subtitle)
                ]
                if not run_ffmpeg_command(copy_cmd):
                    print("复制原视频失败")
                    return None
        
        # 10. 添加QuickTime兼容性（如果需要）
        final_cmd = [
            'ffmpeg', '-y',
            '-i', str(output_with_subtitle),
            '-c', 'copy',
            '-movflags', '+faststart',
            str(output_path)
        ]
        
        print(f"执行命令: {' '.join(final_cmd)}")
        if run_ffmpeg_command(final_cmd):
            print(f"成功添加字幕动画，输出到: {output_path}")
            return output_path
        else:
            print("最终转换失败")
            return None
    
    except Exception as e:
        print(f"添加字幕时出错: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass


def fallback_static_subtitle(video_path, subtitle_img_path, output_path, temp_dir, quicktime_compatible=False):
    """
    静态字幕备用方案
    当动画字幕失败时使用
    
    参数:
        video_path: 视频路径
        subtitle_img_path: 字幕图片路径
        output_path: 输出路径
        temp_dir: 临时目录
        quicktime_compatible: 是否生成QuickTime兼容的视频
    """
    print("使用静态字幕备用方案" + (", QuickTime兼容模式" if quicktime_compatible else ""))
    
    # 获取视频信息
    video_info = get_video_info(video_path)
    if not video_info:
        return None
        
    width, height, duration = video_info
    
    # 计算字幕位置
    x_position = int(width * 0.08)  # 水平位置为视频宽度的8%
    y_position = int(height * 0.65)  # 垂直位置为视频高度的65%
    
    # 使用静态字幕
    output_with_subtitle = temp_dir / "with_static_subtitle.mp4"
    
    # 构建滤镜表达式
    filter_complex = (
        f"[0:v]trim=duration={duration}[v1];"
        f"[1:v]format=rgba[s1];"
        f"[v1][s1]overlay=x={x_position}:y={y_position}:shortest=0:format=auto"
    )
    
    # 直接将字幕添加到视频上
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-i', str(subtitle_img_path),
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',  # 确保输出格式是yuv420p
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-movflags', '+faststart',
    ]
    
    # 添加QuickTime兼容性参数
    if quicktime_compatible:
        cmd.extend([
            '-brand', 'mp42',  # 设置兼容的品牌标记
            '-tag:v', 'avc1',  # 使用标准AVC标记
        ])
        print("应用静态字幕的QuickTime兼容性参数")
    
    # 不要音频
    cmd.extend(['-an', str(output_with_subtitle)])
    
    if not run_ffmpeg_command(cmd):
        print("静态字幕添加失败")
        return None
    
    # 复制到最终输出路径
    ensure_dir(Path(output_path).parent)
    
    # 使用ffmpeg复制整个视频，而不是简单的文件复制
    copy_cmd = [
        'ffmpeg', '-y',
        '-i', str(output_with_subtitle),
        '-c', 'copy',  # 使用复制模式，不重新编码
        '-movflags', '+faststart',
        str(output_path)
    ]
    
    if not run_ffmpeg_command(copy_cmd):
        print(f"复制最终视频失败，尝试直接复制文件")
        shutil.copy2(output_with_subtitle, output_path)
    
    print(f"成功添加静态字幕，输出到: {output_path}")
    return output_path


def process_reverse_effect(video_path, output_path):
    """
    对视频进行正放+倒放处理
    
    参数:
        video_path: 输入视频路径
        output_path: 输出视频路径
        
    返回:
        成功返回True，失败返回False
    """
    print(f"对视频进行正放+倒放处理: {video_path}")
    
    # 使用一条命令完成正放+倒放+拼接
    cmd = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-filter_complex',
        '[0:v]split[v1][v2];[v2]reverse[reversed];[v1][reversed]concat=n=2:v=1:a=0[v]',
        '-map', '[v]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-crf', "23",  
        '-b:v', "4M",       
        '-movflags', '+faststart',
        '-brand', 'mp42',  # 设置兼容的品牌标记
        '-tag:v', 'avc1',  # 使用标准AVC标记
        '-an',  # 不要音频
        str(output_path)
    ]
    
    return run_ffmpeg_command(cmd)


def batch_process_videos(style=None, subtitle_lang=None, quicktime_compatible=False, 
                         img_position_x=100, img_position_y=0, font_size=70, 
                         subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                         subtitle_text_x=0, subtitle_text_y=1190):
    """
    批量处理视频
    
    参数:
        style: 字幕样式，如果为None则每个视频随机选择，如果为"random"则强制每个视频随机选择
        subtitle_lang: 字幕语言，如果为"malay"则所有视频使用马来西亚字幕，如果为"thai"则所有视频使用泰国字幕
        quicktime_compatible: 是否生成QuickTime兼容的视频
        img_position_x: 图片X轴绝对坐标（像素，默认100）
        img_position_y: 图片Y轴绝对坐标（像素，默认0）
        font_size: 字体大小（像素，默认70）
        subtitle_x: 背景X轴绝对坐标（像素，默认-50）
        subtitle_y: 背景Y轴绝对坐标（像素，默认1100）
        bg_width: 背景宽度（像素，默认1000）
        bg_height: 背景高度（像素，默认180）
        img_size: 图片大小（像素，默认420）
        subtitle_text_x: 字幕X轴绝对坐标（像素，默认0）
        subtitle_text_y: 字幕Y轴绝对坐标（像素，默认1190）
        
    返回:
        处理成功的视频数量
    """
    # 确保字幕语言是有效的选择
    if subtitle_lang not in ["malay", "thai", None, "random"]:
        print(f"警告：无效的字幕语言 '{subtitle_lang}'，将使用默认值")
        subtitle_lang = None
    
    # 如果是random，随机选择一种语言并固定使用
    if subtitle_lang == "random":
        subtitle_lang = random.choice(["malay", "thai"])
        print(f"随机选择并固定使用语言: {subtitle_lang}")
    
    print(f"批量处理视频，样式: {'随机' if style is None or style == 'random' else style}, 语言: {subtitle_lang}, QuickTime兼容模式: {'启用' if quicktime_compatible else '禁用'}")
    print(f"图片位置: X={img_position_x}, Y={img_position_y}, 大小={img_size}")
    print(f"字幕背景位置: X={subtitle_x}, Y={subtitle_y}, 宽={bg_width}, 高={bg_height}")
    print(f"字幕文字位置: X={subtitle_text_x}, Y={subtitle_text_y}, 字体大小={font_size}")
    
    # 获取视频目录
    videos_dir = get_data_path("input/videos")
    # 修改为指定的输出目录
    output_dir = Path("/Users/jerry/Documents/VS code file/video+number_backup_20250704_163846-带价格/VideoApp/output")
    
    # 确保目录存在
    if not Path(videos_dir).exists():
        Path(videos_dir).mkdir(parents=True, exist_ok=True)
    if not Path(output_dir).exists():
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 获取所有视频文件
    video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.mkv']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(Path(videos_dir).glob(f"*{ext}")))
    
    if not video_files:
        print("没有找到视频文件")
        return 0
    
    print(f"找到 {len(video_files)} 个视频文件")
    
    # 处理每个视频
    success_count = 0
    last_style = None  # 记录上一个视频使用的样式
    
    # 预先创建所有可能的样式
    all_styles = ["style1", "style2", "style3", "style4", "style5", "style6", "style7", "style8", "style9", "style10", "style11"]
    
    for video_path in video_files:
        print(f"\n处理视频: {video_path.name}")
        output_path = output_dir / f"{video_path.stem}_processed.mp4"
        
        # 为每个视频独立随机选择样式
        current_style = None
        if style == "random" or style is None:
            # 当style为"random"或None时，确保不会连续使用相同的样式
            available_styles = [s for s in all_styles if s != last_style]
            
            # 如果所有样式都已使用过一次，重置可用样式列表
            if len(available_styles) == 0:
                available_styles = all_styles.copy()
                if last_style in available_styles:
                    available_styles.remove(last_style)
            
            current_style = random.choice(available_styles)
            last_style = current_style
            
            print(f"随机选择样式（避免重复）: {current_style}")
        else:
            # 使用指定的样式
            current_style = style
            print(f"使用指定样式: {current_style}")
        
        try:
            if process_video(
                video_path, 
                output_path, 
                current_style, 
                subtitle_lang,
                quicktime_compatible=quicktime_compatible,
                img_position_x=img_position_x,
                img_position_y=img_position_y,
                font_size=font_size,
                subtitle_x=subtitle_x,
                subtitle_y=subtitle_y,
                bg_width=bg_width,
                bg_height=bg_height,
                img_size=img_size,
                subtitle_text_x=subtitle_text_x,
                subtitle_text_y=subtitle_text_y
            ):
                success_count += 1
                print(f"✅ 视频处理成功: {video_path.name}")
            else:
                print(f"❌ 视频处理失败: {video_path.name}")
        except Exception as e:
            print(f"❌ 处理视频时出错: {e}")
    
    print(f"\n批量处理完成: {success_count}/{len(video_files)} 个视频成功")
    return success_count


def find_matching_image(video_name, image_dir="input/images", custom_image_path=None):
    """
    查找与视频文件名匹配的图片
    
    参数:
        video_name: 视频文件名（不含扩展名）
        image_dir: 图片目录（当custom_image_path为None时使用）
        custom_image_path: 用户自定义的图片文件夹路径，优先使用
        
    返回:
        匹配的图片路径，如果没有找到则返回None
    """
    try:
        print(f"查找匹配图片，视频名称: {video_name}")
        
        # 如果用户提供了自定义图片路径，优先使用
        if custom_image_path and Path(custom_image_path).exists():
            full_image_dir = custom_image_path
            print(f"使用用户自定义图片目录: {full_image_dir}")
        else:
            # 获取完整的图片目录路径
            # 1. 优先检查VideoApp/input/images目录
            videoapp_dir_path = Path.cwd() / "VideoApp/input/images"
            # 2. 然后检查当前目录下的input/images
            current_dir_path = Path.cwd() / "input/images"
            
            if Path(videoapp_dir_path).exists():
                full_image_dir = str(videoapp_dir_path)
                print(f"使用VideoApp下的图片目录: {full_image_dir}")
            elif Path(current_dir_path).exists():
                full_image_dir = str(current_dir_path)
                print(f"使用当前工作目录下的图片目录: {full_image_dir}")
            elif image_dir.startswith("../"):
                # 如果是相对路径，直接使用
                full_image_dir = image_dir
                print(f"使用相对路径图片目录: {full_image_dir}")
            else:
                # 否则使用get_data_path函数
                full_image_dir = str(get_data_path(image_dir))
                print(f"使用get_data_path获取图片目录: {full_image_dir}")
        
        print(f"最终图片目录路径: {full_image_dir}")
            
        if not Path(full_image_dir).exists():
            print(f"图片目录不存在: {full_image_dir}")
            # 尝试创建目录
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
    except Exception as ex:
        print(f"查找匹配图片时出错: {ex}")
        import traceback
        traceback.print_exc()
        return None


def batch_process_videos(style=None, subtitle_lang=None, quicktime_compatible=False, 
                         img_position_x=100, img_position_y=0, font_size=70, 
                         subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                         subtitle_text_x=0, subtitle_text_y=1190):
    """
    批量处理视频
    
    参数:
        style: 字幕样式，如果为None则每个视频随机选择，如果为"random"则强制每个视频随机选择
        subtitle_lang: 字幕语言，如果为"malay"则所有视频使用马来西亚字幕，如果为"thai"则所有视频使用泰国字幕
        quicktime_compatible: 是否生成QuickTime兼容的视频
        img_position_x: 图片X轴绝对坐标（像素，默认100）
        img_position_y: 图片Y轴绝对坐标（像素，默认0）
        font_size: 字体大小（像素，默认70）
        subtitle_x: 背景X轴绝对坐标（像素，默认-50）
        subtitle_y: 背景Y轴绝对坐标（像素，默认1100）
        bg_width: 背景宽度（像素，默认1000）
        bg_height: 背景高度（像素，默认180）
        img_size: 图片大小（像素，默认420）
        subtitle_text_x: 字幕X轴绝对坐标（像素，默认0）
        subtitle_text_y: 字幕Y轴绝对坐标（像素，默认1190）
        
    返回:
        处理成功的视频数量
    """
    try:
        # 获取视频目录
        videos_dir = get_data_path("input/videos")
        # 使用相对路径的output目录
        output_dir = Path("output")
        
        # 确保目录存在
        if not Path(videos_dir).exists():
            print(f"视频目录不存在: {videos_dir}")
            return
        
        # 确保输出目录存在
        output_dir_path = Path(output_dir)
        if not output_dir_path.exists():
            try:
                output_dir_path.mkdir(parents=True, exist_ok=True)
                print(f"创建输出目录: {output_dir}")
            except Exception as e:
                print(f"创建输出目录失败: {e}")
                return

        # 列出目录中所有文件
        all_files = [f.name for f in Path(videos_dir).iterdir() if f.is_file()]
        print(f"目录中的文件数量: {len(all_files)}")
        print(f"目录中的所有文件: {all_files}")
        
        # 支持的视频扩展名
        video_extensions = ['.mp4', '.mkv', '.avi']
        
        # 过滤出视频文件
        video_files = [f for f in all_files if any(f.lower().endswith(ext.lower()) for ext in video_extensions)]
        print(f"视频文件数量: {len(video_files)}")
        print(f"视频文件: {video_files}")
        
        # 随机选择字幕样式
        if style is None:
            style = random.choice(["malay", "thai"])
        elif style == "random":
            style = random.choice(["malay", "thai"])
        else:
            style = style.lower()
        
        # 随机选择字幕语言
        if subtitle_lang is None:
            subtitle_lang = random.choice(["malay", "thai"])
        else:
            subtitle_lang = subtitle_lang.lower()
        
        # 处理每个视频文件
        success_count = 0
        for video_file in video_files:
            video_path = Path(videos_dir) / video_file
            print(f"处理视频: {video_path}")
            
            # 查找匹配的图片
            image_path = find_matching_image(video_file)
            if image_path is None:
                print(f"未找到匹配的图片，跳过视频: {video_path}")
                continue
            
            # 处理图片以准备叠加到视频上
            processed_image_path = Path(output_dir) / f"{video_file}_processed.png"
            processed_image_path = process_image_for_overlay(image_path, processed_image_path, size=(img_size, img_size))
            if processed_image_path is None:
                print(f"处理图片失败，跳过视频: {video_path}")
                continue
            
            # 生成输出视频路径
            output_video_path = Path(output_dir) / video_file
            
            # 使用ffmpeg进行视频处理
            command = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(processed_image_path),
                "-filter_complex", f"[1]scale={img_size}:{img_size}[img];[0][img]overlay={img_position_x}:{img_position_y}",
                "-vf", f"drawbox=x={subtitle_x}:y={subtitle_y}:w={bg_width}:h={bg_height}:color=black@0.5:enable='between(t,0,999999)'",
                "-vf", f"drawtext=textfile={get_data_path(f'subtitles/{style}/{subtitle_lang}/{video_file}.txt')}:{'force_style=FontSize=' + str(font_size) if font_size else ''}:x={subtitle_text_x}:y={subtitle_text_y}:enable='between(t,0,999999)'",
                "-c:a", "copy",
                "-c:v", "libx264" if not quicktime_compatible else "libx264 -pix_fmt yuv420p",
                str(output_video_path)
            ]
            print(f"执行命令: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"视频处理失败: {result.stderr}")
                continue
            
            print(f"视频处理完成，保存到: {output_video_path}")
            success_count += 1
        
        print(f"处理完成，成功处理 {success_count} 个视频")
        return success_count
    except Exception as ex:
        print(f"批量处理视频时出错: {ex}")
        import traceback
        traceback.print_exc()
        return 0


def find_matching_image(video_name):
    """
    查找与视频名称匹配的图片
    
    参数:
        video_name: 视频名称
        
    返回:
        匹配的图片路径，如果没有找到则返回None
    """
    try:
        # 获取图片目录
        image_dir = get_data_path("input/images")
        full_image_dir = None
        
        # 检查图片目录是否存在
        if not Path(image_dir).exists():
            print(f"图片目录不存在: {image_dir}")
            return None
        
        # 检查是否为相对路径
        if image_dir.startswith("./"):
            # 如果是当前工作目录下的相对路径，使用当前工作目录
            current_dir_path = Path.cwd()
            full_image_dir = str(current_dir_path)
            print(f"使用当前工作目录下的图片目录: {full_image_dir}")
        elif image_dir.startswith("../"):
            # 如果是相对路径，直接使用
            full_image_dir = image_dir
            print(f"使用相对路径图片目录: {full_image_dir}")
        else:
            # 否则使用get_data_path函数
            full_image_dir = str(get_data_path(image_dir))
            print(f"使用get_data_path获取图片目录: {full_image_dir}")
        
        print(f"最终图片目录路径: {full_image_dir}")
            
        if not Path(full_image_dir).exists():
            print(f"图片目录不存在: {full_image_dir}")
            # 尝试创建目录
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
    except Exception as ex:
        print(f"查找匹配图片时出错: {ex}")
        import traceback
        traceback.print_exc()
        return None


def process_image_for_overlay(image_path, output_path, size=(420, 420)):
    """
    处理图片以准备叠加到视频上
    
    参数:
        image_path: 输入图片路径
        output_path: 输出图片路径
        size: 输出图片大小，默认420x420像素
        
    返回:
        处理后的图片路径，失败返回None
    """
    try:
        print(f"【图片处理】原始图片: {image_path}")
        print(f"【图片处理】目标大小: {size}")
        
        # 打开图片
        img = Image.open(image_path)
        
        original_size = img.size
        print(f"【图片处理】原始图片大小: {original_size}")
            
        # 保持宽高比缩放
        width, height = img.size
        if width > height:
            new_width = size[0]
            new_height = int(height * (new_width / width))
        else:
            new_height = size[1]
            new_width = int(width * (new_height / height))
        
        # 缩放图片
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"【图片处理】缩放后图片大小: {img.size}")
        
        # 创建一个全透明的新图片，大小与缩放后的图片相同
        # 修改：不再使用固定尺寸的画布，改用图片自身尺寸，避免定位问题
        new_img = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
        
        # 直接将图片放置在透明背景上，不再进行居中处理
        new_img.paste(img, (0, 0), img)
        
        # 保存处理后的图片
        new_img.save(output_path)
        print(f"【图片处理】图片处理完成，保存到: {output_path}")
        
        # 验证处理后的图片
        processed_img = Image.open(output_path)
        print(f"【图片处理】验证处理后图片大小: {processed_img.size}")
        
        return output_path
    except Exception as e:
        print(f"处理图片时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_subtitle_image(text, style="style1", width=1080, height=300, font_size=70, output_path=None, subtitle_width=800):
    """
    创建字幕图片
    
    参数:
        text: 字幕文本
        style: 样式名称
        width: 图片宽度
        height: 图片高度
        font_size: 字体大小
        output_path: 输出路径
        
    返回:
        字幕图片路径
    """
    try:
        print(f"创建字幕图片: 宽={width}, 高={height}, 字体大小={font_size}, 样式={style}")
        print(f"字幕内容: {text}")
        
        # 检查文字类型
        def contains_chinese(s):
            # 中文Unicode范围: 4E00-9FFF
            for char in s:
                if '\u4E00' <= char <= '\u9FFF':
                    return True
            return False
            
        def contains_thai(s):
            # 泰文Unicode范围: 0E00-0E7F
            for char in s:
                if '\u0E00' <= char <= '\u0E7F':
                    return True
            return False
            
        is_chinese_text = contains_chinese(text)
        is_thai_text = contains_thai(text)
        print(f"是否包含中文: {is_chinese_text}")
        print(f"是否包含泰文: {is_thai_text}")
        
        # 如果没有指定输出路径，生成一个临时文件
        if not output_path:
            import tempfile
            output_path = Path(tempfile.gettempdir()) / f"subtitle_{int(time.time())}.png"
            
        # 创建透明背景的图片
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 如果是"random"样式，先随机选择一个实际样式
        if style == "random":
            # 从配置文件中动态获取所有可用的样式
            style_config_parser = load_style_config()
            available_styles = []
            
            try:
                # 检查style_config_parser是否有sections方法
                if hasattr(style_config_parser, 'sections') and callable(getattr(style_config_parser, 'sections', None)):
                    # ConfigParser 对象
                    for section in style_config_parser.sections():
                        if section.startswith("styles."):
                            style_name = section.replace("styles.", "")
                            available_styles.append(style_name)
                else:
                    # 如果不是 ConfigParser 对象，使用默认样式列表
                    print("配置文件加载失败，使用默认样式列表")
                    available_styles = []
            except Exception as e:
                print(f"处理样式配置时出错: {e}，使用默认样式列表")
                available_styles = []
            
            # 如果没有找到任何样式，使用默认样式列表
            if not available_styles:
                available_styles = ["style1", "style2", "style3", "style4", "style5", "style6", 
                                    "style7", "style8", "style9", "style10", "style11"]
            
            style = random.choice(available_styles)
            print(f"在create_subtitle_image中随机选择样式: {style} (从 {len(available_styles)} 种样式中选择)")
        
        # 加载样式配置
        style_config = load_style_config(style)
        if style_config and isinstance(style_config, dict):
            print(f"成功加载样式配置: {style_config}")
            
            # 获取字体路径
            font_path = style_config.get('font_path', 'data/fonts/BebasNeue-Regular.ttf')
            print(f"使用自定义字体路径: {font_path}")
            
            # 使用传入的字体大小，这是最高优先级
            custom_font_size = font_size
            print(f"使用传入的字体大小: {custom_font_size}")
            
            # 获取文本颜色
            text_color = style_config.get('text_color', [255, 255, 255, 255])
            if isinstance(text_color, list):
                text_color = tuple(text_color)  # 转换列表为元组
            print(f"使用自定义文本颜色: {text_color}")
            
            # 获取描边颜色
            stroke_color = style_config.get('stroke_color', [0, 0, 0, 255])
            if isinstance(stroke_color, list):
                stroke_color = tuple(stroke_color)  # 转换列表为元组
            print(f"使用自定义描边颜色: {stroke_color}")
            
            # 获取描边宽度
            stroke_width = style_config.get('stroke_width', 2)
            print(f"使用自定义描边宽度: {stroke_width}")
            
            # 获取白色描边比例
            white_stroke_ratio = style_config.get('white_stroke_ratio', 1.2)
            print(f"使用自定义白色描边比例: {white_stroke_ratio}")
            
            # 获取阴影设置
            shadow = style_config.get('shadow', False)
            shadow_color = style_config.get('shadow_color', [0, 0, 0, 120])
            if isinstance(shadow_color, list):
                shadow_color = tuple(shadow_color)  # 转换列表为元组
            shadow_offset = style_config.get('shadow_offset', [4, 4])
            print(f"使用自定义阴影设置: {shadow}")
            print(f"使用自定义阴影颜色: {shadow_color}")
            print(f"使用自定义阴影偏移: {shadow_offset}")
        else:
            # 默认样式
            font_path = 'data/fonts/BebasNeue-Regular.ttf'
            custom_font_size = font_size
            text_color = (255, 255, 255, 255)
            stroke_color = (0, 0, 0, 255)
            stroke_width = 2
            white_stroke_ratio = 1.2
            shadow = False
            shadow_color = (0, 0, 0, 120)
            shadow_offset = (4, 4)
            
        # 根据文字类型选择合适的字体
        if is_chinese_text:
            # 中文文本，优先使用中文字体
            font_config = load_style_config()
            if font_config and 'font_paths' in font_config and 'chinese' in font_config['font_paths']:
                chinese_font_path = font_config['font_paths']['chinese']
                print(f"检测到中文，使用中文字体: {chinese_font_path}")
                font_path = chinese_font_path
            else:
                # 备用中文字体
                chinese_fonts = [
                    'data/fonts/NotoSansSC-Bold.ttf',
                    'data/fonts/SourceHanSansCN-Bold.ttf',
                    'data/fonts/SourceHanSansCN-Heavy.ttf',
                    'data/fonts/NotoSansSC-Black.ttf'
                ]
                for cf in chinese_fonts:
                    cf_file = find_font_file(cf)
                    if cf_file:
                        font_path = cf_file
                        print(f"使用备用中文字体: {font_path}")
                        break
        elif is_thai_text:
            # 泰文文本，使用泰文字体
            font_config = load_style_config()
            if font_config and 'font_paths' in font_config and 'thai' in font_config['font_paths']:
                thai_font_path = font_config['font_paths']['thai']
                print(f"检测到泰文，使用泰文字体: {thai_font_path}")
                font_path = thai_font_path
            
        # 查找字体文件
        font_file = find_font_file(font_path)
        if font_file:
            print(f"找到字体文件: {font_file}")
            try:
                # 加载字体
                font = ImageFont.truetype(font_file, custom_font_size)
                print(f"成功加载字体 {font_file}，大小: {custom_font_size}")
            except Exception as e:
                print(f"加载字体失败: {e}")
                # 尝试详细诊断字体文件
                try:
                    with open(font_file, 'rb') as f:
                        header = f.read(4)
                        print(f"字体文件头部字节: {header.hex()}")
                except Exception as ex:
                    print(f"读取字体文件失败: {ex}")
                font = None
        else:
            font = None
            print("找不到指定字体，将尝试备用字体")
            
        # 如果字体加载失败，尝试其他字体
        if font is None:
            # 尝试其他可能的字体
            fallback_fonts = [
                "data/fonts/Kanit-Bold.ttf",
                "data/fonts/Sarabun-Bold.ttf",
                "data/fonts/Montserrat-Bold.ttf",
                "data/fonts/BebasNeue-Regular.ttf",
                "Arial.ttf",
                "Arial",
                "Helvetica",
                "DejaVuSans.ttf"
            ]
            
            for fb_font in fallback_fonts:
                try:
                    fb_font_file = find_font_file(fb_font)
                    if fb_font_file:
                        font = ImageFont.truetype(fb_font_file, custom_font_size)
                        print(f"使用备用字体: {fb_font_file}, 大小: {custom_font_size}")
                        break
                    elif Path(fb_font).exists():
                        font = ImageFont.truetype(fb_font, custom_font_size)
                        print(f"使用备用字体: {fb_font}, 大小: {custom_font_size}")
                        break
                    elif fb_font in ["Arial", "Helvetica"]:
                        # 尝试使用系统字体
                        font = ImageFont.truetype(fb_font, custom_font_size)
                        print(f"使用系统字体: {fb_font}, 大小: {custom_font_size}")
                        break
                except Exception as e:
                    print(f"加载备用字体 {fb_font} 失败: {e}")
                    continue
            
            # 如果所有字体都加载失败，使用默认字体
            if font is None:
                font = ImageFont.load_default()
                print(f"所有字体加载失败，使用默认字体，尝试指定大小: {custom_font_size}")
                # 尝试强制设置默认字体大小
                try:
                    # 对于默认字体，尝试重新创建指定大小的字体
                    font = ImageFont.load_default()
                    print(f"使用默认字体，尺寸: {custom_font_size}")
                except Exception as ex:
                    print(f"无法创建默认字体: {ex}")
            
        # 分割文本为多行并实现自动换行
        lines = text.strip().split('\n')
        
        # 实现自动换行功能
        wrapped_lines = []
        for line in lines:
            # 检查每行的宽度，如果超过subtitle_width则自动换行
            line_width = draw.textlength(line, font=font)
            
            if line_width <= subtitle_width:
                # 当前行宽度没有超过设定值，直接添加
                wrapped_lines.append(line)
            else:
                # 当前行宽度超过设定值，需要自动换行
                words = line.split(' ')  # 以空格分词
                current_line = ""
                
                for word in words:
                    # 尝试添加当前单词到当前行
                    test_line = current_line + (" " if current_line else "") + word
                    test_width = draw.textlength(test_line, font=font)
                    
                    if test_width <= subtitle_width:
                        # 添加单词后仍在宽度范围内
                        current_line = test_line
                    else:
                        # 添加单词后超过宽度，需要换行
                        if current_line:
                            wrapped_lines.append(current_line)
                            current_line = word
                        else:
                            # 单个单词就超过宽度，强制换行
                            wrapped_lines.append(word)
                            current_line = ""
                
                # 添加最后一行
                if current_line:
                    wrapped_lines.append(current_line)
        
        print(f"原始行数: {len(lines)}, 自动换行后行数: {len(wrapped_lines)}")
        print(f"字幕最大宽度设置: {subtitle_width}px")
        
        # 计算行高和总高度
        line_height = int(custom_font_size * 1.3)  # 增加行高系数，从1.1倍改为1.3倍，解决小字体时行间距过小的问题
        total_height = line_height * len(wrapped_lines)
        
        # 计算起始Y坐标，使文本垂直居中
        y_start = (height - total_height) // 2
        
        print(f"行高: {line_height}, 总高度: {total_height}, 起始Y: {y_start}")
        
        # 绘制每行文本
        for i, line in enumerate(wrapped_lines):
            # 计算文本宽度以居中
            text_width = draw.textlength(line, font=font)
            x = (width - text_width) // 2
            y = y_start + i * line_height
            
            print(f"行 {i+1}: 宽度={text_width}, X={x}, Y={y}")
            
            # 绘制阴影（如果启用）
            if shadow and shadow_offset:
                # 确保shadow_offset是数值类型
                if isinstance(shadow_offset, (list, tuple)) and len(shadow_offset) >= 2:
                    shadow_x = x + int(shadow_offset[0])
                    shadow_y = y + int(shadow_offset[1])
                else:
                    shadow_x = x + 4  # 默认偏移
                    shadow_y = y + 4
                draw.text((shadow_x, shadow_y), line, font=font, fill=shadow_color)
            
            # 创建一个临时图像用于描边
            stroke_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            stroke_draw = ImageDraw.Draw(stroke_img)
            
            # 确保stroke_width是整数类型
            stroke_width_int = int(stroke_width) if isinstance(stroke_width, (int, float)) else 2
            
            # 使用描边绘制文本
            for dx in range(-stroke_width_int, stroke_width_int + 1):
                for dy in range(-stroke_width_int, stroke_width_int + 1):
                    if dx*dx + dy*dy <= stroke_width_int*stroke_width_int:
                        stroke_draw.text((x + dx, y + dy), line, font=font, fill=stroke_color)
            
            # 将描边图像合并到主图像
            image = Image.alpha_composite(image, stroke_img)
            draw = ImageDraw.Draw(image)
            
            # 绘制主文本
            draw.text((x, y), line, font=font, fill=text_color)
        
        # 保存图片
        image.save(output_path)
        print(f"字幕图片已保存: {output_path}")
        
        return output_path
    except Exception as e:
        print(f"创建字幕图片失败: {e}")
        import traceback
        traceback.print_exc()
        return None


# 主函数用于测试
if __name__ == "__main__":
    # 如果有命令行参数，处理指定视频
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        output_path = None
        if len(sys.argv) > 2:
            output_path = sys.argv[2]
            
        process_video(video_path, output_path)
    else:
        # 否则批量处理所有视频
        batch_process_videos()
