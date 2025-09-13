#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频字幕处理器模块
负责处理视频中的字幕添加、样式设置等，重构自旧版video_subtitle.py中的复杂函数
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path
import tempfile
import random
import pandas as pd
import time
import logging
import uuid

# 导入工具函数
from utils import get_video_info, get_audio_duration, run_ffmpeg_command, get_data_path, ensure_dir, load_style_config, find_font_file, find_matching_image, generate_tts_audio, load_subtitle_config

# 导入日志管理器
from log_manager import init_logging, log_with_capture

# 导入其他模块
from video_background import create_rounded_rect_background, process_image_for_overlay
from video_audio import trim_music_to_video_duration, add_tts_audio_to_video, generate_subtitle_tts
# 导入新的字幕模块
from static_subtitle import StaticSubtitleProcessor
from animated_subtitle import AnimatedSubtitleProcessor, DynamicSubtitleProcessor

# 初始化日志系统
log_manager = init_logging()


class VideoSubtitleProcessor:
    """视频字幕处理器类"""
    
    def __init__(self):
        """初始化处理器"""
        pass
    
    @log_with_capture
    def add_subtitle_to_video(self, video_path, output_path, style=None, subtitle_lang=None, 
                            original_video_path=None, quicktime_compatible=False, 
                            img_position_x=100, img_position_y=0, font_size=70, 
                            subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                            subtitle_text_x=0, subtitle_text_y=1190, random_position=False, enable_subtitle=True,
                            enable_background=True, enable_image=True, enable_music=False, music_path="",
                            music_mode="single", music_volume=50, document_path=None, enable_gif=False, 
                            gif_path="", gif_loop_count=-1, gif_scale=1.0, gif_rotation=0, gif_x=800, gif_y=100, scale_factor=1.1, 
                            image_path=None, subtitle_width=500, quality_settings=None, progress_callback=None,
                            video_index=0, enable_dynamic_subtitle=False, animation_style="高亮放大", 
                            animation_intensity=1.5, highlight_color="#FFD700", match_mode="随机样式", 
                            position_x=540, position_y=960,
                            # 新增的动态字幕参数
                            dynamic_font_size=70, dynamic_font_color="#FFFFFF", dynamic_outline_size=2, 
                            dynamic_outline_color="#000000", animation_duration=0.3, opacity=100):
        """
        添加字幕到视频（重构版本）
        
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
            subtitle_text_x: 字幕文字X轴绝对坐标（像素）
            subtitle_text_y: 字幕文字Y轴绝对坐标（像素）
            random_position: 是否启用随机位置
            enable_subtitle: 是否启用字幕
            enable_background: 是否启用背景
            enable_image: 是否启用图片
            enable_music: 是否启用背景音乐
            music_path: 音乐文件或文件夹路径
            music_mode: 音乐匹配模式（single/order/random）
            music_volume: 音量百分比（0-100）
            document_path: 用户选择的文档文件路径，如果为None则使用默认的subtitle.csv
            enable_gif: 是否启用GIF动画
            gif_path: GIF文件路径
            gif_loop_count: GIF循环次数
            gif_scale: GIF缩放系数
            gif_rotation: GIF旋转角度
            gif_x: GIF水平位置
            gif_y: GIF垂直位置
            scale_factor: 视频缩放系数（用于去水印）
            image_path: 图片文件夹路径
            subtitle_width: 字幕最大宽度（像素）
            quality_settings: 导出质量设置
            progress_callback: 进度回调函数，用于报告处理进度
            video_index: 视频索引（用于匹配文档数据和音乐）
            enable_dynamic_subtitle: 是否启用动态字幕
            animation_style: 动画样式
            animation_intensity: 动画强度
            highlight_color: 高亮颜色
            match_mode: 匹配模式
            position_x: 字幕位置X坐标
            position_y: 字幕位置Y坐标
            dynamic_font_size: 动态字幕字体大小
            dynamic_font_color: 动态字幕字体颜色
            dynamic_outline_size: 动态字幕描边大小
            dynamic_outline_color: 动态字幕描边颜色
            animation_duration: 动画持续时间
            opacity: 透明度
            
        返回:
            处理后的视频路径
        """
        # 创建临时目录
        temp_dir = Path(tempfile.mkdtemp())
        print(f"使用临时目录: {temp_dir}")
        
        try:
            # 1. 参数预处理和初始化
            if progress_callback:
                progress_callback("开始处理视频", 5.0)
                
            params = self._initialize_params(
                video_path, output_path, style, subtitle_lang, original_video_path, quicktime_compatible,
                img_position_x, img_position_y, font_size, subtitle_x, subtitle_y, bg_width, bg_height, img_size,
                subtitle_text_x, subtitle_text_y, random_position, enable_subtitle, enable_background, enable_image,
                enable_music, music_path, music_mode, music_volume, document_path, enable_gif, gif_path,
                gif_loop_count, gif_scale, gif_rotation, gif_x, gif_y, scale_factor, image_path, subtitle_width,
                quality_settings, progress_callback, video_index, enable_dynamic_subtitle, animation_style,
                animation_intensity, highlight_color, match_mode, position_x, position_y
            )
            
            # 2. 获取视频信息
            video_info = self._get_video_info(video_path, progress_callback)
            if not video_info:
                return None
            
            width, height, duration = video_info
            
            # 3. 加载字幕配置
            subtitle_df = self._load_subtitle_config(document_path, enable_subtitle, progress_callback)
            
            # 4. 处理动态字幕
            dynamic_processor = self._process_dynamic_subtitle(enable_dynamic_subtitle, enable_subtitle, 
                                                             animation_style, animation_intensity, highlight_color,
                                                             match_mode, position_x, position_y, font_size,
                                                             font_color="#FFFFFF", outline_size=2, outline_color="#000000",
                                                             animation_duration=0.3, opacity=100)
            
            # 5. 处理随机位置
            if enable_subtitle:
                subtitle_text_x, subtitle_text_y = self._process_random_position(
                    random_position, subtitle_x, subtitle_y, subtitle_text_x, subtitle_text_y, subtitle_width, width, height, enable_subtitle
                )
            
            # 6. 处理图片素材
            has_image, final_image_path, processed_img_path = self._process_image(
                enable_image, original_video_path, video_path, image_path, img_size, temp_dir, progress_callback
            )
            
            # 7. 处理GIF素材
            has_gif, processed_gif_path = self._process_gif(
                enable_gif, gif_path, temp_dir, gif_scale, gif_loop_count, duration, gif_rotation, progress_callback, gif_x, gif_y
            )
            
            # 8. 处理字幕素材
            subtitle_img, bg_img, subtitle_ass_path, use_ass_subtitle = self._process_subtitle_materials(  # 修改返回值
                enable_subtitle, subtitle_df, subtitle_lang, video_index, style, font_size, subtitle_width,
                bg_width, bg_height, temp_dir, dynamic_processor, progress_callback, enable_background, width, height
            )
            
            # 9. 处理音乐
            selected_music_path = self._process_music(
                enable_music, music_path, music_mode, video_index, duration, temp_dir, progress_callback
            )
            
            # 10. 构建和执行FFmpeg命令
            result = self._process_with_ffmpeg(
                video_path, output_path, temp_dir, width, height, duration,
                enable_subtitle, enable_background, enable_image, enable_gif, enable_music,
                subtitle_img, bg_img, processed_img_path, processed_gif_path, selected_music_path,
                has_image, has_gif,
                img_position_x, img_position_y, img_size,
                subtitle_text_x, subtitle_text_y, subtitle_text_y,
                bg_width, bg_height, subtitle_x, subtitle_y,
                gif_x, gif_y,
                music_volume, quality_settings, quicktime_compatible,
                progress_callback, selected_music_path is not None,
                subtitle_ass_path, use_ass_subtitle  # 传递ASS字幕相关信息
            )
            
            if result:
                if progress_callback:
                    progress_callback("处理完成", 100.0)
                return output_path
            else:
                return None
                
        except Exception as e:
            print(f"处理视频时出错: {e}")
            import traceback
            traceback.print_exc()
            
            if progress_callback:
                progress_callback(f"处理失败: {str(e)}", 0.0)
            return None
        finally:
            # 清理临时文件
            try:
                if 'temp_dir' in locals() and temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    print(f"已清理临时目录: {temp_dir}")
            except Exception as e:
                print(f"清理临时目录失败: {e}")
    
    def _initialize_params(self, video_path, output_path, style, subtitle_lang, original_video_path,
                          quicktime_compatible, img_position_x, img_position_y, font_size, subtitle_x,
                          subtitle_y, bg_width, bg_height, img_size, subtitle_text_x, subtitle_text_y,
                          random_position, enable_subtitle, enable_background, enable_image, enable_music,
                          music_path, music_mode, music_volume, document_path, enable_gif, gif_path,
                          gif_loop_count, gif_scale, gif_rotation, gif_x, gif_y, scale_factor, image_path,
                          subtitle_width, quality_settings, progress_callback, video_index,
                          enable_dynamic_subtitle, animation_style, animation_intensity, highlight_color,
                          match_mode, position_x, position_y):
        """初始化参数"""
        params = {
            'video_path': video_path,
            'output_path': output_path,
            'style': style,
            'subtitle_lang': subtitle_lang,
            'original_video_path': original_video_path,
            'quicktime_compatible': quicktime_compatible,
            'img_position_x': img_position_x,
            'img_position_y': img_position_y,
            'font_size': font_size,
            'subtitle_x': subtitle_x,
            'subtitle_y': subtitle_y,
            'bg_width': bg_width,
            'bg_height': bg_height,
            'img_size': img_size,
            'subtitle_text_x': subtitle_text_x,
            'subtitle_text_y': subtitle_text_y,
            'random_position': random_position,
            'enable_subtitle': enable_subtitle,
            'enable_background': enable_background,
            'enable_image': enable_image,
            'enable_music': enable_music,
            'music_path': music_path,
            'music_mode': music_mode,
            'music_volume': music_volume,
            'document_path': document_path,
            'enable_gif': enable_gif,
            'gif_path': gif_path,
            'gif_loop_count': gif_loop_count,
            'gif_scale': gif_scale,
            'gif_rotation': gif_rotation,
            'gif_x': gif_x,
            'gif_y': gif_y,
            'scale_factor': scale_factor,
            'image_path': image_path,
            'subtitle_width': subtitle_width,
            'quality_settings': quality_settings,
            'progress_callback': progress_callback,
            'video_index': video_index,
            'enable_dynamic_subtitle': enable_dynamic_subtitle,
            'animation_style': animation_style,
            'animation_intensity': animation_intensity,
            'highlight_color': highlight_color,
            'match_mode': match_mode,
            'position_x': position_x,
            'position_y': position_y
        }
        
        # 添加背景音乐详细日志
        print(f"[背景音乐日志] add_subtitle_to_video函数接收参数:")
        print(f"  - 视频路径: {video_path}")
        print(f"  - 输出路径: {output_path}")
        print(f"  - 视频索引: {video_index}")
        print(f"  - 启用背景音乐: {enable_music}")
        print(f"  - 音乐路径: '{music_path}'")
        print(f"  - 音乐模式: {music_mode}")
        print(f"  - 音乐音量: {music_volume}%")
        
        # 验证音乐文件路径
        if enable_music:
            if not music_path:
                print(f"[背景音乐日志] add_subtitle_to_video警告: 启用了背景音乐但音乐路径为空")
            else:
                music_file_path = Path(music_path)
                if music_file_path.exists():
                    print(f"[背景音乐日志] add_subtitle_to_video确认音乐文件存在: {music_file_path.absolute()}")
                    print(f"[背景音乐日志] 音乐文件大小: {music_file_path.stat().st_size} 字节")
                else:
                    print(f"[背景音乐日志] add_subtitle_to_video错误: 音乐文件不存在: {music_file_path.absolute()}")
        else:
            print(f"[背景音乐日志] add_subtitle_to_video: 背景音乐功能未启用")
            
        return params
    
    def _get_video_info(self, video_path, progress_callback):
        """获取视频信息"""
        if progress_callback:
            progress_callback("获取视频信息", 10.0)
            
        video_info = get_video_info(video_path)
        if not video_info:
            print("无法获取视频信息")
            return None
            
        width, height, duration = video_info
        print(f"视频信息: {width}x{height}, {duration}秒")
        return video_info
    
    def _load_subtitle_config(self, document_path, enable_subtitle, progress_callback):
        """加载字幕配置"""
        if progress_callback:
            progress_callback("加载字幕配置", 15.0)
            
        subtitle_df = None
        
        # 尝试加载用户指定的文档
        if enable_subtitle and document_path and Path(document_path).exists():
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
                print(f"โหลด用户เอกสาร失败: {e}")
                subtitle_df = None
        
        # 如果没有加载到用户文档，尝试加载默认的字幕配置
        if enable_subtitle and subtitle_df is None:
            try:
                # 加载默认的字幕配置ไฟล์
                subtitle_df = load_subtitle_config()
                if subtitle_df is not None and not subtitle_df.empty:
                    print(f"成功โหลด默认字บรรณ์การกำหนด: {len(subtitle_df)} รายการ")
                    print(f"ชื่อคอลัมน์การกำหนดเริ่มต้น: {list(subtitle_df.columns)}")
                else:
                    print("การกำหนดเริ่มต้นของคำบรรณ์หรือไม่มีอยู่")
                    # สร้างการกำหนดเริ่มต้นที่ง่าย
                    default_data = {
                        'name': ['default'],
                        'title': ['特价โปรโมชั่น\nสั่งซื้อตอนนี้ได้รับส่วนลด'],
                        'cn_prompt': ['特价โปรโมชั่น\nสั่งซื้อตอนนี้ได้รับส่วนลด'],
                        'malay_prompt': ['Promosi khasiat\nBeli sekarang dapat diskon'],
                        'thai_prompt': ['โปรโมชั่นพิเศษ\nสั่งซื้อตอนนี้ได้รับส่วนลด']
                    }
                    subtitle_df = pd.DataFrame(default_data)
                    print("ใช้ข้อมูลตัวอย่างสำหรับการทดสอบ")
            except Exception as e:
                print(f"โหลดการกำหนดเริ่มต้นของคำบรรณ์ไม่สำเร็จ: {e}")
                # สร้างการกำหนดเริ่มต้นที่ง่าย
                default_data = {
                    'name': ['default'],
                    'title': ['特价โปรโมชั่น\nสั่งซื้อตอนนี้ได้รับส่วนลด'],
                    'cn_prompt': ['特价โปรโมชั่น\nสั่งซื้อตอนนี้ได้รับส่วนลด'],
                    'malay_prompt': ['Promosi khasiat\nBeli sekarang dapat diskon'],
                    'thai_prompt': ['โปรโมชั่นพิเศษ\nสั่งซื้อตอนนี้ได้รับส่วนลด']
                }
                subtitle_df = pd.DataFrame(default_data)
                print("ใช้ข้อมูลตัวอย่างสำหรับการทดสอบ")
        
        return subtitle_df
    
    def _process_dynamic_subtitle(self, enable_dynamic_subtitle, enable_subtitle, animation_style,
                                animation_intensity, highlight_color, match_mode, position_x, position_y, font_size,
                                font_color="#FFFFFF", outline_size=2, outline_color="#000000", 
                                animation_duration=0.3, opacity=100):
        """处理动态字幕"""
        dynamic_processor = None
        
        # 检查是否启用动态字幕（修复：动态字幕可以独立启用，不依赖enable_subtitle）
        if enable_dynamic_subtitle:
            print(f"[动态字幕] 启用动态字幕功能")
            print(f"[动态字幕] 动画样式: {animation_style}")
            print(f"[动态字幕] 动画强度: {animation_intensity}")
            print(f"[动态字幕] 高亮颜色: {highlight_color}")
            print(f"[动态字幕] 匹配模式: {match_mode}")
            print(f"[动态字幕] 位置坐标: ({position_x}, {position_y})")
            print(f"[动态字幕] 字体大小: {font_size}")
            print(f"[动态字幕] 字体颜色: {font_color}")
            print(f"[动态字幕] 描边大小: {outline_size}")
            print(f"[动态字幕] 描边颜色: {outline_color}")
            print(f"[动态字幕] 动画时长: {animation_duration}")
            print(f"[动态字幕] 透明度: {opacity}")
            
            try:
                dynamic_processor = DynamicSubtitleProcessor(
                    animation_style=animation_style,
                    animation_intensity=animation_intensity,
                    highlight_color=highlight_color,
                    match_mode=match_mode,
                    position_x=position_x,
                    position_y=position_y,
                    font_size=font_size,
                    font_color=font_color,
                    outline_size=outline_size,
                    outline_color=outline_color,
                    animation_duration=animation_duration,
                    opacity=opacity
                )
                print(f"[动态字幕] 动态字幕处理器创建成功")
            except ImportError as e:
                print(f"[动态字幕] 模块导入失败: {e}")
            except Exception as e:
                print(f"[动态字幕] 处理器创建失败: {e}")
                import traceback
                traceback.print_exc()
        
        return dynamic_processor

    def _process_random_position(self, random_position, subtitle_x, subtitle_y, subtitle_text_x, subtitle_text_y, subtitle_width, width, height, enable_subtitle):
        """处理随机位置逻辑"""
        # 如果启用了随机位置且启用了字幕，则处理随机位置
        if random_position and enable_subtitle:
            import random
            # 定义随机区域边界（基于统一坐标系统1080x1920）
            # 用户指定的固定字幕区域：左上角(50,200)到右下角(1030,1720)
            # 注意：1080宽度，左右各留50边距，所以右边界是1030
            # 1920高度，上下边距分别为200和顶边距，底边距为200
            region_left = 50     # 区域左边界
            region_top = 200     # 区역上边界  
            region_right = 1030  # 区역ขวา (1080-50)
            region_bottom = 1720 # 区역ล่าง (1920-200)
            
            # 直接ใช้GUIของคำบรรณ์ความกว้างดังกล่าวเป็นพารามิเตอร์สำหรับตำแหน่งเริ่มต้น
            # ช่วง X: จากขอบเขตซ้ายไปจนถึง (ขอบเขตขวา - ความกว้างคำบรรณ์)
            min_x = region_left
            max_x = region_right - subtitle_width
            # ช่วง Y: จากขอบเขตบนไปจนถึง (ขอบเขตล่าง - ความสูงคำบรรณ์ที่เราประเมินว่าเป็น 200 พิกเซล)
            min_y = region_top
            max_y = region_bottom - 200  # ประเมินความสูงคำบรรณ์ว่าเป็น 200 พิกเซล
            
            # ตรวจสอบช่วงว่ามีความถูกต้องหรือไม่
            min_x = max(min_x, 0)
            max_x = max(max_x, min_x)  # ตรวจสอบว่า max_x ไม่ต่ำกว่า min_x
            min_y = max(min_y, 0)
            max_y = max(max_y, min_y)  # ตรวจสอบว่า max_y ไม่ต่ำกว่า min_y
            
            # สุ่มตำแหน่ง (พิกเซลบนซ้ายของคำบรรณ์)
            new_subtitle_text_x = random.randint(min_x, max_x)
            new_subtitle_text_y = random.randint(min_y, max_y)
            
            print(f"🎲 สุ่มตำแหน่งคำบรรณ์: เริ่มต้น({subtitle_text_x}, {subtitle_text_y}) -> สุ่ม({new_subtitle_text_x}, {new_subtitle_text_y})")
            print(f"📎 สุ่มพิมพ์: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
            print(f"📐 พื้นที่คำบรรณ์: จุดบนซ้าย({region_left}, {region_top}) -> จุดล่างขวา({region_right}, {region_bottom})")
            print(f"📏 ขนาดคำบรรณ์: ความกว้าง={subtitle_width}, ความสูง=200(ประเมิน)")
            
            # อัปเดตพารามิเตอร์ตำแหน่ง
            subtitle_text_x = new_subtitle_text_x
            subtitle_text_y = new_subtitle_text_y
        
        return subtitle_text_x, subtitle_text_y

    def _process_image(self, enable_image, original_video_path, video_path, image_path, img_size, temp_dir, progress_callback):
        """处理图片素材"""
        if progress_callback:
            progress_callback("处理图片素材", 25.0)
            
        has_image = False
        final_image_path = None
        processed_img_path = None
        
        print(f"🎬 【素材状态调试】图片功能启用状态: {enable_image}")
        print(f"🎬 【素材状态调试】用户指定图片路径: {image_path}")
        print(f"🎬 【素材状态调试】原始视频路径: {original_video_path}")
        print(f"🎬 【素材状态调试】当前视频路径: {video_path}")
        
        if enable_image:
            print("📁 图片功能已启用，开始查找匹配图片...")
            
            # 使用原始视频路径查找匹配图片（如果有）
            if original_video_path:
                original_video_name = Path(original_video_path).stem
                print(f"📁 使用原始视频名查找图片: {original_video_name}")
                final_image_path = find_matching_image(original_video_name, custom_image_path=image_path)
                print(f"📁 find_matching_image返回结果: {final_image_path}")
                
            # 如果没有找到，使用当前视频路径
            if not final_image_path:
                video_name = Path(video_path).stem
                print(f"📁 使用当前视频名查找图片: {video_name}")
                final_image_path = find_matching_image(video_name, custom_image_path=image_path)
                print(f"📁 find_matching_image返回ผล: {final_image_path}")
            
            print(f"📁 最终图片路径: {final_image_path}")
            
            if final_image_path:
                print(f"✅ 找到匹配的图片: {final_image_path}")
                # ตรวจสอบว่าไฟล์ภาพมีอยู่จริง
                if Path(final_image_path).exists():
                    print(f"✅ ไฟล์ภาพมีอยู่จริง: {final_image_path}")
                else:
                    print(f"❌ ไฟล์ภาพไม่มีอยู่: {final_image_path}")
                    final_image_path = None
            else:
                print("⚠️ ไม่พบภาพที่ตรงกัน")
        else:
            print("❌ 图片功能ได้ถูกปิดใช้งาน ข้ามการค้นหาภาพ")
            
        if final_image_path and enable_image:
            print(f"✅ พบภาพที่ตรงกัน: {final_image_path}")
            # ประมวลผลภาพ
            print(f"【ภาพกระบวนการ】เริ่มประมวลผลภาพ {final_image_path} โดยตั้งขนาดเป็น {img_size}x{img_size}")
            processed_img_path = temp_dir / "processed_image.png"
            print(f"【ภาพกระบวนการ】เส้นทางประมวลผลภาพชั่วคราว: {processed_img_path}")
            
            # เรียกใช้ฟังก์ชันประมวลผลภาพ
            print(f"【ภาพกระบวนการ】เรียกใช้พารามิเตอร์ process_image_for_overlay: input={final_image_path}, output={processed_img_path}, size=({img_size}, {img_size})")
            processed_img = process_image_for_overlay(
                final_image_path,
                str(processed_img_path),
                size=(img_size, img_size)
            )
            print(f"【ภาพกระบวนการ】process_image_for_overlay คืนค่า: {processed_img}")
            
            if not processed_img:
                print("❌ ประมวลผลภาพไม่สำเร็จ ข้ามการวางภาพ")
                has_image = False
            else:
                print(f"✅ 【ภาพกระบวนการ】ประมวลผลภาพสำเร็จ: {processed_img}")
                # ตรวจสอบว่าไฟล์ภาพที่ประมวลผลแล้วมีอยู่จริง
                if Path(processed_img).exists():
                    print(f"✅ ไฟล์ภาพที่ประมวลผลแล้วมีอยู่จริง: {processed_img}")
                    file_size = Path(processed_img).stat().st_size
                    print(f"✅ ขนาดไฟล์ภาพที่ประมวลผลแล้ว: {file_size} ไบต์")
                else:
                    print(f"❌ ไฟล์ภาพที่ประมวลผลแล้วไม่มีอยู่: {processed_img}")
                has_image = True
        elif enable_image and not final_image_path:
            print("⚠️ ภาพได้ถูกเปิดใช้งานแต่ไม่พบภาพที่ตรงกัน")
            print("📁 ลองใช้ข้อมูลภาพเริ่มต้น...")
            
            # ลองดึงภาพจากไดเรกทอรีภาพ
            try:
                print("📁 【โปรเซสภาพเริ่มต้น】เริ่มลองดึงภาพเริ่มต้น...")
                image_dir = get_data_path("input/images")
                print(f"📁 【โปรเซสภาพเริ่มต้น】เส้นทางไดเรกทอรีภาพ: {image_dir}")
                
                if Path(image_dir).exists():
                    print(f"📁 【โปรเซสภาพเริ่มต้น】ไดเรกทอรีภาพมีอยู่ เริ่มค้นหาไฟล์ภาพ...")
                    image_files = []
                    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        found_files = list(Path(image_dir).glob(f"*{ext}"))
                        found_files_upper = list(Path(image_dir).glob(f"*{ext.upper()}"))
                        print(f"📁 【โปรเซสภาพเริ่มต้น】พิวัฒนาการ {ext}: พบ {len(found_files)} ไฟล์")
                        print(f"📁 【โปรเซสภาพเริ่มต้น】พิวัฒนาการ {ext.upper()}: พบ {len(found_files_upper)} ไฟล์")
                        image_files.extend(found_files)
                        image_files.extend(found_files_upper)
                    
                    print(f"📁 【โปรเซสภาพเริ่มต้น】พบภาพทั้งหมด {len(image_files)} ไฟล์")
                    
                    if image_files:
                        default_image = str(image_files[0])
                        print(f"📁 【โปรเซสภาพเริ่มต้น】ใช้ภาพเริ่มต้น: {default_image}")
                        
                        processed_img_path = temp_dir / "processed_image.png"
                        print(f"📁 【โปรเซสภาพเริ่มต้น】ประมวลผลภาพไปที่: {processed_img_path}")
                        
                        processed_img = process_image_for_overlay(
                            default_image,
                            str(processed_img_path),
                            size=(img_size, img_size)
                        )
                        print(f"📁 【โปรเซสภาพเริ่มต้น】process_image_for_overlay คืนค่า: {processed_img}")
                        
                        if processed_img:
                            print(f"✅ 【ภาพกระบวนการ】ภาพเริ่มต้นประมวลผลสำเร็จ: {processed_img}")
                            has_image = True
                            final_image_path = default_image
                        else:
                            print("❌ ประมวลผลภาพเริ่มต้นไม่สำเร็จ")
                            has_image = False
                    else:
                        print("❌ ไม่มีภาพที่สามารถใช้ได้ในไดเรกทอรีภาพ")
                        has_image = False
                else:
                    print(f"❌ ไม่มีไดเรกทอรีภาพ: {image_dir}")
                    has_image = False
            except Exception as e:
                print(f"❌ ดึงภาพเริ่มต้นไม่สำเร็จ: {e}")
                import traceback
                traceback.print_exc()
                has_image = False
        else:
            if not enable_image:
                print("ภาพได้ถูกปิดใช้งาน")
            has_image = False
        
        return has_image, final_image_path, processed_img_path
    
    def _process_gif(self, enable_gif, gif_path, temp_dir, gif_scale, gif_loop_count, duration, gif_rotation, progress_callback, gif_x=800, gif_y=100):
        """处理GIF素材"""
        if progress_callback:
            progress_callback("处理GIF素材", 30.0)
            
        has_gif = False
        processed_gif_path = None
        
        if enable_gif and gif_path and Path(gif_path).exists():
            print(f"【GIF流程】ประมวลผลGIF {gif_path} โดยมีปัจจัยการขยาย: {gif_scale} และตำแหน่ง: ({gif_x}, {gif_y}) และจำนวนรอบ: {gif_loop_count}")
            
            # ตรวจสอบรูปแบบไฟล์
            file_ext = Path(gif_path).suffix.lower()
            if file_ext in ['.gif', '.webp']:
                # ใช้ฟังก์ชันประมวลผลGIFที่ปรับปรุง ให้เวลาวิดีโอเพื่อให้GIFดำเนินการตลอดเวลาวิดีโอ
                processed_gif_path = self._process_animated_gif_for_video(gif_path, temp_dir, gif_scale, gif_loop_count, duration, gif_rotation)
                
                if processed_gif_path:
                    has_gif = True
                    print(f"【GIF流程】GIFประมวลผลสำเร็จ: {processed_gif_path}")
                else:
                    print(f"【GIF流程】GIFประมวลผลไม่สำเร็จ")
            else:
                print(f"【GIF流程】ไม่รองรับรูปแบบไฟล์: {file_ext}")
        else:
            if not enable_gif:
                print("GIFได้ถูกปิดใช้งาน")
            elif not gif_path:
                print("ไม่ได้ระบุเส้นทางGIF")
            else:
                print(f"GIFไฟล์ไม่มีอยู่: {gif_path}")
        
        return has_gif, processed_gif_path
    
    def _process_animated_gif_for_video(self, gif_path, temp_dir, scale_factor=1.0, loop_count=-1, video_duration=None, gif_rotation=0):
        """
        ฟังก์ชันประมวลผลGIFที่ปรับปรุงสำหรับวิดีโอ
        
        พารามิเตอร์:
            gif_path: เส้นทางไฟล์GIFที่ใช้ร่วม
            temp_dir: เส้นทางไดเรกทอรีชั่วคราว
            scale_factor: ปัจจัยการขยาย
            loop_count: จำนวนรอบ (-1แทนรอบไม่จำกัด)
            video_duration: เวลาวิดีโอ (วินาที) ใช้เพื่อให้GIFดำเนินการตลอดเวลาวิดีโอ
            gif_rotation: องศาการหมุน (0-359 องศา)
            
        คืนค่า:
            เส้นทางไฟล์GIFที่ปรับปรุง ถ้าไม่สำเร็จคืนค่าNone
        """
        try:
            if not Path(gif_path).exists():
                print(f"GIFไฟล์ไม่มีอยู่: {gif_path}")
                return None
            
            # เส้นทางเอาต์พุต
            processed_gif_path = temp_dir / "processed_animated_gif.gif"
            
            # ถ้ามีเวลาวิดีโอ คำนวณจำนวนรอบที่จำเป็น
            if video_duration is not None:
                # ดึงระยะเวลาของGIFเริ่มต้น
                gif_info_cmd = [
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', str(gif_path)
                ]
                
                try:
                    result = subprocess.run(gif_info_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    gif_duration = float(result.stdout.decode().strip())
                    print(f"ระยะเวลาGIFเริ่มต้น: {gif_duration} วินาที")
                    
                    # คำนวณจำนวนรอบที่ต้องการ
                    if gif_duration > 0:
                        required_loops = int(video_duration / gif_duration) + 1
                        print(f"เวลาวิดีโอ: {video_duration} วินาที ต้องการรอบ {required_loops} รอบ")
                    else:
                        required_loops = 10  # รอบเริ่มต้น 10 รอบ
                        
                except Exception as e:
                    print(f"ดึงข้อมูลGIFไม่สำเร็จ ใช้รอบเริ่มต้น: {e}")
                    required_loops = 10
            else:
                required_loops = 10  # รอบเริ่มต้น 10 รอบ
                
            # สร้างคำสั่งFFmpegเพื่อประมวลผลGIF รักษาคุณสมบัติการเคลื่อนไหว
            gif_cmd = [
                'ffmpeg', '-y',
                '-stream_loop', str(required_loops),  # วนซ้ำการเล่น
                '-i', str(gif_path)
            ]
            
            # ถ้ามีเวลาวิดีโอ จำกัดระยะเวลาGIF
            if video_duration is not None:
                gif_cmd.extend(['-t', str(video_duration)])
            
            # เพิ่มฟิลเตอร์ขยายและหมุน (ถ้าจำเป็น)
            filters = []
            if scale_factor != 1.0:
                filters.append(f"scale=iw*{scale_factor}:ih*{scale_factor}")
            
            # เพิ่มฟิลเตอร์หมุน (เพิ่มเสมอเพื่อให้แน่ใจว่าอยู่ในทิศทางที่ถูกต้อง)
            # ฟิลเตอร์หมุนของFFmpeg เป็นการหมุนปีกซ้าย ต้องใช้ค่าติดลบเพื่อทำให้หมุนเป็นทิศทางปีกขวา
            # แปลงองศาเป็นเรเดียน และใช้ค่าติดลบ
            # ใช้เฉพาะเมื่อผู้ใช้ปรับค่า
            base_rotation = 0  # ไม่ใช้แกนหมุนเริ่มต้น ใช้เฉพาะค่าที่ผู้ใช้ตั้ง
            actual_rotation = base_rotation + gif_rotation
            rotation_radians = -actual_rotation * 3.14159265359 / 180
            filters.append(f"rotate={rotation_radians}:fillcolor=none:bilinear=0")
            print(f"【การหมุนGIF】ใช้องศา: {actual_rotation} องศา (เริ่มต้น: {base_rotation} องศา + ผู้ใช้ตั้ง: {gif_rotation} องศา)")
            
            # เพิ่มฟิลเตอร์ประมวลผลGIF รักษาการเคลื่อนไหว
            if filters:
                filter_str = ",".join(filters)
                gif_cmd.extend([
                    '-vf', f'{filter_str},split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128'
                ])
            else:
                gif_cmd.extend([
                    '-vf', 'split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128'
                ])
            
            # ตั้งค่าการวนซ้ำ
            if loop_count == -1:
                gif_cmd.extend(['-loop', '0'])  # วนซ้ำไม่จำกัด
            else:
                gif_cmd.extend(['-loop', str(loop_count)])
            
            gif_cmd.extend([
                '-f', 'gif',
                str(processed_gif_path)
            ])
            
            print(f"【การประมวลผลภาพเคลื่อนไหวGIF】ประมวลผลคำสั่ง: {' '.join(gif_cmd)}")
            
            result = subprocess.run(gif_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"【การประมวลผลภาพเคลื่อนไหวGIF】ประมวลผลสำเร็จ: {processed_gif_path}")
            return str(processed_gif_path)
            
        except subprocess.CalledProcessError as e:
            print(f"【การประมวลผลภาพเคลื่อนไหวGIF】ประมวลผลไม่สำเร็จ: {e}")
            print(f"stderr: {e.stderr.decode()}")
            return None
        except Exception as e:
            print(f"【GIFアニメーション処理】処理異常: {e}")
            return None
    
    def _process_subtitle_materials(self, enable_subtitle, subtitle_df, subtitle_lang, video_index, style,
                                   font_size, subtitle_width, bg_width, bg_height, temp_dir, dynamic_processor,
                                   progress_callback, enable_background=True, width=1080, height=1920):
        """处理字幕素材（字幕图片和背景）"""
        if progress_callback:
            progress_callback("处理字幕素材", 35.0)
            
        subtitle_img = None
        bg_img = None
        subtitle_ass_path = None  # 添加ASS字幕文件路径变量
        use_ass_subtitle = False  # 添加ASS字幕使用标志
        
        # 处理字幕内容（静态字幕和动态字幕独立处理）
        subtitle_text = None
        dynamic_subtitle_text = None
        
        # 首先检查是否有字幕数据
        if subtitle_df is not None:
            print(f"可用的文档列: {list(subtitle_df.columns)}")
            print(f"视频索引: {video_index}")
            
            # 使用新的静态字幕处理器获取字幕文本
            static_processor = StaticSubtitleProcessor()
            
            if dynamic_processor:
                # 如果启用了动态字幕，使用动态字幕处理器获取字幕文本
                animated_processor = AnimatedSubtitleProcessor()
                dynamic_subtitle_text = animated_processor.get_animated_subtitle_text(subtitle_df, subtitle_lang, video_index)
                
            if enable_subtitle:
                # 如果启用了静态字幕，使用静态字幕处理器获取字幕文本
                subtitle_text = static_processor.get_static_subtitle_text(subtitle_df, subtitle_lang, video_index)
        
        # 处理动态字幕（独立于静态字幕）
        if dynamic_processor and dynamic_subtitle_text:
            print(f"[动态字幕] 使用动态字幕处理器生成字幕")
            # 使用新的动态字幕处理器生成ASS字幕
            animated_processor = AnimatedSubtitleProcessor()
            subtitle_ass_path = animated_processor.create_animated_subtitle(
                text=dynamic_subtitle_text,
                width=width,
                height=height,
                font_size=font_size,
                animation_style=dynamic_processor.animation_style,
                animation_intensity=dynamic_processor.animation_intensity,
                highlight_color=dynamic_processor.highlight_color,
                match_mode=dynamic_processor.match_mode,
                position_x=dynamic_processor.position_x,
                position_y=dynamic_processor.position_y,
                font_color=getattr(dynamic_processor, "font_color", "#FFFFFF"),
                outline_size=getattr(dynamic_processor, "outline_size", 2),
                outline_color=getattr(dynamic_processor, "outline_color", "#000000"),
                animation_duration=getattr(dynamic_processor, "animation_duration", 0.3),
                opacity=getattr(dynamic_processor, "opacity", 100)
            )
            
            # 动态字幕文件生成成功
            if subtitle_ass_path and Path(subtitle_ass_path).exists():
                # 设置动态字幕处理标志
                use_ass_subtitle = True
                print(f"[动态字幕] 动态字幕文件生成成功: {subtitle_ass_path}")
            else:
                print(f"[动态字幕] 动态字幕文件生成失败")
        
        # 处理静态字幕（独立于动态字幕）
        if enable_subtitle and subtitle_text:
            # 创建字幕图片
            subtitle_height = 500  # 字幕高度
            subtitle_img_path = temp_dir / "subtitle.png"
            
            # 调试信息：打印字体大小
            print(f"字体大小传递给字幕创建函数: {font_size}")
            
            # 静态字幕生成
            print(f"[静态字幕] 静态字幕生成")
            print(f"[静态字幕] 字幕文本: {subtitle_text}")
            print(f"[静态字幕] 字体大小: {font_size}")
            print(f"[静态字幕] 样式: {style}")
            
            # 使用新的静态字幕处理器生成PNG字幕
            static_processor = StaticSubtitleProcessor()
            subtitle_img = static_processor.create_static_subtitle(
                text=subtitle_text,
                style=style,
                width=subtitle_width,
                height=subtitle_height,
                font_size=font_size,
                output_path=str(subtitle_img_path)
            )
        
        # 处理无字幕数据的情况
        if subtitle_df is None:
            if enable_subtitle:
                print("字幕機能が有効になっていますが、有効な字幕データが存在しないので、字幕生成をスキップします")
            if dynamic_processor:
                print("[动态字幕] 启用了动态字幕，但没有字幕数据，跳过动态字幕生成")
        elif not enable_subtitle and not dynamic_processor:
            print("字幕機能が無効になっています、字幕生成をスキップします")
        
        # 修复：透明背景生成完全独立于字幕功能
        # 检查是否需要生成透明背景（通过enable_background参数控制）
        if enable_background:
            # 透明な背景を角丸四角形として作成し、カスタムサイズを使用する
            bg_img_path = temp_dir / "background.png"
            bg_radius = 20   # 角丸半径
            
            # ビデオフレームからの色抽出を使用して背景を作成する
            print("【背景色】開始し、ビデオフレームからの色抽出を使用して角丸四角形背景を作成する")
            bg_img = create_rounded_rect_background(
                width=bg_width,
                height=bg_height,
                radius=bg_radius,
                output_path=str(bg_img_path),
                sample_frame=None  # 簡素な処理のために、ビデオフレームからの色抽出を使用しない
            )
            
            if not bg_img:
                print("角丸四角形背景の作成に失敗しました")
        else:
            print("【背景色】透明背景功能未启用，跳过背景生成")
        
        return subtitle_img, bg_img, subtitle_ass_path, use_ass_subtitle  # ユーザーにASS字幕に関する情報を返す
    
    def _process_music(self, enable_music, music_path, music_mode, video_index, duration, temp_dir, progress_callback):
        """処理背景音楽"""
        if progress_callback:
            progress_callback("処理背景音楽", 40.0)
            
        selected_music_path = None
        
        if enable_music:
            print(f"【音楽処理】開始し、ビデオインデックス: {video_index}")
            print(f"【音楽処理】音楽パラメーター: enable_music={enable_music}, music_path={music_path}, music_mode={music_mode}")
            # 音楽が有効になっていますが、音楽ファイルパスが指定されていない場合は、デフォルトの音楽ディレクトリを試してみる
            if not music_path:
                # デフォルトの音楽ディレクトリを試してみる
                default_music_dir = get_data_path("music")
                if Path(default_music_dir).exists():
                    music_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.flac']
                    music_files = []
                    for ext in music_extensions:
                        music_files.extend(list(Path(default_music_dir).glob(f"*{ext}")))
                        music_files.extend(list(Path(default_music_dir).glob(f"*{ext.upper()}")))
                    
                    if music_files:
                        # デフォルトで最初の音楽ファイルを使用する
                        selected_music_path = str(music_files[0])
                        print(f"【音楽処理】デフォルトの音楽ディレクトリ内の音楽を使用する: {selected_music_path}")
                    else:
                        print(f"【音楽処理】デフォルトの音楽ディレクトリに音楽ファイルが見つかりません: {default_music_dir}")
                        selected_music_path = None
                else:
                    print(f"【音楽処理】デフォルトの音楽ディレクトリが存在しません: {default_music_dir}")
                    selected_music_path = None
            else:
                # モードに基づいて音楽ファイルを選択する
                if Path(music_path).is_file():
                    # 単独の音楽ファイル
                    selected_music_path = music_path
                    print(f"【音楽処理】単独の音楽ファイルを使用する: {selected_music_path}")
                elif Path(music_path).is_dir():
                    # 音楽ファイルのフォルダ
                    music_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.flac']
                    music_files = []
                    for ext in music_extensions:
                        music_files.extend(list(Path(music_path).glob(f"*{ext}")))
                        music_files.extend(list(Path(music_path).glob(f"*{ext.upper()}")))
                    
                    print(f"【音楽処理】音楽フォルダで {len(music_files)} つの音楽ファイルを見つけました")
                    for i, file in enumerate(music_files):
                        print(f"  [{i}] {file.name}")
                    
                    if music_files:
                        print(f"【音楽処理】音楽モード: {music_mode}")
                        if music_mode == "random":
                            selected_music_path = str(random.choice(music_files))
                            print(f"【音楽処理】ランダムに音楽を選択する: {selected_music_path}")
                        elif music_mode == "sequence":
                            # 順序モード：ビデオインデックスを使用して音楽ファイルを選択する
                            # インデックスが範囲外に出ないようにする
                            music_file_index = video_index % len(music_files)
                            selected_music_path = str(music_files[music_file_index])
                            print(f"【音楽処理】順序に音楽を選択する: {selected_music_path} (音楽インデックス: {music_file_index}/{len(music_files)-1}, ビデオインデックス: {video_index})")
                        else:  # 単独モード、最初のものを選択する
                            selected_music_path = str(music_files[0])
                            print(f"【音楽処理】最初の音楽を選択する: {selected_music_path}")
                    else:
                        print(f"【音楽処理】音楽フォルダに音楽ファイルが見つかりません: {music_path}")
                        selected_music_path = None
                else:
                    print(f"【音楽処理】音楽パスが有効なファイルやフォルダではありません: {music_path}")
                    selected_music_path = None
        else:
            print(f"【音楽処理】音楽機能が有効になっていません")

        print(f"【音乐处理】最终选择的音乐路径: {selected_music_path}")
        if selected_music_path and Path(selected_music_path).exists():
            print(f"【音乐处理】音乐文件存在，大小: {Path(selected_music_path).stat().st_size} 字节")
            
            # 根据视频时长自动裁剪音乐
            print(f"【音乐处理】开始根据视频时长裁剪音乐")
            print(f"【音乐处理】视频时长: {duration}秒")
            
            # 创建临时裁剪音乐文件路径
            trimmed_music_path = temp_dir / f"trimmed_music_{uuid.uuid4().hex[:8]}.mp3"
            
            # 调用音乐裁剪函数
            trimmed_result = trim_music_to_video_duration(selected_music_path, duration, trimmed_music_path)
            
            if trimmed_result:
                selected_music_path = trimmed_result
                print(f"【音乐处理】音乐裁剪成功，使用裁剪后的音乐: {selected_music_path}")
            else:
                print(f"【音乐处理】音乐裁剪失败，使用原始音乐文件")
        elif selected_music_path:
            print(f"【音乐处理】警告：音乐文件不存在！")
            print(f"【音乐处理】检查的路径: {selected_music_path}")
            print(f"【音乐处理】路径类型: {type(selected_music_path)}")
        
        return selected_music_path
    
    def _process_with_ffmpeg(self, video_path, output_path, temp_dir, width, height, duration,
                            enable_subtitle, enable_background, enable_image, enable_gif, enable_music,
                            subtitle_img, bg_img, processed_img_path, processed_gif_path, selected_music_path,
                            has_image, has_gif,
                            img_position_x, img_position_y, img_size,
                            subtitle_text_x, subtitle_text_y, final_y_position,
                            bg_width, bg_height, subtitle_x, subtitle_y,
                            gif_x, gif_y,
                            music_volume, quality_settings, quicktime_compatible,
                            progress_callback, has_music_file, 
                            subtitle_ass_path=None, use_ass_subtitle=False):
        """使用FFmpeg处理视频"""
        # 显式初始化变量以避免静态分析工具报告未定义错误
        gif_x = gif_x if gif_x is not None else 800
        gif_y = gif_y if gif_y is not None else 100
        
        if progress_callback:
            progress_callback("FFmpeg处理视频", 50.0)
            
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
        print(f"【位置调试】字幕位置: x={subtitle_absolute_x}, y={final_y_position}, 字体大小={70}")
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
        
        # 素材输入已在前面添加，这里只需要设置索引
        current_input_index = 1
        
        if enable_subtitle and subtitle_img:
            subtitle_index = current_input_index
            current_input_index += 1
            logging.info(f"  📝 字幕输入索引: {subtitle_index}")
            
        if enable_background and bg_img:
            bg_index = current_input_index
            current_input_index += 1
            logging.info(f"  🎨 背景输入索引: {bg_index}")
            
        if enable_image and has_image:
            # 确保processed_img_path已定义且文件存在
            if 'processed_img_path' in locals() and processed_img_path and Path(processed_img_path).exists():
                img_index = current_input_index
                current_input_index += 1
                logging.info(f"  📸 图片输入索引: {img_index}")
            else:
                logging.warning(f"  ⚠️ 图片启用但processed_img_path未定义或文件不存在")
                img_index = None
                has_image = False
            
        if enable_gif and has_gif:
            gif_index = current_input_index
            current_input_index += 1
            logging.info(f"  🎞️ GIF输入索引: {gif_index}")
        
        input_index = current_input_index
        logging.info(f"  📊 总输入文件数: {input_index} (包括主视频)")
            
        # 构建复杂过滤器
        logging.info("🔍 开始构建过滤器链")
        filter_complex_parts = [f"[0:v]trim=duration={duration}[v1]"]
        current_stream = "v1"
        stream_index = 2
        
        # 格式化图层
        logging.info("🎨 格式化图层")
        if enable_background and bg_index is not None:
            filter_complex_parts.append(f"[{bg_index}:v]format=rgba[bg]")
            logging.info(f"  🎨 背景图层: [{bg_index}:v] -> [bg]")
            
        if enable_image and img_index is not None:
            filter_complex_parts.append(f"[{img_index}:v]format=rgba[img]")
            logging.info(f"  📸 图片图层: [{img_index}:v] -> [img]")
            
        if enable_gif and gif_index is not None:
            filter_complex_parts.append(f"[{gif_index}:v]format=rgba[gif]")
            logging.info(f"  🎞️ GIF图层: [{gif_index}:v] -> [gif]")
            
        if enable_subtitle and subtitle_index is not None:
            filter_complex_parts.append(f"[{subtitle_index}:v]format=rgba[s1]")
            logging.info(f"  📝 字幕图层: [{subtitle_index}:v] -> [s1]")
        
        # 叠加背景（如果启用）
        logging.info("🔄 开始叠加层处理")
        if enable_background and bg_index is not None:
            cmd = f"[{current_stream}][bg]overlay=x='if(lt(t,{entrance_duration}),{bg_start_x}+({bg_final_x}-({bg_start_x}))*t/{entrance_duration},{bg_final_x})':y={bg_y_position}:shortest=0:format=auto[v{stream_index}]"
            filter_complex_parts.append(cmd)
            logging.info(f"  🎨 添加背景叠加: {current_stream} + bg -> v{stream_index}")
            logging.info(f"    位置: x={bg_final_x}, y={bg_y_position}")
            current_stream = f"v{stream_index}"
            stream_index += 1
        else:
            if enable_background:
                logging.warning(f"  ⚠️ 背景启用但bg_index为None")
        
        # 叠加图片（如果启用）
        if enable_image and img_index is not None:
            cmd = f"[{current_stream}][img]overlay=x='if(lt(t,{entrance_duration}),{img_start_x}+({img_x_position}-({img_start_x}))*t/{entrance_duration},{img_x_position})':y={img_final_position}:shortest=0:format=auto[v{stream_index}]"
            filter_complex_parts.append(cmd)
            logging.info(f"  📸 添加图片叠加: {current_stream} + img -> v{stream_index}")
            logging.info(f"    位置: x={img_x_position}, y={img_final_position}")
            current_stream = f"v{stream_index}"
            stream_index += 1
        else:
            if enable_image:
                logging.warning(f"  ⚠️ 图片启用但img_index为None或has_image为False")
            
        # 叠加GIF（如果启用）
        if enable_gif and gif_index is not None:
            # 保持GIF动画特性，使用正确的overlay语法
            cmd = f"[{current_stream}][gif]overlay=x={gif_x}:y={gif_y}:shortest=0:repeatlast=0[v{stream_index}]"
            filter_complex_parts.append(cmd)
            logging.info(f"  🎞️ 添加GIF叠加: {current_stream} + gif -> v{stream_index}")
            logging.info(f"    位置: x={gif_x}, y={gif_y}")
            logging.info(f"    修复说明: 保持GIF动画特性")
            current_stream = f"v{stream_index}"
            stream_index += 1
        else:
            if enable_gif:
                logging.warning(f"  ⚠️ GIF启用但gif_index为None或has_gif为False")
            
        # 处理动态字幕（ASS字幕）- 独立于静态字幕
        if use_ass_subtitle and subtitle_ass_path:
            # 使用ASS字幕文件
            # ASS字幕不需要作为输入流，直接在过滤器中使用
            # 确保跨平台路径格式正确并进行转义
            ass_path_str = str(subtitle_ass_path)
            if os.name == 'nt':  # Windows系统
                # 将反斜杠替换为正斜杠，保持驱动器字母格式 (C:/path/to/file)
                ass_path_str = ass_path_str.replace('\\', '/')
            else:
                # Unix/Linux/macOS系统，确保使用正斜杠
                ass_path_str = ass_path_str.replace('\\', '/')
            
            # 对路径进行转义，处理特殊字符和空格
            # 使用单引号包围路径以避免特殊字符问题
            ass_filter = f"[{current_stream}]ass='{ass_path_str}'[v{stream_index}]"
            filter_complex_parts.append(ass_filter)
            logging.info(f"  📝 添加动态字幕(ASS): {current_stream} -> v{stream_index}")
            logging.info(f"    ASS文件: {subtitle_ass_path}")
            current_stream = f"v{stream_index}"
            stream_index += 1
        
        # 处理静态字幕（PNG字幕）- 独立于动态字幕
        if enable_subtitle and subtitle_index is not None:
            # 使用PNG图片字幕
            # 修正坐标系统：将1080x1920坐标系统映射到实际视频尺寸
            video_info = get_video_info(video_path)
            if video_info:
                actual_width, actual_height, _ = video_info
                # 计算坐标缩放比例
                x_scale = actual_width / 1080.0
                y_scale = actual_height / 1920.0
                
                # 转换坐标到实际视频尺寸
                scaled_subtitle_x = int(subtitle_absolute_x * x_scale)
                scaled_subtitle_y = int(final_y_position * y_scale)
                scaled_start_y = int(start_y_position * y_scale)
                scaled_final_y = int(final_y_position * y_scale)
                
                print(f"🔧 坐标系统转换: 原始({subtitle_absolute_x}, {final_y_position}) -> 实际({scaled_subtitle_x}, {scaled_subtitle_y})")
                print(f"🔧 缩放比例: X={x_scale:.3f}, Y={y_scale:.3f}")
                logging.info(f"🔧 坐标系统转换: 原始({subtitle_absolute_x}, {final_y_position}) -> 实际({scaled_subtitle_x}, {scaled_subtitle_y})")
            else:
                # 如果无法获取视频信息，使用原始坐标
                scaled_subtitle_x = subtitle_absolute_x
                scaled_subtitle_y = final_y_position
                scaled_start_y = start_y_position
                scaled_final_y = final_y_position
                print("⚠️ 无法获取视频信息，使用原始坐标")
                logging.warning("⚠️ 无法获取视频信息，使用原始坐标")
            
            cmd = f"[{current_stream}][s1]overlay=x={scaled_subtitle_x}:y='if(lt(t,{entrance_duration}),{scaled_start_y}-({scaled_start_y}-{scaled_final_y})*t/{entrance_duration},{scaled_final_y})':shortest=0:format=auto[v{stream_index}]"
            filter_complex_parts.append(cmd)
            logging.info(f"  📝 添加PNG字幕叠加: {current_stream} + s1 -> v{stream_index}")
            logging.info(f"    位置: x={scaled_subtitle_x}, y={scaled_final_y}")
            logging.info(f"    随机位置: {False}")
            current_stream = f"v{stream_index}"
            stream_index += 1
        else:
            logging.warning(f"  ⚠️ 字幕启用但没有可用的字幕文件")
        
        # 检查是否有任何素材需要处理
        # 静态字幕和动态字幕可以同时存在，分别处理
        has_any_overlay = (enable_subtitle and subtitle_img) or (enable_background and bg_img) or (enable_image and has_image) or (enable_gif and has_gif) or use_ass_subtitle
        
        # 组合过滤器链，并确保最终输出端点正确设置
        if has_any_overlay:
             # 确保最终输出有一个明确的标签[v]
             if current_stream != "v":
                 # 将最终流标记为[v]
                 filter_complex_parts.append(f"[{current_stream}]null[v]")
        else:
            # 如果没有任何叠加操作，确保有一个[v]标签
            if current_stream != "v":
                filter_complex_parts.append(f"[{current_stream}]null[v]")
        
        filter_complex = ";".join(filter_complex_parts)
        logging.info(f"  🔗 最终过滤器链: {filter_complex}")
        
        # 如果没有启用任何叠加功能，确保filter_complex_parts不为空
        if not has_any_overlay:
            filter_complex = ""
            print("未启用任何叠加功能，跳过滤镜处理")
        
        # 添加详细的调试信息
        logging.info(f"【素材状态调试】完整状态检查")
        logging.info(f"  enable_subtitle: {enable_subtitle}, subtitle_img: {subtitle_img is not None}")
        logging.info(f"  enable_background: {enable_background}, bg_img: {bg_img is not None}")
        logging.info(f"  enable_image: {enable_image}, has_image: {has_image}")
        logging.info(f"  enable_gif: {enable_gif}, has_gif: {has_gif}")
        logging.info(f"  enable_music: {enable_music}, selected_music_path: {selected_music_path}")
        logging.info(f"  has_any_overlay: {has_any_overlay}")
        
        print(f"【素材状态调试】")
        print(f"  enable_subtitle: {enable_subtitle}, subtitle_img: {subtitle_img is not None}")
        print(f"  enable_background: {enable_background}, bg_img: {bg_img is not None}")
        print(f"  enable_image: {enable_image}, has_image: {has_image}")
        print(f"  enable_gif: {enable_gif}, has_gif: {has_gif}")
        print(f"  has_any_overlay: {has_any_overlay}")
        
        # 添加更详细的素材状态检查
        if enable_image:
            logging.info(f"  📸 图片详细状态: final_image_path={processed_img_path}")
            if processed_img_path:
                logging.info(f"  📸 图片大小: {Path(processed_img_path).stat().st_size} 字节")
                # 修复：检查bg_img是否为None
                if bg_img is not None:
                    logging.info(f"  🎨 背景文件存在: {Path(bg_img).exists()}")
                else:
                    logging.info(f"  🎨 背景文件不存在")
                # 修复：检查processed_gif_path是否为None
                if processed_gif_path is not None:
                    logging.info(f"  🎞️ GIF文件存在: {Path(processed_gif_path).exists()}")
                else:
                    logging.info(f"  🎞️ GIF文件不存在")
                # 修复：检查music_path是否为None
                if selected_music_path is not None:
                    logging.info(f"  🎵 音乐路径存在: {Path(selected_music_path).exists()}")
                else:
                    logging.info(f"  🎵 音乐路径不存在")
                exists = Path(processed_img_path).exists()
                if Path(processed_img_path).exists():
                    logging.info(f"  📸 图片大小: {Path(processed_img_path).stat().st_size} 字节")
                    
        if enable_background:
            logging.info(f"  🎨 背景详细状态: bg_img={bg_img}")
            if bg_img:
                logging.info(f"  🎨 背景文件存在: {Path(bg_img).exists()}")
                
        if enable_gif:
            logging.info(f"  🎞️ GIF详细状态: processed_gif_path={processed_gif_path}")
            if processed_gif_path:
                logging.info(f"  🎞️ GIF文件存在: {Path(processed_gif_path).exists()}")
                
        if enable_music:
            logging.info(f"  🎵 音乐详细状态: selected_music_path={selected_music_path}")
            if selected_music_path:
                logging.info(f"  🎵 音乐路径存在: {Path(selected_music_path).exists()}")
        
        if enable_image and not has_image:
            logging.warning(f"  ⚠️ 图片功能已启用但has_image为False")
            logging.warning(f"  processed_img_path: {processed_img_path}")
            print(f"  ⚠️ 图片功能已启用但has_image为False")
            print(f"  processed_img_path: {processed_img_path}")
            if processed_img_path:
                exists = Path(processed_img_path).exists()
                logging.warning(f"  图片文件存在: {exists}")
                print(f"  图片文件存在: {exists}")
                
        if enable_background and not bg_img:
            logging.warning(f"  ⚠️ 背景功能已启用但bg_img为None")
            print(f"  ⚠️ 背景功能已启用但bg_img为None")
            
        # 构建FFmpeg命令
        input_index = 1  # 视频输入为0，从1开始计算其他输入
        
        # 添加字幕、背景、图片、GIF等素材输入
        # 只有在启用静态字幕且有字幕图片时才添加字幕输入（允许与动态字幕同时存在）
        if enable_subtitle and subtitle_img:
            ffmpeg_command.extend(['-i', str(subtitle_img)])
            input_index += 1
            
        if enable_background and bg_img:
            ffmpeg_command.extend(['-i', str(bg_img)])
            input_index += 1
            
        if enable_image and has_image and 'processed_img_path' in locals() and processed_img_path and Path(processed_img_path).exists():
            ffmpeg_command.extend(['-i', str(processed_img_path)])
            input_index += 1
            
        if enable_gif and has_gif:
            ffmpeg_command.extend(['-i', str(processed_gif_path)])
            input_index += 1
        
        # 音乐输入
        music_index = None
        if selected_music_path:
            print(f"【音乐处理】开始添加音乐输入到FFmpeg命令")
            print(f"【音乐处理】音乐文件路径: {selected_music_path}")
            print(f"【音乐处理】音乐文件存在性检查: {Path(selected_music_path).exists()}")
            if Path(selected_music_path).exists():
                print(f"【音乐处理】音乐文件大小: {Path(selected_music_path).stat().st_size} 字节")
            
            ffmpeg_command.extend(['-i', selected_music_path])
            music_index = input_index
            input_index += 1
            print(f"【音乐处理】添加音乐输入，索引: {music_index}")
            print(f"【音乐处理】当前FFmpeg命令长度: {len(ffmpeg_command)}")
            print(f"【音乐处理】当前输入索引: {input_index}")
            # 检查音乐文件是否存在
            if Path(selected_music_path).exists():
                print(f"【音乐处理】音乐文件存在，大小: {Path(selected_music_path).stat().st_size} 字节")
            else:
                print(f"【音乐处理】警告：音乐文件不存在！")
        else:
            print(f"【音乐处理】没有选择音乐文件")
        
        # 始终构建FFmpeg命令，确保音乐能够正确处理
        # 修复：当启用音乐时，即使没有叠加素材也要进入FFmpeg处理逻辑
        if has_any_overlay or selected_music_path:
            
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
            
            # 添加过滤器链（如果需要叠加素材）
            # 只有在有叠加素材时才添加过滤器链
            if has_any_overlay and filter_complex:
                ffmpeg_command.extend(['-filter_complex', filter_complex])
            
            # 音频处理 - 修复音频流映射
            if selected_music_path:
                # 计算音量调节值（50% = 0.5）
                volume_ratio = music_volume / 100.0
                print(f"【音乐处理】开始音频流映射处理")
                print(f"【音乐处理】音量比例: {volume_ratio} (原始音量: {music_volume}%)")
                print(f"【音乐处理】音乐输入索引: {music_index}")
                print(f"【音乐处理】是否有叠加素材: {has_any_overlay}")
                
                # 添加音频流映射和处理参数
                if has_any_overlay:
                    # 如果有叠加素材，视频流来自过滤器链
                    audio_params = [
                        '-map', '[v]',  # 映射过滤器链的视频输出
                        '-map', f'{music_index}:a?',  # 映射音乐的音频流，使用可选映射避免错误
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-af', f'volume={volume_ratio}',  # 调节音量
                        '-shortest'  # 以最短的流为准（视频结束时音频也结束）
                    ]
                    print(f"【音乐处理】叠加模式 - 视频流映射: [v]")
                    print(f"【音乐处理】叠加模式 - 音频流映射: {music_index}:a")
                    ffmpeg_command.extend(audio_params)
                else:
                    # 如果没有叠加素材，直接映射视频流
                    # 使用实际记录的音乐索引，而不是重新计算
                    music_input_index = music_index
                    
                    # 为Windows系统优化音频处理参数
                    import platform
                    if platform.system() == 'Windows':
                        # Windows下使用更稳定的音频滤镜参数
                        audio_filter = f'volume={volume_ratio}:precision=fixed'
                    else:
                        # macOS和其他系统使用默认参数
                        audio_filter = f'volume={volume_ratio}'
                    
                    audio_params = [
                        '-map', '0:v',  # 映射视频流
                        '-map', f'{music_input_index}:a?',  # 映射音乐的音频流，使用可选映射避免错误
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-af', audio_filter,  # 调节音量
                        '-shortest'  # 以最短的流为准（视频结束时音频也结束）
                    ]
                    print(f"【音乐处理】直接模式 - 视频流映射: 0:v")
                    print(f"【音乐处理】直接模式 - 音频流映射: {music_input_index}:a (实际索引: {music_index})")
                    ffmpeg_command.extend(audio_params)
                print(f"【音乐处理】添加音频编码参数，音量: {music_volume}%")
                print(f"【音乐处理】音频参数: {audio_params}")
            else:
                # 如果没有音乐，保留原视频的音频流
                if has_any_overlay:
                    # 如果有叠加素材，映射过滤器链的视频输出和原视频的音频流
                    ffmpeg_command.extend(['-map', '[v]', '-map', '0:a?'])
                else:
                    # 如果没有叠加素材，直接映射视频流和音频流
                    ffmpeg_command.extend(['-map', '0:v', '-map', '0:a?'])
                # 保留原视频音频编码
                ffmpeg_command.extend(['-c:a', 'copy'])
                print(f"【音乐处理】没有音乐，保留原视频音频流")
            
            ffmpeg_command.append(str(output_with_subtitle))
            
            # 报告进度：开始执行FFmpeg命令
            if progress_callback:
                progress_callback("开始视频处理", 50.0)
                
            # 执行命令
            logging.info(f"🎥 执行最终FFmpeg命令")
            logging.info(f"  命令长度: {len(ffmpeg_command)} 个参数")
            logging.info(f"  输入文件数: {input_index}")
            logging.info(f"  输出文件: {output_with_subtitle}")
            logging.info(f"  完整命令: {' '.join(ffmpeg_command)}")
            print(f"【音乐处理】FFmpeg命令详细信息:")
            print(f"【音乐处理】  命令长度: {len(ffmpeg_command)} 个参数")
            print(f"【音乐处理】  输入文件数: {input_index}")
            print(f"【音乐处理】  输出文件: {output_with_subtitle}")
            print(f"【音乐处理】  是否包含音乐: {selected_music_path is not None}")
            if selected_music_path:
                print(f"【音乐处理】  音乐文件: {selected_music_path}")
                print(f"【音乐处理】  音乐索引: {music_index}")
            print(f"执行命令: {' '.join(ffmpeg_command)}")
            # 报告进度：执行FFmpeg命令中
            if progress_callback:
                progress_callback("执行视频处理中", 70.0)
                
            print(f"【音乐处理】开始执行FFmpeg命令...")
            result = run_ffmpeg_command(ffmpeg_command)
            print(f"【音乐处理】FFmpeg命令执行结果: {result}")
                
            if not result:
                print("添加素材失败，尝试使用备用方法")
                return None
        else:
            print("所有素材功能都已禁用，但需要处理音乐")
            print(f"【音乐处理】检查音乐参数: selected_music_path={selected_music_path}, enable_music={enable_music}")
            # 如果只有音乐，直接复制视频并添加音乐
            if selected_music_path:
                volume_ratio = music_volume / 100.0
                print(f"【音乐处理】只添加音乐，不添加其他素材")
                print(f"【音乐处理】音乐文件路径: {selected_music_path}")
                print(f"【音乐处理】音量比例: {volume_ratio} (原始音量: {music_volume}%)")
                # 检查音乐文件是否存在
                if Path(selected_music_path).exists():
                    print(f"【音乐处理】音乐文件存在，大小: {Path(selected_music_path).stat().st_size} 字节")
                else:
                    print(f"【音乐处理】警告：音乐文件不存在！")
                    print(f"【音乐处理】检查的路径: {selected_music_path}")
                
                # 为Windows系统优化音频处理参数
                import platform
                if platform.system() == 'Windows':
                    # Windows下使用更稳定的音频滤镜参数
                    audio_filter = f'volume={volume_ratio}:precision=fixed'
                else:
                    # macOS和其他系统使用默认参数
                    audio_filter = f'volume={volume_ratio}'
                
                copy_with_music_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-i', selected_music_path,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-af', audio_filter,
                    '-map', '0:v',  # 映射视频流
                    '-map', '1:a?',   # 映射音频流，使用可选映射避免错误
                    '-shortest',
                    str(output_with_subtitle)
                ]
                print(f"【音乐处理】纯音乐模式FFmpeg命令详细信息:")
                print(f"【音乐处理】  输入视频: {video_path}")
                print(f"【音乐处理】  输入音乐: {selected_music_path}")
                print(f"【音乐处理】  输出文件: {output_with_subtitle}")
                print(f"【音乐处理】  视频流映射: 0:v")
                print(f"【音乐处理】  音频流映射: 1:a?")
                print(f"执行命令: {' '.join(copy_with_music_cmd)}")
                print(f"【音乐处理】开始执行纯音乐模式FFmpeg命令...")
                result = run_ffmpeg_command(copy_with_music_cmd)
                print(f"【音乐处理】纯音乐模式FFmpeg命令执行结果: {result}")
                if not result:
                    print("添加音乐失败")
                    return None
            else:
                print("没有音乐，直接复制原视频")
                # 直接复制原视频
                copy_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-c', 'copy',
                    str(output_with_subtitle)
                ]
                if not run_ffmpeg_command(copy_cmd):
                    print("复制原视频失败")
                    return None
        
        # 10. 添加QuickTime兼容性（如果需要）
        def _apply_final_conversion(input_path, output_path, progress_callback=None):
            """应用最终转换，添加QuickTime兼容性"""
            ensure_dir(Path(output_path).parent)
            
            final_cmd = [
                'ffmpeg', '-y',
                '-i', str(input_path),
                '-c', 'copy',
                '-movflags', '+faststart',
                str(output_path)
            ]
            
            print(f"执行命令: {' '.join(final_cmd)}")
            # 报告进度：最终转换
            if progress_callback:
                progress_callback("最终转换", 95.0)
                
            return run_ffmpeg_command(final_cmd)
            
        if _apply_final_conversion(output_with_subtitle, output_path, progress_callback):
            print(f"成功添加字幕动画，输出到: {output_path}")
            # 报告进度：处理完成
            if progress_callback:
                progress_callback("处理完成", 100.0)
            return output_path
        else:
            print("最终转换失败")
            return None


    def process_video_with_dynamic_subtitle(self, video_path, output_path, subtitle_text, 
                                           animation_style="高亮放大", animation_intensity=1.5, 
                                           highlight_color="#FFD700", progress_callback=None):
        """
        使用动态字幕处理视频的简化接口
        """
        return self.add_subtitle_to_video(
            video_path=video_path,
            output_path=output_path,
            enable_dynamic_subtitle=True,
            animation_style=animation_style,
            animation_intensity=animation_intensity,
            highlight_color=highlight_color,
            progress_callback=progress_callback
        )
    
    def add_dynamic_subtitle_to_video(self, video_path, output_path, subtitle_data, 
                                     animation_config=None, progress_callback=None):
        """
        为视频添加动态字幕的专用方法
        """
        if animation_config is None:
            animation_config = {
                "animation_style": "高亮放大",
                "animation_intensity": 1.5,
                "highlight_color": "#FFD700"
            }
        
        return self.add_subtitle_to_video(
            video_path=video_path,
            output_path=output_path,
            enable_dynamic_subtitle=True,
            animation_style=animation_config.get("animation_style", "高亮放大"),
            animation_intensity=animation_config.get("animation_intensity", 1.5),
            highlight_color=animation_config.get("highlight_color", "#FFD700"),
            progress_callback=progress_callback
        )


# 创建全局处理器实例
_subtitle_processor = VideoSubtitleProcessor()


def add_subtitle_to_video(*args, **kwargs):
    """
    兼容旧接口的函数，调用新的VideoSubtitleProcessor类
    """
    return _subtitle_processor.add_subtitle_to_video(*args, **kwargs)