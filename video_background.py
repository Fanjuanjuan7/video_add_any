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


def create_subtitle_image(text, style=None, width=1080, height=500, font_size=70, 
                         output_path=None, subtitle_width=500):
    """
    创建字幕图片
    
    参数:
        text: 字幕文本
        style: 字幕样式
        width: 图片宽度（视频宽度）
        height: 图片高度
        font_size: 字体大小
        output_path: 输出路径
        subtitle_width: 字幕最大宽度（用于自动换行）
        
    返回:
        字幕图片路径
    """
    try:
        print(f"🔧 创建字幕图片: 文本='{text}', 样式={style}, 宽度={width}, 高度={height}, 字体大小={font_size}")
        print(f"📏 字幕最大宽度: {subtitle_width}")
        
        # 检查文本是否包含中文或泰文
        is_chinese_text = any('\u4e00' <= char <= '\u9fff' for char in text)
        is_thai_text = any('\u0e00' <= char <= '\u0e7f' for char in text)
        print(f"🔤 文本类型: 中文={is_chinese_text}, 泰文={is_thai_text}")
        
        # 如果没有指定输出路径，生成一个临时文件
        if not output_path:
            import tempfile
            output_path = Path(tempfile.gettempdir()) / f"subtitle_{int(time.time())}.png"
            
        # 创建透明背景的图片，宽度为subtitle_width+一些边距，而不是整个视频宽度
        # 这样可以确保字幕图片的实际宽度与文本宽度匹配
        # 增加额外的边距以避免文本被截断，同时确保图片足够大以容纳所有文本
        image_width = min(width, max(subtitle_width + 200, 1200))  # 增加边距并设置最小宽度
        image_height = max(height, 600)  # 增加图片高度以确保有足够的垂直空间
        image = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
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
                    for section in style_config_parser.sections():  # type: ignore
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
        
        # 实现自动换行功能 - 改进版本，避免切断单词
        wrapped_lines = []
        for line in lines:
            # 检查每行的宽度，如果超过subtitle_width则自动换行
            line_width = draw.textlength(line, font=font)
            
            if line_width <= subtitle_width:
                # 当前行宽度没有超过设定值，直接添加
                wrapped_lines.append(line)
            else:
                # 当前行宽度超过设定值，需要自动换行
                # 改进的换行逻辑：避免切断单词
                words = line.split(' ')  # 以空格分词
                current_line = ""
                
                for i, word in enumerate(words):
                    # 尝试添加当前单词到当前行
                    test_line = current_line + (" " if current_line else "") + word
                    test_width = draw.textlength(test_line, font=font)
                    
                    if test_width <= subtitle_width:
                        # 添加单词后仍在宽度范围内
                        current_line = test_line
                    else:
                        # 添加单词后超过宽度，需要换行
                        if current_line:
                            # 如果当前行不为空，将当前行添加到结果中
                            wrapped_lines.append(current_line)
                            # 新的一行从当前单词开始
                            current_line = word
                        else:
                            # 如果当前行为空但单个单词就超过宽度，我们需要强制换行
                            # 按字符逐个添加直到达到宽度限制
                            char_line = ""
                            for char in word:
                                test_char_line = char_line + char
                                test_char_width = draw.textlength(test_char_line, font=font)
                                
                                if test_char_width <= subtitle_width:
                                    char_line = test_char_line
                                else:
                                    # 如果添加这个字符会超过宽度
                                    if char_line:  # 如果已经有字符了，换行
                                        wrapped_lines.append(char_line)
                                        char_line = char
                                    else:  # 如果第一个字符就超宽，强制添加
                                        char_line = char
                            
                            # 处理剩余的字符
                            if char_line:
                                current_line = char_line
                
                # 添加最后一行
                if current_line:
                    wrapped_lines.append(current_line)
        
        print(f"原始行数: {len(lines)}, 自动换行后行数: {len(wrapped_lines)}")
        print(f"字幕最大宽度设置: {subtitle_width}px")
        
        # 计算行高和总高度，增加额外空间确保文本完整显示
        line_height = int(custom_font_size * 1.5)  # 进一步增加行高系数，从1.3倍改为1.5倍
        total_height = line_height * len(wrapped_lines) + 100  # 增加额外的垂直空间
        
        # 计算起始Y坐标，使文本垂直居中，并增加顶部边距
        y_start = max(50, (image_height - total_height) // 2)  # 确保至少有50像素的顶部边距
        
        print(f"行高: {line_height}, 总高度: {total_height}, 起始Y: {y_start}")
        
        # 绘制每行文本
        for i, line in enumerate(wrapped_lines):
            # 计算文本宽度以居中
            text_width = draw.textlength(line, font=font)
            # 修改为左对齐，而不是居中对齐
            x = 80  # 增加左边距到80像素，提供更多空间
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
            
            # 创建一个临时图像用于描边，确保尺寸与主图像匹配
            stroke_img = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
            stroke_draw = ImageDraw.Draw(stroke_img)
            
            # 确保stroke_width是整数类型
            stroke_width_int = int(stroke_width) if isinstance(stroke_width, (int, float)) else 2
            
            # 使用描边绘制文本，增加描边范围以确保完整显示
            for dx in range(-stroke_width_int-3, stroke_width_int + 4):  # 增加描边范围
                for dy in range(-stroke_width_int-3, stroke_width_int + 4):  # 增加描边范围
                    if dx*dx + dy*dy <= (stroke_width_int+2)*(stroke_width_int+2):  # 调整描边范围计算
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