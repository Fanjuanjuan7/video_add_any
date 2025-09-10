#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频背景处理模块
负责创建背景、处理图像叠加等视觉效果
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path
import tempfile
import random
import time
from PIL import Image, ImageDraw, ImageFont
import uuid

# 导入工具函数
from utils import get_video_info, get_audio_duration, run_ffmpeg_command, get_data_path, ensure_dir, load_style_config, find_font_file, find_matching_image, generate_tts_audio, load_subtitle_config

# 导入日志管理器
from log_manager import init_logging, log_with_capture

# 初始化日志系统
log_manager = init_logging()


# 兼容旧接口的函数（如果需要）
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
        
        # 确保输出目录存在
        ensure_dir(Path(output_path).parent)
        
        # 保存处理后的图片
        new_img.save(output_path)
        
        # 验证处理后的图片
        processed_img = Image.open(output_path)
        print(f"【图片处理】验证处理后图片大小: {processed_img.size}")
        
        return output_path
    except Exception as e:
        print(f"处理图片时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

