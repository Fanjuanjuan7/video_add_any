#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理辅助函数模块
将复杂的add_subtitle_to_video函数分解为多个小函数
"""

import subprocess
import random
import tempfile
from pathlib import Path
from PIL import Image
import pandas as pd

# 导入工具函数
from utils import get_video_info, run_ffmpeg_command, get_data_path, load_style_config, find_font_file, find_matching_image
from log_manager import log_with_capture


def load_subtitle_config(document_path):
    """加载字幕配置"""
    subtitle_df = None
    
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
    
    return subtitle_df


def process_style_and_language(style, subtitle_lang):
    """处理样式和语言选择"""
    # 如果是"random"样式，先随机选择一个实际样式
    if style == "random":
        # 从配置文件中动态获取所有可用的样式
        style_config_parser = load_style_config()
        available_styles = []
        
        try:
            # 检查style_config_parser是否有sections方法
            if hasattr(style_config_parser, 'sections') and callable(getattr(style_config_parser, 'sections', None)):
                # ConfigParser 对象
                sections = style_config_parser.sections()  # type: ignore
                for section in sections:
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
    
    return style, subtitle_lang


def process_random_position(random_position, subtitle_text_x, subtitle_text_y, subtitle_width):
    """处理随机位置逻辑"""
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
        new_subtitle_text_x = random.randint(int(min_x), int(max_x))
        new_subtitle_text_y = random.randint(int(min_y), int(max_y))
        
        print(f"🎲 随机字幕位置: 原始({subtitle_text_x}, {subtitle_text_y}) -> 随机({new_subtitle_text_x}, {new_subtitle_text_y})")
        print(f"📎 边界检查: X范围[{min_x}, {max_x}], Y范围[{min_y}, {max_y}]")
        print(f"📐 字幕区域: 左上角({region_left}, {region_top}) -> 右下角({region_right}, {region_bottom})")
        print(f"📏 字幕宽度: 设定={subtitle_width}, 估算={estimated_subtitle_width}")
        print(f"🖥️ 区域尺寸: {region_right - region_left}x{region_bottom - region_top}, 可用X范围: {max_x - min_x}")
        
        # 更新位置参数
        subtitle_text_x = new_subtitle_text_x
        subtitle_text_y = new_subtitle_text_y
    else:
        print(f"📍 使用固定字幕位置: ({subtitle_text_x}, {subtitle_text_y})")
    
    return subtitle_text_x, subtitle_text_y


def process_image_matching(enable_image, original_video_path, video_path, image_path, temp_dir, img_size):
    """处理图片匹配"""
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
        # 处理图片
        print(f"【图片流程】处理图片 {final_image_path}，大小设置为 {img_size}x{img_size}")
        processed_img_path = temp_dir / "processed_image.png"
        # 导入处理函数
        from video_core import process_image_for_overlay
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
        image_dir_path = Path(image_dir)
        if enable_image and image_dir_path.exists():
            print(f"图片目录存在: {image_dir}")
            # 列出目录中的文件
            try:
                image_files = [f.name for f in image_dir_path.iterdir() if f.is_file()]
                print(f"图片目录中的文件数量: {len(image_files)}")
                if image_files:
                    print(f"图片目录中的文件: {image_files[:5]}{'...' if len(image_files) > 5 else ''}")
            except Exception as e:
                print(f"列出图片目录文件时出错: {e}")
        elif enable_image:
            print(f"图片目录不存在: {image_dir}")
        
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
                    # 导入处理函数
                    from video_core import process_image_for_overlay
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
    
    return has_image, final_image_path, processed_img_path


def process_gif(enable_gif, gif_path, temp_dir, gif_scale, gif_loop_count, duration, gif_x, gif_y):
    """处理GIF"""
    has_gif = False
    processed_gif_path = None
    
    if enable_gif and gif_path and Path(gif_path).exists():
        print(f"【GIF流程】处理GIF {gif_path}，缩放系数: {gif_scale}，位置: ({gif_x}, {gif_y})，循环次数: {gif_loop_count}")
        
        # 检查文件格式
        file_ext = Path(gif_path).suffix.lower()
        if file_ext in ['.gif', '.webp']:
            # 使用改进的GIF处理函数，传递视频时长确保GIF持续整个视频时长
            # 导入处理函数
            from video_core import process_animated_gif_for_video
            processed_gif_path = process_animated_gif_for_video(gif_path, temp_dir, gif_scale, gif_loop_count, duration)
            
            if processed_gif_path:
                has_gif = True
                print(f"【GIF流程】GIF处理成功: {processed_gif_path}")
            else:
                print(f"【GIF流程】GIF处理失败")
        else:
            print(f"【GIF流程】不支持的文件格式: {file_ext}")
    else:
        if not enable_gif:
            print("GIF功能已禁用")
        elif not gif_path:
            print("未指定GIF路径")
        else:
            print(f"GIF文件不存在: {gif_path}")
    
    return has_gif, processed_gif_path