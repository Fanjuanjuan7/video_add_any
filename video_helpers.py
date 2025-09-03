#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理辅助函数模块
提供视频处理过程中需要的辅助功能函数
"""

import pandas as pd
from pathlib import Path
import sys

def load_subtitle_config(document_path=None):
    """加载字幕配置"""
    subtitle_df = None
    
    # 如果提供了文档路径且文件存在，加载用户指定的文档
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
    
    # 如果没有加载到用户文档，尝试加载默认的字幕配置
    if subtitle_df is None:
        try:
            # 导入工具函数
            from utils import load_subtitle_config as load_default_config
            subtitle_df = load_default_config()
            if subtitle_df is not None and not subtitle_df.empty:
                print(f"成功加载默认字幕配置: {len(subtitle_df)} 条记录")
            else:
                print("默认字幕配置为空或不存在")
        except Exception as e:
            print(f"加载默认字幕配置失败: {e}")
    
    return subtitle_df


def get_tts_text_for_video(subtitle_df, language, video_index=0):
    """
    根据视频索引获取对应的TTS文本
    
    参数:
        subtitle_df: 字幕配置DataFrame
        language: 语言选择 (chinese, malay, thai)
        video_index: 视频索引（从0开始）
        
    返回:
        对应视频的TTS文本
    """
    if subtitle_df is None or subtitle_df.empty:
        print("字幕配置为空")
        return ""
    
    # 定义语言到列名的映射
    lang_to_column = {
        "chinese": "cn_prompt",
        "malay": "malay_prompt", 
        "thai": "thai_prompt"
    }
    
    # 获取对应的列名
    column_name = lang_to_column.get(language, "cn_prompt")
    print(f"获取TTS文本: 语言={language}, 列名={column_name}, 视频索引={video_index}")
    
    # 检查列是否存在
    if column_name not in subtitle_df.columns:
        print(f"列 '{column_name}' 不存在于字幕配置中")
        return ""
    
    # 获取有效的文本数据
    valid_texts = subtitle_df[subtitle_df[column_name].notna() & (subtitle_df[column_name] != "")]
    
    if valid_texts.empty:
        print(f"列 '{column_name}' 中没有有效数据")
        return ""
    
    # 如果视频索引超出范围，使用最后一个可用的文本
    if video_index >= len(valid_texts):
        video_index = len(valid_texts) - 1
        print(f"视频索引超出范围，使用最后一个文本: 索引={video_index}")
    
    # 获取对应索引的文本
    tts_text = str(valid_texts.iloc[video_index][column_name])
    print(f"获取到TTS文本: {tts_text}")
    
    return tts_text


def process_style_and_language(style, subtitle_lang):
    """处理样式和语言选择"""
    # 如果是"random"样式，先随机选择一个实际样式
    if style == "random":
        # 从配置文件中动态获取所有可用的样式
        from utils import load_style_config
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
                import random
                style = random.choice(chinese_styles)
                print(f"中文语言，优先选择中文样式: {style}")
            else:
                # 如果没有中文样式，使用常规样式
                import random
                style = random.choice(available_styles)
                print(f"中文语言但无中文样式，使用常规样式: {style}")
        else:
            # 非中文语言，优先使用非中文样式
            regular_styles = [s for s in available_styles if 'chinese' not in s]
            if regular_styles:
                import random
                style = random.choice(regular_styles)
                print(f"非中文语言，选择非中文样式: {style}")
            else:
                # 如果没有非中文样式，使用默认样式
                import random
                style = random.choice(available_styles)
                print(f"非中文语言但无非中文样式，使用常规样式: {style}")
        
    if subtitle_lang is None:
        import random
        available_langs = ["chinese", "malay", "thai"]
        subtitle_lang = random.choice(available_langs)
        print(f"随机选择语言: {subtitle_lang}")
    
    return style, subtitle_lang


def process_random_position(random_position, subtitle_x, subtitle_y, subtitle_text_x, subtitle_text_y, subtitle_width):
    """处理随机位置逻辑"""
    if random_position:
        import random
        # 定义随机区域边界（基于统一坐标系统1080x1920）
        # 用户指定的固定字幕区域：左上角(50,200)到右下角(1030,1720)
        # 注意：1080宽度，左右各留50边距，所以右边界是1030
        # 1920高度，上下边距分别为200和顶边距，底边距为200
        region_left = 50     # 区域左边界
        region_top = 200     # 区域上边界  
        region_right = 1030  # 区域右边界 (1080-50)
        region_bottom = 1720 # 区域下边界 (1920-200)
        
        # 直接使用GUI中的字幕宽度参数，将字幕左上角作为位置参考点
        # X坐标范围：从区域左边界到（区域右边界 - 字幕宽度）
        min_x = region_left
        max_x = region_right - subtitle_width
        # Y坐标范围：从区域上边界到（区域下边界 - 一个合理的高度估算，比如200像素）
        min_y = region_top
        max_y = region_bottom - 200  # 估算字幕高度为200像素
        
        # 确保范围有效
        min_x = max(min_x, 0)
        max_x = max(max_x, min_x)  # 确保max_x不小于min_x
        min_y = max(min_y, 0)
        max_y = max(max_y, min_y)  # 确保max_y不小于min_y
        
        # 生成随机位置（字幕左上角坐标）
        new_subtitle_text_x = random.randint(min_x, max_x)
        new_subtitle_text_y = random.randint(min_y, max_y)
        
        print(f"🎲 随机字幕位置: 原始({subtitle_text_x}, {subtitle_text_y}) -> 随机({new_subtitle_text_x}, {new_subtitle_text_y})")
        print(f"📎 随机范围: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
        print(f"📐 字幕区域: 左上角({region_left}, {region_top}) -> 右下角({region_right}, {region_bottom})")
        print(f"📏 字幕尺寸: 宽={subtitle_width}, 高=200(估算)")
        
        # 更新位置参数
        subtitle_text_x = new_subtitle_text_x
        subtitle_text_y = new_subtitle_text_y
    
    return subtitle_text_x, subtitle_text_y


def process_image_matching(video_name, image_dir="input/images", custom_image_path=None):
    """处理图片匹配逻辑"""
    try:
        print(f"查找匹配图片: 视频名={video_name}, 图片目录={image_dir}")
        
        # 如果提供了自定义图片路径，直接使用
        if custom_image_path and Path(custom_image_path).exists():
            print(f"使用自定义图片路径: {custom_image_path}")
            full_image_dir = custom_image_path
        else:
            # 尝试不同的图片目录路径
            from utils import get_data_path
            videoapp_dir_path = Path.cwd() / "VideoApp/input/images"
            current_dir_path = Path.cwd() / "input/images"
            
            if videoapp_dir_path.exists():
                full_image_dir = str(videoapp_dir_path)
                print(f"使用VideoApp图片目录: {full_image_dir}")
            elif current_dir_path.exists():
                full_image_dir = str(current_dir_path)
                print(f"使用当前目录图片目录: {full_image_dir}")
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


def process_gif(gif_path, temp_dir, scale_factor=1.0, loop_count=-1, video_duration=None):
    """处理GIF逻辑"""
    try:
        if not Path(gif_path).exists():
            print(f"GIF文件不存在: {gif_path}")
            return None
        
        # 输出路径
        from pathlib import Path
        processed_gif_path = Path(temp_dir) / "processed_animated_gif.gif"
        
        # 如果提供了视频时长，计算需要的循环次数
        if video_duration is not None:
            # 获取原始GIF的持续时间
            import subprocess
            gif_info_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', str(gif_path)
            ]
            
            try:
                result = subprocess.run(gif_info_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                gif_duration = float(result.stdout.decode().strip())
                print(f"原始GIF时长: {gif_duration} 秒")
                
                # 计算需要循环的次数
                if gif_duration > 0:
                    required_loops = int(video_duration / gif_duration) + 1
                    print(f"视频时长: {video_duration} 秒，需要循环 {required_loops} 次")
                else:
                    required_loops = 10  # 默认循环10次
                    
            except Exception as e:
                print(f"获取GIF信息失败，使用默认循环次数: {e}")
                required_loops = 10
        else:
            required_loops = 10  # 默认循环10次
            
        # 构建FFmpeg命令来处理GIF，保持动画特性
        import subprocess
        gif_cmd = [
            'ffmpeg', '-y',
            '-stream_loop', str(required_loops),  # 循环播放
            '-i', str(gif_path)
        ]
        
        # 如果提供了视频时长，限制GIF时长
        if video_duration is not None:
            gif_cmd.extend(['-t', str(video_duration)])
        
        # 添加缩放过滤器（如果需要）
        filters = []
        if scale_factor != 1.0:
            filters.append(f"scale=iw*{scale_factor}:ih*{scale_factor}")
        
        # 添加GIF处理过滤器，保持动画
        if filters:
            filter_str = ",".join(filters)
            gif_cmd.extend([
                '-vf', f'{filter_str},split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128'
            ])
        else:
            gif_cmd.extend([
                '-vf', 'split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128'
            ])
        
        # 设置循环参数
        if loop_count == -1:
            gif_cmd.extend(['-loop', '0'])  # 无限循环
        else:
            gif_cmd.extend(['-loop', str(loop_count)])
        
        gif_cmd.extend([
            '-f', 'gif',
            str(processed_gif_path)
        ])
        
        print(f"【GIF动画处理】执行命令: {' '.join(gif_cmd)}")
        
        result = subprocess.run(gif_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"【GIF动画处理】处理成功: {processed_gif_path}")
        return str(processed_gif_path)
        
    except subprocess.CalledProcessError as e:
        print(f"【GIF动画处理】处理失败: {e}")
        print(f"stderr: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"【GIF动画处理】处理异常: {e}")
        return None