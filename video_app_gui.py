#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理GUI界面
集成单个视频处理和批量处理功能
"""

import os
import sys
import json
import subprocess  # 添加subprocess导入
from pathlib import Path
import random
import configparser
import pandas as pd

# 将所有PyQt5导入放在一个try块中
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QLabel, 
                                QLineEdit, QPushButton, QFileDialog, QComboBox, QCheckBox, 
                                QSpinBox, QDoubleSpinBox, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                QGroupBox, QMessageBox, QProgressBar, 
                                QListWidget, QAbstractItemView, QSplitter, QSlider,
                                QTextEdit)  # 添加QTextEdit导入
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
    
except ImportError as e:
    print(f"错误: {e}")
    print("缺少PyQt5库，请先安装:")
    print("pip install PyQt5")
    sys.exit(1)

# 确认必要的库导入
try:
    # 导入处理函数
    from video_core import process_video
    from utils import load_style_config, get_data_path
    # 导入日志管理器
    from log_manager import init_logging, get_log_manager
    import logging
except ImportError as e:
    print(f"错误: {e}")
    print("请确保video_core.py和utils.py在当前目录或Python路径中")
    sys.exit(1)


class ProcessingThread(QThread):
    """视频处理线程"""
    progress_updated = pyqtSignal(int, str)
    processing_complete = pyqtSignal(bool, dict)  # 修改为dict传递统计信息
    processing_stage_updated = pyqtSignal(str, float)  # 新增信号，用于更新处理阶段和进度
    
    def __init__(self, short_videos, long_videos, folders, output_dir, style, subtitle_lang, 
                 quicktime_compatible, img_position_x, img_position_y, 
                 font_size, subtitle_width, subtitle_x, subtitle_y, bg_width, bg_height, img_size,
                 subtitle_text_x, subtitle_text_y, random_position, enable_subtitle,
                 enable_background, enable_image, enable_music, music_path, music_mode, music_volume,
                 document_path=None, enable_gif=False, gif_path="", gif_loop_count=-1, 
                 gif_scale=1.0, gif_rotation=0, gif_x=800, gif_y=100, scale_factor=1.1, image_path=None, quality_settings=None,
                 enable_tts=False, tts_voice="zh-CN-XiaoxiaoNeural", tts_volume=100, tts_text="", auto_match_duration=True,
                 enable_dynamic_subtitle=False, animation_style="highlight", animation_intensity=1.5, 
                 highlight_color="#FFD700", match_mode="fixed"):  # 添加动态字幕参数
        super().__init__()
        # 分别存储不同类型的文件
        self.short_videos = short_videos  # 小于9秒的视频
        self.long_videos = long_videos    # 大于等于9秒的视频
        self.folders = folders            # 文件夹列表
        self.output_dir = output_dir
        self.style = style
        self.subtitle_lang = subtitle_lang
        self.quicktime_compatible = quicktime_compatible
        self.img_position_x = img_position_x
        self.img_position_y = img_position_y
        self.font_size = font_size
        self.subtitle_width = subtitle_width
        self.subtitle_x = subtitle_x
        self.subtitle_y = subtitle_y
        self.bg_width = bg_width
        self.bg_height = bg_height
        self.img_size = img_size
        self.subtitle_text_x = subtitle_text_x
        self.subtitle_text_y = subtitle_text_y
        self.random_position = random_position
        self.enable_subtitle = enable_subtitle
        self.enable_background = enable_background
        self.enable_image = enable_image
        self.enable_music = enable_music
        self.music_path = music_path
        self.music_mode = music_mode
        self.music_volume = music_volume
        self.document_path = document_path
        self.enable_gif = enable_gif
        self.gif_path = gif_path
        self.gif_loop_count = gif_loop_count
        self.gif_scale = gif_scale
        self.gif_rotation = gif_rotation
        self.gif_x = gif_x
        self.gif_y = gif_y
        self.scale_factor = scale_factor
        self.image_path = image_path
        self.quality_settings = quality_settings or {}  # 添加质量设置参数
        # TTS相关参数
        self.enable_tts = enable_tts
        self.tts_voice = tts_voice
        self.tts_volume = tts_volume
        self.tts_text = tts_text  # 用户输入的固定TTS文本
        self.auto_match_duration = auto_match_duration  # 添加自动匹配时长参数
        self.user_document_path = document_path  # 保存用户指定的文档路径
        
        # 动态字幕相关参数
        self.enable_dynamic_subtitle = enable_dynamic_subtitle
        self.animation_style = animation_style
        self.animation_intensity = animation_intensity
        self.highlight_color = highlight_color
        self.match_mode = match_mode
    
    def run(self):
        import time
        import tempfile
        from pathlib import Path
        from video_core import process_video, process_folder_videos, preprocess_video_by_type, preprocess_video_without_reverse
        
        start_time = time.time()
        
        try:
            # 获取日志管理器并记录开始信息
            log_manager = get_log_manager()
            total_files = len(self.short_videos) + len(self.long_videos) + len(self.folders)
            logging.info(f"🚀 开始批量处理，总计: {total_files} 个项目")
            logging.info(f"  - 短视频 (<9秒): {len(self.short_videos)} 个")
            logging.info(f"  - 长视频 (>=9秒): {len(self.long_videos)} 个")
            logging.info(f"  - 文件夹: {len(self.folders)} 个")
            logging.info(f"📋 处理参数: style={self.style}, lang={self.subtitle_lang}")
            logging.info(f"📋 素材设置: subtitle={self.enable_subtitle}, bg={self.enable_background}, img={self.enable_image}")
            logging.info(f"📋 随机位置: {self.random_position}")
            logging.info(f"📋 TTS设置: enable={self.enable_tts}, voice={self.tts_voice}")
            
            success_count = 0
            failed_items = []
            
            # 第一阶段：预处理所有视频
            print("开始预处理阶段...")
            preprocessed_videos = []  # 存储预处理后的视频路径和原始信息
            
            # 1. 预处理文件夹中的视频
            for i, folder_path in enumerate(self.folders):
                try:
                    logging.info(f"📁 开始预处理文件夹 {i+1}/{len(self.folders)}: {Path(folder_path).name}")
                    self.progress_updated.emit(int((i / total_files) * 100), f"预处理文件夹 {i+1}/{len(self.folders)}: {Path(folder_path).name}")
                    
                    # 创建用于文件夹处理的临时目录
                    folder_temp_dir = Path(tempfile.mkdtemp())
                    print(f"创建文件夹处理临时目录: {folder_temp_dir}")
                    
                    # 处理文件夹中的视频，拼接成一个视频
                    merged_video_path = process_folder_videos(folder_path, folder_temp_dir)
                    
                    if merged_video_path and Path(merged_video_path).exists():
                        print(f"文件夹视频预处理完成: {merged_video_path}")
                        # 获取预处理后视频的信息
                        from utils import get_video_info
                        merged_info = get_video_info(merged_video_path)
                        if merged_info:
                            width, height, duration = merged_info
                            print(f"预处理后视频信息: 时长: {duration:.2f}秒, 分辨率: {width}x{height}")
                        
                        # 将预处理后的视频添加到列表中
                        preprocessed_videos.append({
                            'type': 'folder',
                            'original_path': folder_path,
                            'preprocessed_path': merged_video_path,
                            'output_name': f"{Path(folder_path).name}_processed.mp4"
                        })
                    else:
                        failed_items.append(f"📁 {Path(folder_path).name}")
                        logging.error(f"❌ 文件夹视频拼接失败: {Path(folder_path).name}")
                        print(f"❌ 文件夹视频拼接失败: {Path(folder_path).name}")
                except Exception as folder_error:
                    failed_items.append(f"📁 {Path(folder_path).name}")
                    logging.error(f"❌ 文件夹预处理异常: {Path(folder_path).name} - {str(folder_error)}")
                    print(f"❌ 文件夹预处理异常: {Path(folder_path).name} - {str(folder_error)}")
            
            # 2. 预处理短视频 (< 9秒)
            for i, video_path in enumerate(self.short_videos):
                try:
                    logging.info(f"⏱️ 开始预处理短视频 {i+1}/{len(self.short_videos)}: {Path(video_path).name}")
                    current_index = len(self.folders) + i
                    self.progress_updated.emit(int((current_index / total_files) * 100), f"预处理短视频 {i+1}/{len(self.short_videos)}: {Path(video_path).name}")
                    
                    # 对短视频进行预处理（水印处理+正放倒放）
                    import tempfile
                    temp_dir = Path(tempfile.mkdtemp())
                    preprocessed_path = None
                    try:
                        preprocessed_path = preprocess_video_by_type(video_path, temp_dir)
                        
                        if preprocessed_path and Path(preprocessed_path).exists():
                            print(f"短视频预处理完成: {preprocessed_path}")
                            # 获取预处理后视频的信息
                            from utils import get_video_info
                            preprocessed_info = get_video_info(preprocessed_path)
                            if preprocessed_info:
                                width, height, duration = preprocessed_info
                                print(f"预处理后视频信息: 时长: {duration:.2f}秒, 分辨率: {width}x{height}")
                            
                            # 将预处理后的视频添加到列表中，同时保存临时目录路径
                            preprocessed_videos.append({
                                'type': 'short',
                                'original_path': video_path,
                                'preprocessed_path': preprocessed_path,
                                'temp_dir': str(temp_dir),  # 保存临时目录路径
                                'output_name': f"{Path(video_path).stem}_processed.mp4"
                            })
                        else:
                            failed_items.append(f"⏱️ {Path(video_path).name}")
                            logging.error(f"❌ 短视频预处理失败: {Path(video_path).name}")
                            print(f"❌ 短视频预处理失败: {Path(video_path).name}")
                            # 预处理失败时清理临时目录
                            try:
                                import shutil
                                shutil.rmtree(temp_dir)
                            except:
                                pass
                    except Exception as video_error:
                        failed_items.append(f"⏱️ {Path(video_path).name}")
                        logging.error(f"❌ 短视频预处理异常: {Path(video_path).name} - {str(video_error)}")
                        print(f"❌ 短视频预处理异常: {Path(video_path).name} - {str(video_error)}")
                        # 异常时清理临时目录
                        try:
                            import shutil
                            shutil.rmtree(temp_dir)
                        except:
                            pass
                except Exception as short_video_error:
                    failed_items.append(f"⏱️ {Path(video_path).name}")
                    logging.error(f"❌ 短视频预处理异常: {Path(video_path).name} - {str(short_video_error)}")
                    print(f"❌ 短视频预处理异常: {Path(video_path).name} - {str(short_video_error)}")
            
            # 3. 预处理长视频 (>= 9秒)
            for i, video_path in enumerate(self.long_videos):
                try:
                    logging.info(f"🎬 开始预处理长视频 {i+1}/{len(self.long_videos)}: {Path(video_path).name}")
                    current_index = len(self.folders) + len(self.short_videos) + i
                    self.progress_updated.emit(int((current_index / total_files) * 100), f"预处理长视频 {i+1}/{len(self.long_videos)}: {Path(video_path).name}")
                    
                    # 对长视频进行预处理（仅水印处理，不进行正放倒放）
                    import tempfile
                    temp_dir = Path(tempfile.mkdtemp())
                    preprocessed_path = None
                    try:
                        preprocessed_path = preprocess_video_without_reverse(video_path, temp_dir)
                        
                        if preprocessed_path and Path(preprocessed_path).exists():
                            print(f"长视频预处理完成: {preprocessed_path}")
                            # 获取预处理后视频的信息
                            from utils import get_video_info
                            preprocessed_info = get_video_info(preprocessed_path)
                            if preprocessed_info:
                                width, height, duration = preprocessed_info
                                print(f"预处理后视频信息: 时长: {duration:.2f}秒, 分辨率: {width}x{height}")
                            
                            # 将预处理后的视频添加到列表中，同时保存临时目录路径
                            preprocessed_videos.append({
                                'type': 'long',
                                'original_path': video_path,
                                'preprocessed_path': preprocessed_path,
                                'temp_dir': str(temp_dir),  # 保存临时目录路径
                                'output_name': f"{Path(video_path).stem}_processed.mp4"
                            })
                        else:
                            failed_items.append(f"🎬 {Path(video_path).name}")
                            logging.error(f"❌ 长视频预处理失败: {Path(video_path).name}")
                            print(f"❌ 长视频预处理失败: {Path(video_path).name}")
                            # 预处理失败时清理临时目录
                            try:
                                import shutil
                                shutil.rmtree(temp_dir)
                            except:
                                pass
                    except Exception as preprocess_error:
                        failed_items.append(f"🎬 {Path(video_path).name}")
                        logging.error(f"❌ 长视频预处理异常: {Path(video_path).name} - {str(preprocess_error)}")
                        print(f"❌ 长视频预处理异常: {Path(video_path).name} - {str(preprocess_error)}")
                        # 异常时清理临时目录
                        try:
                            import shutil
                            shutil.rmtree(temp_dir)
                        except:
                            pass
                except Exception as long_video_error:
                    failed_items.append(f"🎬 {Path(video_path).name}")
                    logging.error(f"❌ 长视频预处理异常: {Path(video_path).name} - {str(long_video_error)}")
                    print(f"❌ 长视频预处理异常: {Path(video_path).name} - {str(long_video_error)}")
            
            # 第二阶段：统一处理所有预处理后的视频
            print(f"预处理阶段完成，共预处理 {len(preprocessed_videos)} 个视频，开始统一处理阶段...")
            total_preprocessed = len(preprocessed_videos)
            
            # 统一处理所有预处理后的视频，使用简单的索引进行背景音乐匹配
            for i, video_info in enumerate(preprocessed_videos):
                item_start_time = time.time()
                
                # 计算进度
                current_index = i
                total_items = total_preprocessed + len(failed_items)  # 包含失败项
                base_progress = (current_index / total_items) * 100 if total_items > 0 else 0
                
                video_type = video_info['type']
                original_path = video_info['original_path']
                preprocessed_path = video_info['preprocessed_path']
                output_name = video_info['output_name']
                
                self.progress_updated.emit(
                    int(base_progress), 
                    f"处理视频 {i+1}/{total_preprocessed}: {Path(original_path).name}"
                )
                
                # 发送处理阶段信息
                self.processing_stage_updated.emit(f"开始处理视频 {i+1}/{total_preprocessed}", 0.0)
                
                logging.info(f"开始处理视频 {i+1}/{total_preprocessed}: {Path(original_path).name} (类型: {video_type})")
                
                try:
                    with log_manager.capture_output():
                        # 对预处理后的视频进行精处理（添加字幕、图片等）
                        output_path = Path(self.output_dir) / output_name
                        print(f"准备对预处理后的视频进行精处理...")
                        print(f"输出路径: {output_path}")
                        
                        # 定义内部回调函数来更新视频处理进度
                        def update_progress_callback(stage, progress_percent):
                            # 计算当前项目的进度占总进度的比例
                            current_item_progress = base_progress + (progress_percent / 100.0) * (100.0 / total_items)
                            self.progress_updated.emit(int(current_item_progress), 
                                                      f"处理视频 {i+1}/{total_preprocessed}: {stage} ({progress_percent:.0f}%)")
                            # 发送处理阶段信息
                            self.processing_stage_updated.emit(stage, progress_percent)
                        
                        # 如果启用了TTS且用户没有输入固定文本，则为每个视频获取对应的TTS文本
                        current_tts_text = self.tts_text  # 默认使用用户输入的固定文本
                        print(f"视频处理TTS设置: enable={self.enable_tts}, fixed_text='{self.tts_text}'")
                        if self.enable_tts and not self.tts_text:
                            # 为每个视频获取对应的TTS文本
                            try:
                                from video_helpers import get_tts_text_for_video
                                from utils import load_subtitle_config
                                subtitle_df = load_subtitle_config()
                                if subtitle_df is not None and not subtitle_df.empty:
                                    # 使用视频索引获取对应的TTS文本（简化索引计算）
                                    current_tts_text = get_tts_text_for_video(subtitle_df, self.subtitle_lang, i)
                                    print(f"为视频 {i+1} 获取TTS文本: {current_tts_text}")
                                else:
                                    print("无法加载字幕配置，使用空TTS文本")
                                    current_tts_text = ""
                            except Exception as e:
                                print(f"获取TTS文本时出错: {e}")
                                current_tts_text = ""
                        else:
                            current_tts_text = self.tts_text  # 确保变量已定义
                            print(f"使用用户输入的固定TTS文本: {current_tts_text}")
                        
                        # 对预处理后的视频进行精处理
                        # 获取音乐模式的实际值
                        music_mode_value = self.music_mode.currentData() if hasattr(self.music_mode, 'currentData') else self.music_mode
                        music_path_value = self.music_path.text() if hasattr(self.music_path, 'text') else self.music_path
                        print(f"调用process_video进行精处理，视频索引: {i}")
                        print(f"音乐参数: enable_music={self.enable_music}, music_path={music_path_value}, music_mode={music_mode_value}, music_volume={self.music_volume}")
                        result = process_video(
                            preprocessed_path, 
                            str(output_path),
                            self.style, 
                            self.subtitle_lang, 
                            self.quicktime_compatible,
                            self.img_position_x, 
                            self.img_position_y,
                            self.font_size,
                            self.subtitle_x,
                            self.subtitle_y,
                            self.bg_width,
                            self.bg_height,
                            self.img_size,
                            self.subtitle_text_x,
                            self.subtitle_text_y,
                            self.random_position,
                            self.enable_subtitle,
                            self.enable_background,
                            self.enable_image,
                            self.enable_music,
                            music_path_value,
                            music_mode_value,
                            self.music_volume,
                            self.user_document_path,
                            self.enable_gif,
                            self.gif_path,
                            self.gif_loop_count,
                            self.gif_scale,
                            self.gif_rotation,
                            self.gif_x,
                            self.gif_y,
                            self.scale_factor,
                            self.image_path,
                            self.subtitle_width,
                            quality_settings=self.quality_settings,
                            progress_callback=update_progress_callback,
                            video_index=i,  # 传递简单的索引，避免复杂的索引计算
                            enable_tts=self.enable_tts,
                            tts_voice=self.tts_voice,
                            tts_volume=self.tts_volume,
                            tts_text=current_tts_text,
                            auto_match_duration=self.auto_match_duration  # 添加自动匹配时长参数
                        )
                        
                        item_end_time = time.time()
                        item_duration = item_end_time - item_start_time
                        print(f"视频精处理完成，耗时: {item_duration:.2f}秒")
                        video_name = Path(original_path).name
                        if result:
                            success_count += 1
                            logging.info(f"✅ 视频处理成功: {video_name} (耗时: {item_duration:.1f}秒)")
                            print(f"✅ 视频处理成功: {video_name} (耗时: {item_duration:.1f}秒)")
                            
                            # 更新整体进度
                            current_progress = int(((current_index + 1) / total_items) * 100)
                            self.progress_updated.emit(
                                current_progress,
                                f"已完成: {i+1}/{total_preprocessed} - {video_name} (耗时: {item_duration:.1f}秒)"
                            )
                        else:
                            failed_items.append(f"🎥 {video_name}")
                            logging.error(f"❌ 视频处理失败: {video_name}")
                            print(f"❌ 视频处理失败: {video_name}")
                            
                            # 即使失败也更新进度
                            current_progress = int(((current_index + 1) / total_items) * 100)
                            self.progress_updated.emit(
                                current_progress,
                                f"视频处理失败: {i+1}/{total_preprocessed} - {video_name}"
                            )
                        
                        # 无论成功还是失败，都清理临时目录
                        if 'temp_dir' in video_info:
                            try:
                                import shutil
                                shutil.rmtree(video_info['temp_dir'])
                                print(f"已清理临时目录: {video_info['temp_dir']}")
                            except Exception as e:
                                print(f"清理临时目录失败: {e}")
                except Exception as video_error:
                    video_name = Path(original_path).name
                    failed_items.append(f"🎥 {video_name}")
                    logging.error(f"❌ 视频处理异常: {video_name} - {str(video_error)}")
                    print(f"❌ 视频处理异常: {video_name} - {str(video_error)}")
                    
                    # 即使异常也更新进度
                    current_progress = int(((current_index + 1) / total_items) * 100)
                    self.progress_updated.emit(
                        current_progress,
                        f"视频处理异常: {i+1}/{total_preprocessed} - {video_name}"
                    )
                    
                    # 异常时也清理临时目录
                    if 'temp_dir' in video_info:
                        try:
                            import shutil
                            shutil.rmtree(video_info['temp_dir'])
                            print(f"已清理临时目录: {video_info['temp_dir']}")
                        except Exception as e:
                            print(f"清理临时目录失败: {e}")
            
            # 所有处理完成
            end_time = time.time()
            total_duration = end_time - start_time
            avg_duration = total_duration / total_files if total_files > 0 else 0
            
            # 准备统计信息
            stats = {
                'total_videos': total_files,
                'success_count': success_count,
                'failed_count': len(failed_items),
                'failed_videos': [item.split(' ', 1)[1] if ' ' in item else item for item in failed_items],
                'total_time': total_duration,
                'avg_time': avg_duration,
                'output_dir': str(self.output_dir)
            }
            
            # 发送完成信号
            self.processing_complete.emit(True, stats)
            
            # 记录完成日志
            logging.info(f"🏁 批量处理完成！成功: {success_count}/{total_files} 个，耗时: {total_duration:.1f}秒")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # 准备错误统计信息
            total_items = len(self.short_videos) + len(self.long_videos) + len(self.folders)
            error_stats = {
                'total_videos': total_items,
                'success_count': 0,
                'failed_count': total_items,
                'total_time': time.time() - start_time if 'start_time' in locals() else 0,
                'avg_time': 0,
                'failed_videos': [f"⏱️ {Path(p).name}" for p in self.short_videos] + 
                                [f"🎬 {Path(p).name}" for p in self.long_videos] + 
                                [f"📁 {Path(p).name}" for p in self.folders],
                'output_dir': str(self.output_dir),
                'error': str(e)
            }
            
            self.progress_updated.emit(100, f"处理出错: {str(e)}")
            self.processing_complete.emit(False, error_stats)

class VideoProcessorApp(QMainWindow):
    """视频处理应用主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频处理工具")
        self.setGeometry(100, 100, 1200, 850)  # 增大窗口高度以确保底部按钮和进度条完全显示
        self.setMinimumSize(1000, 700)  # 设置最小窗口大小，确保界面元素不会被压缩
        self.setMaximumSize(1600, 1200)  # 设置最大窗口大小，保持合理的界面比例
        
        # 设置窗口标题栏样式，无法在 macOS 上完全自定义，但可以调整
        if sys.platform == 'darwin':
            # macOS 上的特殊设置
            self.setUnifiedTitleAndToolBarOnMac(True)  # 设置统一外观
        
        # 应用全局样式表以参考苹果系统的界面配色
        # 根据不同操作系统设置不同的字体大小
        font_size = "13px"
        label_font_size = "13px"
        groupbox_font_size = "13px"
        button_font_size = "13px"
        
        if sys.platform == 'win32':
            # Windows系统下增大字体
            font_size = "14px"
            label_font_size = "14px"
            groupbox_font_size = "15px"
            button_font_size = "14px"
            
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2c2c2c;
                color: #ffffff;
            }
            QGroupBox {
                padding-top: 16px;
                margin-top: 10px;
                font-weight: bold;
                border-radius: 8px;
                border: 1px solid #555555;
                background-color: #353535;
                color: #ffffff;
                font-size: {groupbox_font_size};
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0px 8px 0px 8px;
                background-color: #353535;
                color: #ffffff;
                border-radius: 4px;
            }
            QLabel {
                color: #ffffff;
                font-size: {label_font_size};
            }
            QListWidget {
                border: 1px solid #555555;
                border-radius: 6px;
                background-color: #2c2c2c;
                color: #ffffff;
                padding: 2px;
            }
            QListWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #3a3a3a;
                color: #ffffff;
                margin: 1px 0px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected {
                background-color: #0070f3;
                color: #ffffff;
            }
            QPushButton {
                background-color: #0070f3;
                border: 1px solid #0060d0;
                border-radius: 4px;
                padding: 3px 8px;
                color: #ffffff;
                min-height: 28px;
                font-size: {button_font_size};
            }
            QPushButton:hover {
                background-color: #1884ff;
            }
            QPushButton:pressed {
                background-color: #0060d0;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #a0a0a0;
            }
            QPushButton#primaryButton {
                background-color: #0070f3;
                color: #ffffff;
                border: 1px solid #0060d0;
                font-weight: bold;
                min-height: 32px;
            }
            QPushButton#primaryButton:hover {
                background-color: #1884ff;
            }
            QPushButton#primaryButton:pressed {
                background-color: #0060d0;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 4px 8px;
                background-color: #2c2c2c;
                color: #ffffff;
                selection-background-color: #0070f3;
                selection-color: #ffffff;
                font-size: {font_size};
                min-height: 26px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #0070f3;
            }
            QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
                background-color: #3a3a3a;
                color: #a0a0a0;
            }
            /* 增强QSpinBox和QDoubleSpinBox的按钮样式 */
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                height: 12px;
                border-left: 1px solid #555555;
                border-bottom: 1px solid #555555;
                border-top-right-radius: 4px;
                background-color: #3a3a3a;
            }
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
                background-color: #4a4a4a;
            }
            QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {
                background-color: #0070f3;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                width: 10px;
                height: 6px;
                image: url(:/images/up_arrow.png);  /* 如果有图标文件 */
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                height: 12px;
                border-left: 1px solid #555555;
                border-top: 1px solid #555555;
                border-bottom-right-radius: 4px;
                background-color: #3a3a3a;
            }
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #4a4a4a;
            }
            QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
                background-color: #0070f3;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                width: 10px;
                height: 6px;
                image: url(:/images/down_arrow.png);  /* 如果有图标文件 */
            }
            QComboBox {
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 4px 28px 4px 8px;
                background-color: #2c2c2c;
                color: #ffffff;
                min-height: 26px;
                font-size: {font_size};
            }
            QComboBox:focus {
                border: 1px solid #0070f3;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #555555;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #555555;
                background-color: #2c2c2c;
                color: #ffffff;
                selection-background-color: #0070f3;
                selection-color: #ffffff;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #2c2c2c;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QCheckBox::indicator:checked {
                background-color: #0070f3;
                border: 1px solid #0060d0;
            }
            QCheckBox::indicator:checked:disabled {
                background-color: #666666;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 4px;
                background: #3a3a3a;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0070f3;
                border: 1px solid #0060d0;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:disabled {
                background: #666666;
                border: 1px solid #555555;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #2c2c2c;
            }
            QTabBar::tab {
                background: #353535;
                border: 1px solid #555555;
                padding: 6px 12px;
                color: #ffffff;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #454545;
                border-bottom-color: #454545;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                background-color: #2c2c2c;
                color: #ffffff;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0070f3;
                border-radius: 3px;
            }
            QStatusBar {
                background-color: #353535;
                color: #ffffff;
            }
            QToolTip {
                background-color: #2c2c2c;
                color: #ffffff;
                border: 1px solid #555555;
            }
        """)
        
        # 初始化日志系统
        print("📄 初始化日志管理系统...")
        self.log_manager = init_logging()
        logging.info("🎉 视频处理应用启动")
        logging.info(f"🖥️  运行平台: {sys.platform}")
        
        # 加载配置和样式
        self.style_config = load_style_config()  # type: ignore
        self.settings = QSettings("VideoApp", "VideoProcessor")
        
        # 设置默认输出目录为代码所在目录下的output文件夹
        self.default_output_dir = str(Path(__file__).parent / "output")
        os.makedirs(self.default_output_dir, exist_ok=True)
        
        # 初始化UI
        self.init_ui()
        self.load_saved_settings()
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局和标签页
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(8)
        # 增加底部边距以确保进度条完全可见，避免被任务栏遮挡
        self.main_layout.setContentsMargins(10, 10, 10, 50)
        
        # 创建标签页控件
        self.tabs = QTabWidget()
        self.process_tab = QWidget()
        self.settings_tab = QWidget()
        
        self.tabs.addTab(self.process_tab, "视频处理")
        self.tabs.addTab(self.settings_tab, "设置")
        
        # 初始化各个标签页
        self.init_process_tab()
        self.init_settings_tab()
        
        # 状态栏和进度条
        self.status_bar = self.statusBar()
        if self.status_bar is not None:
            self.status_bar.setMinimumHeight(30)  # 增加状态栏最小高度
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setTextVisible(True)
            # 增加进度条高度和宽度以提高可见性
            self.progress_bar.setMinimumHeight(25)
            self.progress_bar.setMinimumWidth(300)
            self.status_bar.addPermanentWidget(self.progress_bar, 1)  # 设置拉伸因子为1，使进度条占据更多空间
            self.status_bar.showMessage("准备就绪")
            # 设置状态栏样式
            self.status_bar.setStyleSheet("QStatusBar {border-top: 1px solid #555555; padding: 3px; background-color: #353535;}")
            self.progress_bar.setStyleSheet("QProgressBar {border: 1px solid #555555; border-radius: 4px; text-align: center;} QProgressBar::chunk {background-color: #3498db;}")

        
        # 添加标签页到主布局
        self.main_layout.addWidget(self.tabs)
        
    def init_process_tab(self):
        """初始化视频处理标签页"""
        main_layout = QVBoxLayout(self.process_tab)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        
        # 左侧：视频选择和基本设置
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # 视频选择组
        video_group = QGroupBox("视频选择")
        video_group.setMinimumHeight(180)
        video_group.setMaximumHeight(200)
        video_layout = QVBoxLayout()
        video_layout.setSpacing(6)
        video_layout.setContentsMargins(8, 8, 8, 8)
        
        # 添加视频文件按钮
        video_btn_layout = QHBoxLayout()
        video_btn_layout.setSpacing(8)
        add_video_btn = QPushButton("添加视频文件")
        add_video_btn.setFixedHeight(26)
        add_video_btn.clicked.connect(self.add_video_files)
        add_folder_for_processing_btn = QPushButton("添加文件夹整体")
        add_folder_for_processing_btn.setFixedHeight(26)
        add_folder_for_processing_btn.clicked.connect(self.add_folder_for_processing)
        add_mixed_folder_btn = QPushButton("添加混合文件夹")
        add_mixed_folder_btn.setFixedHeight(26)
        add_mixed_folder_btn.clicked.connect(self.add_mixed_folder)
        clear_btn = QPushButton("清空列表")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self.clear_video_list)
        
        video_btn_layout.addWidget(add_video_btn)
        video_btn_layout.addWidget(add_folder_for_processing_btn)
        video_btn_layout.addWidget(add_mixed_folder_btn)
        video_btn_layout.addWidget(clear_btn)
        
        # 视频列表
        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.video_list.setMinimumHeight(680)  # 调整高度与右侧两列对齐
        self.video_list.setMaximumHeight(800)  # 设置最大高度
        # 设置列表行高以显示完整路径
        self.video_list.setStyleSheet("QListWidget::item { height: 22px; }")
        
        video_label = QLabel("已选择的视频文件:")
        video_label.setMaximumHeight(18)
        
        video_layout.addLayout(video_btn_layout)
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_list)
        
        video_group.setLayout(video_layout)
        
        # 文档选择组
        document_group = QGroupBox("文档选择")
        document_group.setMinimumHeight(110)
        document_group.setMaximumHeight(130)
        document_layout = QVBoxLayout()
        document_layout.setSpacing(6)
        document_layout.setContentsMargins(8, 8, 8, 8)
        
        # 文档选择按钮和路径显示
        doc_btn_layout = QHBoxLayout()
        doc_btn_layout.setSpacing(8)
        select_doc_btn = QPushButton("选择文档文件")
        select_doc_btn.setFixedHeight(26)
        select_doc_btn.clicked.connect(self.select_document_file)
        clear_doc_btn = QPushButton("清除文档")
        clear_doc_btn.setFixedHeight(26)
        clear_doc_btn.clicked.connect(self.clear_document)
        
        doc_btn_layout.addWidget(select_doc_btn)
        doc_btn_layout.addWidget(clear_doc_btn)
        
        # 文档路径显示
        self.document_path = QLineEdit()
        self.document_path.setReadOnly(True)
        self.document_path.setMaximumHeight(24)
        self.document_path.setPlaceholderText("支持格式: CSV, Excel (.xlsx/.xls), Markdown (.md), Text (.txt)")
        
        doc_label = QLabel("已选择的文档文件:")
        doc_label.setMaximumHeight(18)
        
        document_layout.addLayout(doc_btn_layout)
        document_layout.addWidget(doc_label)
        document_layout.addWidget(self.document_path)
        
        document_group.setLayout(document_layout)
        
        # 图片路径选择组
        image_group = QGroupBox("图片路径")
        image_group.setMinimumHeight(110)
        image_group.setMaximumHeight(130)
        image_layout = QVBoxLayout()
        image_layout.setSpacing(6)
        image_layout.setContentsMargins(8, 8, 8, 8)
        
        # 图片路径选择按钮和路径显示
        img_btn_layout = QHBoxLayout()
        img_btn_layout.setSpacing(8)
        select_img_btn = QPushButton("选择图片文件夹")
        select_img_btn.setFixedHeight(26)
        select_img_btn.clicked.connect(self.select_image_folder)
        clear_img_btn = QPushButton("清除路径")
        clear_img_btn.setFixedHeight(26)
        clear_img_btn.clicked.connect(self.clear_image_path)
        
        img_btn_layout.addWidget(select_img_btn)
        img_btn_layout.addWidget(clear_img_btn)
        
        # 图片路径显示
        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)
        self.image_path.setMaximumHeight(24)
        self.image_path.setPlaceholderText("选择包含图片文件的文件夹，系统将自动匹配视频名称")
        
        img_label = QLabel("已选择的图片文件夹:")
        img_label.setMaximumHeight(18)
        
        image_layout.addLayout(img_btn_layout)
        image_layout.addWidget(img_label)
        image_layout.addWidget(self.image_path)
        
        image_group.setLayout(image_layout)
        
        # 输出设置组
        output_group = QGroupBox("输出设置")
        output_group.setMinimumHeight(90)
        output_group.setMaximumHeight(110)
        output_layout = QGridLayout()
        output_layout.setSpacing(6)
        output_layout.setContentsMargins(8, 8, 8, 8)
        
        self.output_dir = QLineEdit()
        self.output_dir.setReadOnly(True)
        self.output_dir.setMaximumHeight(24)
        output_browse_btn = QPushButton("选择...")
        output_browse_btn.setFixedHeight(26)
        output_browse_btn.clicked.connect(self.browse_output_dir)
        output_browse_btn.setMaximumWidth(80)
        
        output_layout.addWidget(QLabel("输出目录:"), 0, 0)
        output_layout.addWidget(self.output_dir, 0, 1)
        output_layout.addWidget(output_browse_btn, 0, 2)
        
        output_group.setLayout(output_layout)
        
        # 添加组件到左侧布局，按上到下顺序排列
        left_layout.addWidget(video_group)
        left_layout.addWidget(document_group)
        left_layout.addWidget(image_group)
        left_layout.addWidget(output_group)
        left_layout.addStretch()
        
        # 右侧：样式和高级设置（两列布局）
        right_widget = QWidget()
        right_main_layout = QHBoxLayout(right_widget)
        right_main_layout.setSpacing(15)
        right_main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 左列
        left_column = QWidget()
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setSpacing(12)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        
        # 右列
        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setSpacing(12)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        
        # 样式设置组
        style_group = QGroupBox("字幕样式")
        style_group.setMinimumHeight(260)
        style_group.setMaximumHeight(280)
        style_layout = QGridLayout()
        style_layout.setSpacing(6)
        style_layout.setContentsMargins(8, 8, 8, 8)
        
        self.style_combo = QComboBox()
        self.populate_style_combo(self.style_combo)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("随机", "random")
        self.lang_combo.addItem("中文", "chinese")
        self.lang_combo.addItem("马来语", "malay")
        self.lang_combo.addItem("泰语", "thai")
        
        self.quicktime_check = QCheckBox("QuickTime兼容模式")
        
        # 添加字体大小调节
        self.font_size = QSpinBox()
        self.font_size.setRange(30, 150)
        self.font_size.setValue(70)
        self.font_size.setToolTip("字体大小（像素）")
        
        # 添加字幕宽度调节
        self.subtitle_width = QSpinBox()
        self.subtitle_width.setRange(200, 1500)
        self.subtitle_width.setValue(600)  # 增加默认字幕宽度从500到600像素
        self.subtitle_width.setToolTip("字幕最大宽度（像素），超过此宽度自动换行")

        
        # 启用字幕开关
        self.enable_subtitle = QCheckBox("启用字幕")
        self.enable_subtitle.setChecked(True)
        self.enable_subtitle.setToolTip("勾选后视频中会添加字幕")
        
        # 字幕位置随机化开关
        self.random_subtitle_position = QCheckBox("字幕位置随机化")
        self.random_subtitle_position.setToolTip("勾选后字幕将在指定区域(50,200)到(1030,1720)内随机放置")
        self.random_subtitle_position.stateChanged.connect(self.on_random_position_changed)
        
        # 字幕坐标设置
        self.subtitle_text_x = QSpinBox()
        self.subtitle_text_x.setRange(-9999, 9999)
        self.subtitle_text_x.setValue(0)
        self.subtitle_text_x.setToolTip("字幕X轴绝对坐标（像素）")
        
        self.subtitle_text_y = QSpinBox()
        self.subtitle_text_y.setRange(-9999, 9999)
        self.subtitle_text_y.setValue(1190)
        self.subtitle_text_y.setToolTip("字幕Y轴绝对坐标（像素）")
        
        style_layout.addWidget(self.enable_subtitle, 0, 0, 1, 2)
        style_layout.addWidget(QLabel("字幕样式:"), 1, 0)
        style_layout.addWidget(self.style_combo, 1, 1)
        style_layout.addWidget(QLabel("字幕语言:"), 2, 0)
        style_layout.addWidget(self.lang_combo, 2, 1)
        style_layout.addWidget(QLabel("字体大小:"), 3, 0)
        style_layout.addWidget(self.font_size, 3, 1)
        style_layout.addWidget(QLabel("字幕宽度:"), 4, 0)
        style_layout.addWidget(self.subtitle_width, 4, 1)
        style_layout.addWidget(self.random_subtitle_position, 5, 0, 1, 2)
        style_layout.addWidget(QLabel("X坐标 (像素):"), 6, 0)
        style_layout.addWidget(self.subtitle_text_x, 6, 1)
        style_layout.addWidget(QLabel("Y坐标 (像素):"), 7, 0)
        style_layout.addWidget(self.subtitle_text_y, 7, 1)
        style_layout.addWidget(self.quicktime_check, 8, 0, 1, 2)
        
        style_group.setLayout(style_layout)
        
        # 图片设置组
        img_group = QGroupBox("图片设置")
        img_group.setMinimumHeight(180)  # 设置最小高度以让界面不太挤
        img_layout = QGridLayout()
        img_layout.setSpacing(6)  # 减少图片设置组间距
        img_layout.setContentsMargins(8, 8, 8, 8)  # 减少图片设置组边距
        
        # 启用添加图片开关
        self.enable_image = QCheckBox("启用添加图片")
        self.enable_image.setChecked(True)
        self.enable_image.setToolTip("勾选后视频中会添加匹配的图片")
        
        self.img_x = QSpinBox()
        self.img_x.setRange(-9999, 9999)
        self.img_x.setValue(100)
        self.img_x.setToolTip("图片X轴绝对坐标（像素）")
        
        self.img_y = QSpinBox()
        self.img_y.setRange(-9999, 9999)
        self.img_y.setValue(1280)
        self.img_y.setToolTip("图片Y轴绝对坐标（像素）")
        
        self.img_size = QSpinBox()
        self.img_size.setRange(50, 1500)
        self.img_size.setValue(420)
        self.img_size.setSingleStep(10)
        self.img_size.setToolTip("图片大小（像素）")
        
        img_layout.addWidget(self.enable_image, 0, 0, 1, 2)
        img_layout.addWidget(QLabel("X轴坐标 (像素):"), 1, 0)
        img_layout.addWidget(self.img_x, 1, 1)
        img_layout.addWidget(QLabel("Y轴坐标 (像素):"), 2, 0)
        img_layout.addWidget(self.img_y, 2, 1)
        img_layout.addWidget(QLabel("图片大小 (像素):"), 3, 0)
        img_layout.addWidget(self.img_size, 3, 1)
        
        img_group.setLayout(img_layout)
        
        # 删除字幕位置设置组（已整合到字幕样式组中）
        
        # 背景设置组
        bg_group = QGroupBox("背景设置")
        bg_group.setMinimumHeight(200)  # 设置最小高度
        bg_layout = QGridLayout()
        bg_layout.setSpacing(6)  # 减少背景设置组间距
        bg_layout.setContentsMargins(8, 8, 8, 8)  # 减少背景设置组边距
        
        # 启用透明背景开关
        self.enable_background = QCheckBox("启用透明背景")
        self.enable_background.setChecked(True)
        self.enable_background.setToolTip("勾选后字幕会有透明背景")
        
        self.bg_width = QSpinBox()
        self.bg_width.setRange(500, 1500)
        self.bg_width.setValue(1000)
        self.bg_width.setSingleStep(50)
        self.bg_width.setToolTip("背景宽度（像素）")
        
        self.bg_height = QSpinBox()
        self.bg_height.setRange(100, 500)
        self.bg_height.setValue(180)
        self.bg_height.setSingleStep(10)
        self.bg_height.setToolTip("背景高度（像素）")
        
        # 背景坐标设置
        self.bg_x = QSpinBox()
        self.bg_x.setRange(-9999, 9999)
        self.bg_x.setValue(-50)
        self.bg_x.setToolTip("背景X轴绝对坐标（像素）")
        
        self.bg_y = QSpinBox()
        self.bg_y.setRange(-9999, 9999)
        self.bg_y.setValue(1100)
        self.bg_y.setToolTip("背景Y轴绝对坐标（像素）")
        
        bg_layout.addWidget(self.enable_background, 0, 0, 1, 2)
        bg_layout.addWidget(QLabel("背景宽度 (像素):"), 1, 0)
        bg_layout.addWidget(self.bg_width, 1, 1)
        bg_layout.addWidget(QLabel("背景高度 (像素):"), 2, 0)
        bg_layout.addWidget(self.bg_height, 2, 1)
        bg_layout.addWidget(QLabel("X坐标 (像素):"), 3, 0)
        bg_layout.addWidget(self.bg_x, 3, 1)
        bg_layout.addWidget(QLabel("Y坐标 (像素):"), 4, 0)
        bg_layout.addWidget(self.bg_y, 4, 1)
        
        # 添加去水印设置说明到背景设置下方
        watermark_desc = QLabel("通过放大视频然后裁剪来去除边缘水印")
        watermark_desc.setStyleSheet("color: gray; font-size: 12px;")
        bg_layout.addWidget(watermark_desc, 5, 0, 1, 2)
        
        bg_group.setLayout(bg_layout)
        
        # 智能语音组
        material_group = QGroupBox("智能语音")
        material_group.setMinimumHeight(180)  # 设置最小高度
        material_layout = QGridLayout()
        material_layout.setSpacing(6)  # 减少素材选择组间距
        material_layout.setContentsMargins(8, 8, 8, 8)  # 减少素材选择组边距
        
        # 智能语音勾选框
        self.enable_voice = QCheckBox("启用智能语音")
        self.enable_voice.setChecked(False)
        self.enable_voice.setToolTip("勾选后会为视频添加AI配音")
        
        # 语言选择
        self.voice_language_combo = QComboBox()
        self.populate_voice_languages()  # 填充语言选项
        self.voice_language_combo.currentTextChanged.connect(self.on_voice_language_changed)  # 添加语言变化事件
        
        # 音色选择
        self.voice_type_combo = QComboBox()
        self.populate_voice_types()  # 填充音色选项
        
        # 自动匹配时长
        self.auto_match_duration = QCheckBox("自动匹配时长")
        self.auto_match_duration.setChecked(True)
        self.auto_match_duration.setToolTip("勾选后会通过调节播放速度使音频时长与视频一致，检测视频时长和生成的配音时长，通过让配音时长变速去匹配视频时长")
        self.auto_match_duration.stateChanged.connect(self.on_auto_match_duration_changed)  # 添加状态变化事件
        
        # 音量调节
        self.voice_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.voice_volume_slider.setRange(0, 100)
        self.voice_volume_slider.setValue(100)
        self.voice_volume_label = QLabel("100%")
        self.voice_volume_slider.valueChanged.connect(
            lambda value: self.voice_volume_label.setText(f"{value}%")
        )
        
        voice_volume_layout = QHBoxLayout()
        voice_volume_layout.setSpacing(5)  # 减少音量布局间距
        voice_volume_layout.addWidget(self.voice_volume_slider)
        voice_volume_layout.addWidget(self.voice_volume_label)
        
        material_layout.addWidget(self.enable_voice, 0, 0, 1, 2)
        material_layout.addWidget(QLabel("语言:"), 1, 0)
        material_layout.addWidget(self.voice_language_combo, 1, 1)
        material_layout.addWidget(QLabel("音色:"), 2, 0)
        material_layout.addWidget(self.voice_type_combo, 2, 1)
        material_layout.addWidget(self.auto_match_duration, 3, 0, 1, 2)  # 添加自动匹配时长控件
        material_layout.addWidget(QLabel("音量:"), 4, 0)
        material_layout.addLayout(voice_volume_layout, 4, 1)
        
        material_group.setLayout(material_layout)
        
        # 音乐设置组
        music_group = QGroupBox("音乐设置")
        music_group.setMinimumHeight(180)
        music_group.setMaximumHeight(200)
        music_layout = QGridLayout()
        music_layout.setSpacing(6)  # 减少音乐设置组间距
        music_layout.setContentsMargins(8, 8, 8, 8)  # 减少音乐设置组边距
        
        # 开关控制
        self.enable_music = QCheckBox("启用背景音乐")
        self.enable_music.setChecked(False)
        self.enable_music.stateChanged.connect(self.on_music_enabled_changed)
        music_layout.addWidget(self.enable_music, 0, 0, 1, 2)
        
        # 音乐文件/文件夹选择
        self.music_path = QLineEdit()
        self.music_path.setReadOnly(True)
        self.music_path.setPlaceholderText("选择音乐文件或文件夹")
        music_file_btn = QPushButton("选择音乐文件")
        music_file_btn.clicked.connect(self.select_music_file)
        music_folder_btn = QPushButton("选择音乐文件夹")
        music_folder_btn.clicked.connect(self.select_music_folder)
        music_file_btn.setMaximumWidth(100)  # 限制按钮宽度
        music_folder_btn.setMaximumWidth(120)  # 限制按钮宽度
        
        music_layout.addWidget(QLabel("音乐路径:"), 1, 0)
        music_layout.addWidget(self.music_path, 1, 1)
        music_layout.addWidget(music_file_btn, 2, 0)
        music_layout.addWidget(music_folder_btn, 2, 1)
        
        # 音乐匹配模式
        self.music_mode = QComboBox()
        self.music_mode.addItem("单一模式", "single")
        self.music_mode.addItem("顺序模式", "sequence")
        self.music_mode.addItem("随机模式", "random")
        
        music_layout.addWidget(QLabel("匹配模式:"), 3, 0)
        music_layout.addWidget(self.music_mode, 3, 1)
        
        # 音量调节
        self.music_volume = QSlider(Qt.Orientation.Horizontal)
        self.music_volume.setRange(0, 100)
        self.music_volume.setValue(50)
        self.music_volume.valueChanged.connect(self.on_volume_changed)
        
        self.volume_label = QLabel("50%")
        self.volume_label.setMinimumWidth(40)
        
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(5)  # 减少音量布局间距
        volume_layout.addWidget(self.music_volume)
        volume_layout.addWidget(self.volume_label)
        
        music_layout.addWidget(QLabel("音量:"), 4, 0)
        music_layout.addLayout(volume_layout, 4, 1)
        
        music_group.setLayout(music_layout)
        
        # 保存按钮引用以便后续启用/禁用
        self.music_file_btn = music_file_btn
        self.music_folder_btn = music_folder_btn
        
        # 初始状态下禁用音乐相关控件
        self.music_path.setEnabled(False)
        self.music_file_btn.setEnabled(False)
        self.music_folder_btn.setEnabled(False)
        self.music_mode.setEnabled(False)
        self.music_volume.setEnabled(False)
        
        # 动态字幕设置组（添加到音乐设置下方）
        dynamic_subtitle_group = QGroupBox("动态字幕设置")
        dynamic_subtitle_group.setMinimumHeight(150)
        dynamic_subtitle_group.setMaximumHeight(170)
        dynamic_subtitle_layout = QGridLayout()
        dynamic_subtitle_layout.setSpacing(6)
        dynamic_subtitle_layout.setContentsMargins(8, 8, 8, 8)
        
        # 启用动态字幕勾选框
        self.enable_dynamic_subtitle = QCheckBox("启用动态字幕")
        self.enable_dynamic_subtitle.setChecked(False)
        self.enable_dynamic_subtitle.setToolTip("勾选后视频中会添加动态字幕效果")
        
        # 动画样式选择
        self.animation_style_combo = QComboBox()
        self.animation_style_combo.addItem("高亮放大", "highlight")
        self.animation_style_combo.addItem("弹跳效果", "bounce")
        self.animation_style_combo.addItem("发光效果", "glow")
        
        # 动画强度调节
        self.animation_intensity = QDoubleSpinBox()
        self.animation_intensity.setRange(0.5, 3.0)
        self.animation_intensity.setValue(1.5)
        self.animation_intensity.setSingleStep(0.1)
        self.animation_intensity.setDecimals(1)
        
        # 高亮颜色选择
        self.highlight_color_combo = QComboBox()
        self.highlight_color_combo.addItem("金色", "#FFD700")
        self.highlight_color_combo.addItem("红色", "#FF6B6B")
        self.highlight_color_combo.addItem("青色", "#4ECDC4")
        self.highlight_color_combo.addItem("紫色", "#9B59B6")
        self.highlight_color_combo.addItem("橙色", "#FF8C00")
        
        # 匹配模式选择
        self.match_mode_combo = QComboBox()
        self.match_mode_combo.addItem("指定样式", "fixed")
        self.match_mode_combo.addItem("随机样式", "random")
        self.match_mode_combo.addItem("循环样式", "cycle")
        
        dynamic_subtitle_layout.addWidget(self.enable_dynamic_subtitle, 0, 0, 1, 2)
        dynamic_subtitle_layout.addWidget(QLabel("动画样式:"), 1, 0)
        dynamic_subtitle_layout.addWidget(self.animation_style_combo, 1, 1)
        dynamic_subtitle_layout.addWidget(QLabel("动画强度:"), 2, 0)
        dynamic_subtitle_layout.addWidget(self.animation_intensity, 2, 1)
        dynamic_subtitle_layout.addWidget(QLabel("高亮颜色:"), 3, 0)
        dynamic_subtitle_layout.addWidget(self.highlight_color_combo, 3, 1)
        dynamic_subtitle_layout.addWidget(QLabel("匹配模式:"), 4, 0)
        dynamic_subtitle_layout.addWidget(self.match_mode_combo, 4, 1)
        
        dynamic_subtitle_group.setLayout(dynamic_subtitle_layout)
        
        # GIF设置组
        gif_group = QGroupBox("GIF动画设置")
        gif_group.setMinimumHeight(200)
        gif_group.setMaximumHeight(220)
        gif_layout = QGridLayout()
        gif_layout.setSpacing(6)  # 减少GIF设置组间距
        gif_layout.setContentsMargins(8, 8, 8, 8)  # 减少GIF设置组边距
        
        # 启用GIF动图复选框
        self.enable_gif = QCheckBox("启用GIF动图")
        self.enable_gif.setChecked(False)
        self.enable_gif.setToolTip("勾选后视频中会添加透明背景GIF动画")
        gif_layout.addWidget(self.enable_gif, 0, 0, 1, 3)
        
        # GIF路径选择
        self.gif_path = QLineEdit()
        self.gif_path.setReadOnly(True)
        self.gif_path.setPlaceholderText("选择GIF文件")
        gif_browse_btn = QPushButton("浏览GIF")
        gif_browse_btn.clicked.connect(self.select_gif_file)
        gif_browse_btn.setMaximumWidth(80)  # 限制按钮宽度
        
        gif_layout.addWidget(QLabel("GIF路径:"), 1, 0)
        gif_layout.addWidget(self.gif_path, 1, 1)
        gif_layout.addWidget(gif_browse_btn, 1, 2)
        
        # GIF循环次数（保留功能但不显示UI控件）
        self.gif_loop_count = QSpinBox()
        self.gif_loop_count.setRange(-1, 999)  # -1表示无限循环
        self.gif_loop_count.setValue(-1)
        self.gif_loop_count.setVisible(False)  # 隐藏UI控件
        
        # GIF缩放系数
        self.gif_scale = QDoubleSpinBox()
        self.gif_scale.setRange(0.1, 5.0)
        self.gif_scale.setValue(1.0)
        self.gif_scale.setSingleStep(0.1)
        self.gif_scale.setDecimals(1)
        self.gif_scale.setToolTip("设置GIF的缩放比例，1.0为原始大小")
        
        gif_layout.addWidget(QLabel("缩放系数:"), 3, 0)
        gif_layout.addWidget(self.gif_scale, 3, 1)
        
        # GIF旋转角度
        self.gif_rotation = QSpinBox()
        self.gif_rotation.setRange(0, 359)
        self.gif_rotation.setValue(0)
        self.gif_rotation.setSuffix("°")
        self.gif_rotation.setToolTip("设置GIF的旋转角度，0-359度")
        
        gif_layout.addWidget(QLabel("旋转角度:"), 4, 0)
        gif_layout.addWidget(self.gif_rotation, 4, 1)
        
        # GIF位置设置
        self.gif_x = QSpinBox()
        self.gif_x.setRange(-2000, 2000)
        self.gif_x.setValue(800)
        self.gif_x.setToolTip("GIF左上角X坐标")
        
        self.gif_y = QSpinBox()
        self.gif_y.setRange(-2000, 2000)
        self.gif_y.setValue(100)
        self.gif_y.setToolTip("GIF左上角Y坐标")
        
        gif_layout.addWidget(QLabel("X坐标:"), 5, 0)
        gif_layout.addWidget(self.gif_x, 5, 1)
        gif_layout.addWidget(QLabel("Y坐标:"), 6, 0)
        gif_layout.addWidget(self.gif_y, 6, 1)
        
        gif_group.setLayout(gif_layout)
        
        # 去水印设置组（删除说明文字）
        watermark_group = QGroupBox("去水印设置")
        watermark_group.setMinimumHeight(100)
        watermark_group.setMaximumHeight(120)
        watermark_layout = QGridLayout()
        watermark_layout.setSpacing(6)  # 减少去水印设置组间距
        watermark_layout.setContentsMargins(8, 8, 8, 8)  # 减少去水印设置组边距
        
        # 缩放系数设置
        self.scale_factor = QDoubleSpinBox()
        self.scale_factor.setRange(1.0, 3.0)
        self.scale_factor.setValue(1.1)
        self.scale_factor.setSingleStep(0.1)
        self.scale_factor.setDecimals(1)
        self.scale_factor.setToolTip("设置视频缩放系数来去除水印，1.1表示放大到110%")
        
        watermark_layout.addWidget(QLabel("缩放系数:"), 0, 0)
        watermark_layout.addWidget(self.scale_factor, 0, 1)
        
        watermark_group.setLayout(watermark_layout)
        
        # 重新布局UI面板
        # 第二列：字幕样式、背景设置
        left_column_layout.addWidget(style_group)
        left_column_layout.addWidget(bg_group)
        left_column_layout.addStretch()
        
        # 第三列：动态字幕设置、音乐设置
        middle_column_layout = QVBoxLayout()
        middle_column_layout.setSpacing(12)
        middle_column_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建中间列容器
        middle_column = QWidget()
        middle_column.setLayout(middle_column_layout)
        
        middle_column_layout.addWidget(material_group)
        middle_column_layout.addWidget(music_group)
        middle_column_layout.addWidget(dynamic_subtitle_group)  # 添加动态字幕设置
        middle_column_layout.addStretch()
        
        # 第四列：图片设置、gif动画设置、去水印设置、智能语音设置
        right_column_layout.addWidget(img_group)
        right_column_layout.addWidget(gif_group)
        right_column_layout.addWidget(watermark_group)  # 去水印设置放在gif动图设置下方
        right_column_layout.addStretch()
        
        # 添加三列到主要水平布局
        right_main_layout.addWidget(left_column)
        right_main_layout.addWidget(middle_column)
        right_main_layout.addWidget(right_column)
        
        # 将左右两侧添加到分栏器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # 设置分栏器初始大小
        # 第一列宽度为原来宽度的70%，第二、三、四列宽度相同
        splitter.setSizes([245, 875])  # 调整比例以更好地利用空间
        
        # 添加分栏器到主布局
        main_layout.addWidget(splitter)
        
        # 操作按钮
        # 创建底部按钮区域容器
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        
        # 添加说明标签
        process_label = QLabel("准备好所有设置后，点击下方按钮开始处理视频:")
        process_label.setStyleSheet("font-weight: bold; color: #3498db;")
        
        # 处理按钮
        process_btn = QPushButton("处理所有视频")
        process_btn.setObjectName("primaryButton")
        process_btn.setMinimumHeight(40)  # 增加按钮高度
        process_btn.setMinimumWidth(1100)  # 调整宽度与三列板块总宽相等
        process_btn.setStyleSheet("""
            QPushButton#primaryButton {
                background-color: #0070f3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                min-height: 36px;
            }
            QPushButton#primaryButton:hover {
                background-color: #0084ff;
            }
            QPushButton#primaryButton:pressed {
                background-color: #0060d0;
            }
        """)
        process_btn.clicked.connect(self.process_videos)
        
        # 将按钮添加到底部布局
        bottom_layout.addWidget(process_label)
        bottom_layout.addStretch(1)  # 添加弹性空间
        bottom_layout.addWidget(process_btn)
        bottom_layout.addStretch(1)  # 添加弹性空间
        
        # 将底部容器添加到主布局
        main_layout.addWidget(bottom_container)
    
    def init_settings_tab(self):
        """初始化设置标签页"""
        layout = QVBoxLayout(self.settings_tab)
        layout.setSpacing(5)  # 减少主布局间距
        layout.setContentsMargins(5, 5, 5, 5)  # 减少边距
        
        # 字体设置组
        font_group = QGroupBox("字体设置")
        font_layout = QGridLayout()
        font_layout.setSpacing(3)  # 减少字体组间距
        font_layout.setContentsMargins(5, 5, 5, 5)  # 减少字体组边距
        
        self.font_path_label = QLabel("字体目录: " + str(get_data_path("fonts")))
        font_open_btn = QPushButton("打开字体目录")
        font_open_btn.clicked.connect(self.open_font_dir)
        font_open_btn.setMaximumWidth(120)  # 限制按钮宽度
        
        font_layout.addWidget(self.font_path_label, 0, 0, 1, 2)
        font_layout.addWidget(font_open_btn, 1, 0)
        
        font_group.setLayout(font_layout)
        
        # 样式设置组
        style_config_group = QGroupBox("样式配置")
        style_config_layout = QGridLayout()
        style_config_layout.setSpacing(3)  # 减少样式配置组间距
        style_config_layout.setContentsMargins(5, 5, 5, 5)  # 减少样式配置组边距
        
        self.style_path_label = QLabel("样式配置文件: " + str(get_data_path("config") / "subtitle_styles.ini"))
        style_open_btn = QPushButton("打开样式配置")
        style_open_btn.clicked.connect(self.open_style_config)
        style_reload_btn = QPushButton("重新加载样式")
        style_reload_btn.clicked.connect(self.reload_styles)
        style_open_btn.setMaximumWidth(120)  # 限制按钮宽度
        style_reload_btn.setMaximumWidth(120)  # 限制按钮宽度
        
        style_config_layout.addWidget(self.style_path_label, 0, 0, 1, 2)
        style_config_layout.addWidget(style_open_btn, 1, 0)
        style_config_layout.addWidget(style_reload_btn, 1, 1)
        
        style_config_group.setLayout(style_config_layout)
        
        # 默认设置组
        default_group = QGroupBox("默认设置")
        default_layout = QGridLayout()
        default_layout.setSpacing(3)  # 减少默认设置组间距
        default_layout.setContentsMargins(5, 5, 5, 5)  # 减少默认设置组边距
        
        self.save_paths_check = QCheckBox("记住上一次的文件路径")
        self.save_paths_check.setChecked(True)
        
        self.default_qt_check = QCheckBox("默认使用QuickTime兼容模式")
        self.default_qt_check.setChecked(False)
        
        default_layout.addWidget(self.save_paths_check, 0, 0)
        default_layout.addWidget(self.default_qt_check, 1, 0)
        
        default_group.setLayout(default_layout)
        
        # 智能配音设置组
        voice_group = QGroupBox("智能配音设置")
        voice_layout = QGridLayout()
        voice_layout.setSpacing(3)  # 减少智能配音组间距
        voice_layout.setContentsMargins(5, 5, 5, 5)  # 减少智能配音组边距
        
        # API平台选择
        self.voice_api_combo = QComboBox()
        self.voice_api_combo.addItem("OpenAI-Edge-TTS", "edge_tts")
        self.voice_api_combo.addItem("ElevenLabs", "elevenlabs")
        self.voice_api_combo.currentTextChanged.connect(self.on_api_platform_changed)
        
        voice_layout.addWidget(QLabel("API平台:"), 0, 0)
        voice_layout.addWidget(self.voice_api_combo, 0, 1)
        
        # API Key输入
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("输入API Key")
        
        api_test_btn = QPushButton("测试连接")
        api_test_btn.clicked.connect(self.test_api_connection)
        api_test_btn.setMaximumWidth(100)  # 限制按钮宽度
        
        voice_layout.addWidget(QLabel("API Key:"), 1, 0)
        voice_layout.addWidget(self.api_key_input, 1, 1)
        voice_layout.addWidget(api_test_btn, 1, 2)
        
        # TTS文本输入
        self.tts_text_input = QTextEdit()
        self.tts_text_input.setMaximumHeight(60)
        self.tts_text_input.setPlaceholderText("输入要转换为语音的文本内容")
        
        voice_layout.addWidget(QLabel("TTS文本:"), 2, 0)
        voice_layout.addWidget(self.tts_text_input, 2, 1, 1, 2)
        
        # 自动匹配时长
        self.auto_match_duration = QCheckBox("自动匹配时长")
        self.auto_match_duration.setChecked(True)
        self.auto_match_duration.setToolTip("勾选后会通过调节播放速度使音频时长与视频一致，检测视频时长和生成的配音时长，通过让配音时长变速去匹配视频时长")
        
        voice_layout.addWidget(self.auto_match_duration, 3, 0)
        
        # TTS音量控制
        tts_volume_layout = QHBoxLayout()
        self.tts_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_volume_slider.setRange(0, 100)
        self.tts_volume_slider.setValue(100)
        self.tts_volume_label = QLabel("100%")
        self.tts_volume_slider.valueChanged.connect(
            lambda value: self.tts_volume_label.setText(f"{value}%")
        )
        
        tts_volume_layout.addWidget(self.tts_volume_slider)
        tts_volume_layout.addWidget(self.tts_volume_label)
        
        voice_layout.addWidget(QLabel("TTS音量:"), 4, 0)
        voice_layout.addLayout(tts_volume_layout, 4, 1, 1, 2)
        
        voice_group.setLayout(voice_layout)
        
        # 导出质量设置组
        quality_group = QGroupBox("导出质量设置 (TikTok优化)")
        quality_layout = QGridLayout()
        quality_layout.setSpacing(3)  # 减少导出质量组间距
        quality_layout.setContentsMargins(5, 5, 5, 5)  # 减少导出质量组边距
        
        # CRF质量设置
        self.crf_value = QSpinBox()
        self.crf_value.setRange(0, 51)
        self.crf_value.setValue(18)
        self.crf_value.setToolTip("CRF值，越小质量越高。推荐: 15(极高质量) 18(高质量) 23(中等质量)")
        
        quality_layout.addWidget(QLabel("CRF质量:"), 0, 0)
        quality_layout.addWidget(self.crf_value, 0, 1)
        
        # 编码预设
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("极快 (ultrafast) - 编码最快但文件较大", "ultrafast")
        self.preset_combo.addItem("很快 (veryfast) - 快速编码", "veryfast")
        self.preset_combo.addItem("快速 (fast) - 平衡速度和质量", "fast")
        self.preset_combo.addItem("中等 (medium) - 默认设置", "medium")
        self.preset_combo.addItem("慢速 (slow) - 更好的压缩效率 (推荐)", "slow")
        self.preset_combo.addItem("很慢 (veryslow) - 最佳压缩效率", "veryslow")
        self.preset_combo.setCurrentIndex(4)  # 默认选择slow
        self.preset_combo.setToolTip("编码预设，影响编码速度和文件大小。TikTok推荐slow获得更好的质量")
        
        quality_layout.addWidget(QLabel("编码预设:"), 0, 2)
        quality_layout.addWidget(self.preset_combo, 0, 3)
        
        # Profile设置
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Baseline - 最低兼容性", "baseline")
        self.profile_combo.addItem("Main - 中等兼容性", "main")
        self.profile_combo.addItem("High - 最佳质量 (推荐)", "high")
        self.profile_combo.setCurrentIndex(2)  # 默认选择high
        self.profile_combo.setToolTip("H.264 Profile设置，High提供最佳质量和压缩效率")
        
        quality_layout.addWidget(QLabel("H.264 Profile:"), 1, 0)
        quality_layout.addWidget(self.profile_combo, 1, 1)
        
        # Level设置
        self.level_combo = QComboBox()
        self.level_combo.addItem("3.1 - 基本兼容性", "3.1")
        self.level_combo.addItem("4.0 - 高清支持", "4.0")
        self.level_combo.addItem("4.1 - 推荐设置", "4.1")
        self.level_combo.addItem("4.2 - 高级设置", "4.2")
        self.level_combo.setCurrentIndex(2)  # 默认选择 4.1
        self.level_combo.setToolTip("H.264 Level设置，4.1支持高清竖屏视频")
        
        quality_layout.addWidget(QLabel("H.264 Level:"), 1, 2)
        quality_layout.addWidget(self.level_combo, 1, 3)
        
        # 最大码率设置
        self.maxrate_spin = QSpinBox()
        self.maxrate_spin.setRange(1000, 20000)
        self.maxrate_spin.setValue(8000)
        self.maxrate_spin.setSuffix(" kbps")
        self.maxrate_spin.setToolTip("最大码率限制，TikTok推荐 6000-8000 kbps")
        
        quality_layout.addWidget(QLabel("最大码率:"), 2, 0)
        quality_layout.addWidget(self.maxrate_spin, 2, 1)
        
        # 缓冲区大小
        self.bufsize_spin = QSpinBox()
        self.bufsize_spin.setRange(2000, 40000)
        self.bufsize_spin.setValue(16000)
        self.bufsize_spin.setSuffix(" kbps")
        self.bufsize_spin.setToolTip("缓冲区大小，通常设为最大码率的2倍")
        
        quality_layout.addWidget(QLabel("缓冲区大小:"), 2, 2)
        quality_layout.addWidget(self.bufsize_spin, 2, 3)
        
        # GOP大小 (关键帧间隔)
        self.gop_spin = QSpinBox()
        self.gop_spin.setRange(15, 60)
        self.gop_spin.setValue(30)
        self.gop_spin.setToolTip("GOP大小(关键帧间隔)，30表示每30帧一个关键帧")
        
        quality_layout.addWidget(QLabel("GOP大小:"), 3, 0)
        quality_layout.addWidget(self.gop_spin, 3, 1)
        
        # Tune设置
        self.tune_combo = QComboBox()
        self.tune_combo.addItem("无优化", "none")
        self.tune_combo.addItem("电影内容 (film) - 推荐", "film")
        self.tune_combo.addItem("动画内容 (animation)", "animation")
        self.tune_combo.addItem("精细细节 (grain)", "grain")
        self.tune_combo.addItem("静态图像 (stillimage)", "stillimage")
        self.tune_combo.setCurrentIndex(1)  # 默认选择film
        self.tune_combo.setToolTip("针对不同内容类型的优化设置")
        
        quality_layout.addWidget(QLabel("内容优化:"), 3, 2)
        quality_layout.addWidget(self.tune_combo, 3, 3)
        
        # 像素格式
        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItem("yuv420p - 标准格式 (推荐)", "yuv420p")
        self.pixfmt_combo.addItem("yuv422p - 高质量格式", "yuv422p")
        self.pixfmt_combo.addItem("yuv444p - 最高质量格式", "yuv444p")
        self.pixfmt_combo.setCurrentIndex(0)  # 默认yuv420p
        self.pixfmt_combo.setToolTip("像素格式，yuv420p兼容性最佳")
        
        quality_layout.addWidget(QLabel("像素格式:"), 4, 0)
        quality_layout.addWidget(self.pixfmt_combo, 4, 1)
        
        quality_group.setLayout(quality_layout)
        
        # 保存按钮
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMaximumWidth(100)  # 限制按钮宽度
        
        # 添加所有组件到布局
        layout.addWidget(font_group)
        layout.addWidget(style_config_group)
        layout.addWidget(default_group)
        layout.addWidget(quality_group)  # 添加质量设置组
        layout.addWidget(voice_group)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)  # 左对齐保存按钮
        layout.addStretch()
    
    def populate_style_combo(self, combo_box):
        """填充样式下拉框"""
        combo_box.clear()
        combo_box.addItem("随机", "random")
        
        # 从样式配置中读取可用样式
        styles = []
        try:
            # 确保 style_config 是 ConfigParser 实例
            if isinstance(self.style_config, configparser.ConfigParser):
                for section in self.style_config.sections():
                    if section.startswith("styles."):
                        style_name = section.replace("styles.", "")
                        styles.append(style_name)
        except Exception:
            # 如果读取失败，就使用空列表
            pass
        
        # 添加样式到下拉框
        for style in sorted(styles):
            # 获取样式描述
            style_section = f"styles.{style}"
            description = ""
            
            # 尝试获取注释作为描述
            try:
                if isinstance(self.style_config, configparser.ConfigParser):
                    if self.style_config.has_option(style_section, "; 样式配置"):
                        comment_text = self.style_config.get(style_section, "; 样式配置")
                        for line in comment_text.split("\n"):
                            if line.strip() and not line.strip().startswith("["):
                                description = line.strip()
                                break
                    
                    # 如果没有注释，查看第一个非空行
                    if not description:
                        for option in self.style_config.options(style_section):
                            if option.startswith(";") and not option.startswith("; "):
                                description = option.lstrip(";").strip()
                                break
            except Exception:
                # 如果读取失败，就使用默认描述
                pass
            
            # 如果仍然没有描述，使用样式名称
            if not description:
                description = style
            
            # 添加到下拉框
            combo_box.addItem(f"{style} - {description}", style)
    
    def add_video_files(self):
        """添加视频文件到列表"""
        initial_dir = self.settings.value("last_video_dir", "")
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", 
            initial_dir,
            "视频文件 (*.mp4 *.mov *.avi *.wmv *.mkv);;所有文件 (*)"
        )
        
        if file_paths:
            # 保存最后访问的目录
            self.settings.setValue("last_video_dir", str(Path(file_paths[0]).parent))
            
            # 添加文件到列表
            for file_path in file_paths:
                if not self._is_file_in_list(file_path):
                    self.video_list.addItem(file_path)
            
            # 如果输出目录为空，设为默认输出目录
            if not self.output_dir.text() and file_paths:
                self.output_dir.setText(self.default_output_dir)
    
    def add_folder_for_processing(self):
        """添加文件夹到处理列表（作为整体处理）"""
        initial_dir = self.settings.value("last_video_dir", "")
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含视频文件的文件夹（将作为整体处理）",
            initial_dir
        )
        
        if folder_path:
            self.settings.setValue("last_video_dir", folder_path)
            
            # 添加文件夹路径到列表
            if not self._is_file_in_list(folder_path):
                self.video_list.addItem(folder_path)
                print(f"添加文件夹到处理列表: {folder_path}")
            
            # 如果输出目录为空，设置默认输出目录
            if not self.output_dir.text():
                folder_path_obj = Path(folder_path)
                default_output = folder_path_obj.parent / "output"
                self.output_dir.setText(str(default_output))
    
    def add_mixed_folder(self):
        """添加混合文件夹到处理列表（分别处理文件夹中的文件和子文件夹）"""
        initial_dir = self.settings.value("last_video_dir", "")
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含视频文件和子文件夹的文件夹（将分别处理）",
            initial_dir
        )
        
        if folder_path:
            self.settings.setValue("last_video_dir", folder_path)
            
            # 查找文件夹中的所有项目（文件和子文件夹）
            video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.mkv']
            items_added = 0
            
            try:
                folder_path_obj = Path(folder_path)
                for item_path in folder_path_obj.iterdir():
                    if item_path.is_file() and item_path.suffix.lower() in video_extensions:
                        # 添加视频文件
                        if not self._is_file_in_list(str(item_path)):
                            self.video_list.addItem(str(item_path))
                            items_added += 1
                    elif item_path.is_dir():
                        # 添加子文件夹
                        if not self._is_file_in_list(str(item_path)):
                            self.video_list.addItem(str(item_path))
                            items_added += 1
                
                # 如果找到了项目并且输出目录为空，设置默认输出目录
                if items_added > 0 and not self.output_dir.text():
                    default_output = folder_path_obj / "output"
                    self.output_dir.setText(str(default_output))
                    
                if items_added == 0:
                    QMessageBox.information(self, "提示", "所选文件夹中没有找到视频文件或子文件夹")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件夹失败: {str(e)}")
    
    def add_video_folder(self):
        """添加文件夹中的所有视频文件到列表"""
        initial_dir = self.settings.value("last_video_dir", "")
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含视频文件的文件夹",
            initial_dir
        )
        
        if folder_path:
            self.settings.setValue("last_video_dir", folder_path)
            
            # 查找文件夹中的视频文件
            video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.mkv']
            video_files = []
            
            try:
                folder_path_obj = Path(folder_path)
                for file_path in folder_path_obj.iterdir():
                    if (file_path.is_file() and 
                        file_path.suffix.lower() in video_extensions):
                        video_files.append(str(file_path))
                
                # 排序并添加到列表
                video_files.sort()
                for file_path in video_files:
                    if not self._is_file_in_list(file_path):
                        self.video_list.addItem(file_path)
            
                # 如果找到了视频并且输出目录为空，设置默认输出目录
                if video_files and not self.output_dir.text():
                    default_output = folder_path_obj / "output"
                    self.output_dir.setText(str(default_output))
                    
                if not video_files:
                    QMessageBox.information(self, "提示", "所选文件夹中没有找到视频文件")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件夹失败: {str(e)}")
    
    def _is_file_in_list(self, file_path):
        """检查文件是否已经在列表中"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item is not None and item.text() == file_path:
                return True
        return False
    
    def clear_video_list(self):
        """清空视频列表"""
        self.video_list.clear()
    
    def browse_output_dir(self):
        """浏览选择输出目录"""
        initial_dir = self.output_dir.text() or self.settings.value("last_output_dir", "")
        if not initial_dir and self.video_list.count() > 0:
            # 如果输出目录为空，使用第一个视频的目录作为起始
            first_item = self.video_list.item(0)
            if first_item is not None:
                initial_dir = str(Path(first_item.text()).parent)
            
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录",
            initial_dir
        )
        
        if dir_path:
            self.output_dir.setText(dir_path)
            self.settings.setValue("last_output_dir", dir_path)
    
    def process_videos(self):
        """处理所有添加到列表中的视频"""
        # 获取列表中的所有视频文件，而不仅是选中的
        video_count = self.video_list.count()
        if video_count == 0:
            QMessageBox.warning(self, "警告", "请先添加视频文件")
            return
        
        # 获取所有视频的路径，添加检查确保项目存在
        video_paths = []
        folder_paths = []
        
        for i in range(video_count):
            item = self.video_list.item(i)
            if item is not None:
                path = item.text()
                # 检查路径是文件还是文件夹
                if Path(path).is_file():
                    video_paths.append(path)
                elif Path(path).is_dir():
                    folder_paths.append(path)
        
        output_dir = self.output_dir.text()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return
        
        # 确保输出目录存在
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建输出目录: {str(e)}")
            return
            
        # 分类处理文件：小于9秒、大于等于9秒、文件夹
        short_videos = []    # 小于9秒的视频
        long_videos = []     # 大于等于9秒的视频
        folders = folder_paths  # 文件夹列表
        
        # 对视频文件按长度分类
        for video_path in video_paths:
            try:
                from utils import get_video_info
                video_info = get_video_info(video_path)
                if video_info:
                    _, _, duration = video_info
                    if duration < 9.0:
                        short_videos.append(video_path)
                    else:
                        long_videos.append(video_path)
                else:
                    # 如果无法获取视频信息，默认按长视频处理
                    long_videos.append(video_path)
            except Exception as e:
                print(f"获取视频信息失败 {video_path}: {e}")
                # 如果出错，默认按长视频处理
                long_videos.append(video_path)
        
        print(f"分类结果: 短视频({len(short_videos)}个), 长视频({len(long_videos)}个), 文件夹({len(folders)}个)")
        
        # 获取选择的样式和语言
        style_idx = self.style_combo.currentIndex()
        style = self.style_combo.itemData(style_idx)
        
        lang_idx = self.lang_combo.currentIndex()
        lang = self.lang_combo.itemData(lang_idx)
        
        # 获取所有设置参数
        quicktime_compatible = self.quicktime_check.isChecked()
        img_position_x = self.img_x.value()
        img_position_y = self.img_y.value()
        font_size = self.font_size.value()
        subtitle_width = self.subtitle_width.value()  # 获取字幕宽度参数
        subtitle_x = self.bg_x.value()  # 使用背景设置中的坐标
        subtitle_y = self.bg_y.value()  # 使用背景设置中的坐标
        bg_width = self.bg_width.value()
        bg_height = self.bg_height.value()
        img_size = self.img_size.value()
        
        # 获取新增的参数
        random_position = self.random_subtitle_position.isChecked()
        enable_subtitle = self.enable_subtitle.isChecked()
        enable_background = self.enable_background.isChecked()
        enable_image = self.enable_image.isChecked()
        
        # 获取音乐参数
        enable_music = self.enable_music.isChecked()
        music_path = self.music_path.text()
        music_mode = self.music_mode.currentData()
        music_volume = self.music_volume.value()
        
        # 获取文档路径
        document_path = self.document_path.text().strip() if hasattr(self, 'document_path') and self.document_path.text().strip() else None
        if document_path:
            print(f"使用用户选择的文档: {document_path}")
        else:
            print("未选择文档，将使用默认配置")
        
        # 获取图片路径
        image_path = self.image_path.text().strip() if hasattr(self, 'image_path') and self.image_path.text().strip() else None
        if image_path:
            print(f"使用用户选择的图片文件夹: {image_path}")
        else:
            print("未选择图片文件夹，将使用默认配置")
        
        # 获取GIF参数
        enable_gif = self.enable_gif.isChecked()
        gif_path = self.gif_path.text().strip()
        gif_loop_count = self.gif_loop_count.value()
        gif_scale = self.gif_scale.value()
        gif_x = self.gif_x.value()
        gif_y = self.gif_y.value()
        
        # 获取去水印参数
        scale_factor = self.scale_factor.value()
        
        # 获取质量设置参数
        quality_settings = {}
        if hasattr(self, 'crf_value'):
            quality_settings = {
                'crf_value': self.crf_value.value(),
                'preset_value': self.preset_combo.currentData(),
                'profile_value': self.profile_combo.currentData(),
                'level_value': self.level_combo.currentData(),
                'maxrate_value': self.maxrate_spin.value(),
                'bufsize_value': self.bufsize_spin.value(),
                'gop_value': self.gop_spin.value(),
                'tune_value': self.tune_combo.currentData(),
                'pixfmt_value': self.pixfmt_combo.currentData()
            }
        
        # 获取TTS参数
        enable_tts = False
        tts_voice = "zh-CN-XiaoxiaoNeural"
        tts_volume = 100
        tts_text = ""
        
        # 检查是否启用了TTS功能
        # 获取TTS参数
        enable_tts = False  # 默认不启用
        tts_voice = "zh-CN-XiaoxiaoNeural"
        tts_volume = 100
        tts_text = ""
        
        # 检查是否启用了智能语音
        if self.enable_voice.isChecked():
            enable_tts = True
            # 获取TTS相关参数
            tts_voice = self.voice_type_combo.currentData() or "zh-CN-XiaoxiaoNeural"
            tts_volume = self.voice_volume_slider.value()
            # 修改TTS文本获取逻辑：如果用户没有输入文本，则从字幕配置中获取
            user_tts_text = self.tts_text_input.toPlainText().strip() if hasattr(self, 'tts_text_input') else ""
            if user_tts_text:
                tts_text = user_tts_text
            else:
                # 如果用户没有输入TTS文本，则在处理每个视频时从字幕配置中获取对应的文本
                print("用户未输入TTS文本，将在处理每个视频时从字幕配置中获取...")
                tts_text = ""  # 将在处理每个视频时获取
            print(f"TTS设置: enable={enable_tts}, voice={tts_voice}, volume={tts_volume}, text='{tts_text}'")
        
        # 获取动态字幕参数
        enable_dynamic_subtitle = self.enable_dynamic_subtitle.isChecked()
        animation_style = self.animation_style_combo.currentData()
        animation_intensity = self.animation_intensity.value()
        highlight_color = self.highlight_color_combo.currentData()
        match_mode = self.match_mode_combo.currentData()
        
        print(f"[动态字幕] 参数设置: 启用={enable_dynamic_subtitle}, 样式={animation_style}, 强度={animation_intensity}, 颜色={highlight_color}, 模式={match_mode}")
        
        # 启动处理线程，传递分类后的文件列表
        self.processing_thread = ProcessingThread(
            short_videos, long_videos, folders, output_dir, style, lang, 
            quicktime_compatible, img_position_x, img_position_y,
            font_size, subtitle_width, subtitle_x, subtitle_y, bg_width, bg_height, img_size,
            self.subtitle_text_x.value(), self.subtitle_text_y.value(),
            random_position, enable_subtitle, enable_background, enable_image,
            enable_music, music_path, music_mode, music_volume,
            document_path, enable_gif, gif_path, gif_loop_count, gif_scale, self.gif_rotation.value(), gif_x, gif_y, scale_factor, image_path,
            quality_settings,  # 添加质量设置参数
            enable_tts, tts_voice, tts_volume, tts_text, self.auto_match_duration.isChecked(),  # 添加TTS参数和自动匹配时长参数
            enable_dynamic_subtitle, animation_style, animation_intensity, highlight_color, match_mode  # 添加动态字幕参数
        )
        
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.processing_complete.connect(self.processing_finished)
        self.processing_thread.processing_stage_updated.connect(self.update_processing_stage)
        
        # 禁用界面
        self.disable_ui()
        
        # 开始处理
        self.processing_thread.start()
        
        # 保存设置
        self.save_current_settings()
    
    def update_progress(self, value, message):
        """更新进度条和状态栏"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
        if self.status_bar is not None:
            self.status_bar.showMessage(message)
    
    def update_processing_stage(self, stage, progress_percent):
        """更新处理阶段信息"""
        # 这里可以添加更详细的处理阶段显示逻辑
        # 例如，在GUI中显示当前正在处理的阶段
        logging.info(f"当前处理阶段: {stage} ({progress_percent:.1f}%)")
    
    def processing_finished(self, success, stats):
        """处理完成后的操作"""
        # 恢复界面
        self.enable_ui()
        
        # 准备统计信息
        if isinstance(stats, dict):
            total_videos = stats.get('total_videos', 0)
            success_count = stats.get('success_count', 0)
            failed_count = stats.get('failed_count', 0)
            total_time = stats.get('total_time', 0)
            avg_time = stats.get('avg_time', 0)
            failed_videos = stats.get('failed_videos', [])
            output_dir = stats.get('output_dir', '')

            error_msg = stats.get('error', '')
            
            # 格式化时间
            def format_time(seconds):
                if seconds < 60:
                    return f"{seconds:.1f}秒"
                elif seconds < 3600:
                    minutes = int(seconds // 60)
                    secs = seconds % 60
                    return f"{minutes}分{secs:.1f}秒"
                else:
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = seconds % 60
                    return f"{hours}小时{minutes}分{secs:.1f}秒"
            
            # 弹窗内容
            if success:
                if success_count == total_videos:
                    title = "🎉 全部处理成功"
                    icon = QMessageBox.Icon.Information
                else:
                    title = "⚠️ 部分处理成功"
                    icon = QMessageBox.Icon.Warning
            else:
                title = "❌ 处理失败"
                icon = QMessageBox.Icon.Critical
            
            # 构建详细信息
            message = f"""📊 处理统计信息：

💹 生成视频数量：{success_count} / {total_videos} 个
⏱️ 总用时：{format_time(total_time)}
⏰ 平均单个视频耗时：{format_time(avg_time)}
"""
            
            if failed_count > 0:
                message += f"\n❌ 失败视频：{failed_count} 个"
                if len(failed_videos) <= 5:
                    message += f"\n失败文件：{', '.join(failed_videos)}"
                else:
                    message += f"\n失败文件：{', '.join(failed_videos[:5])}等..."
            
            if error_msg:
                message += f"\n\n错误信息：{error_msg}"
            
            # 创建自定义消息框
            msg_box = QMessageBox(self)
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            
            # 添加按钮
            ok_button = msg_box.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
            
            # 如果有成功处理的视频，添加打开输出目录按钮
            open_dir_button = None
            if success_count > 0 and output_dir and Path(output_dir).exists():
                open_dir_button = msg_box.addButton("📂 打开输出目录", QMessageBox.ButtonRole.ActionRole)
            
            # 显示对话框
            result = msg_box.exec_()
            
            # 处理按钮点击
            if msg_box.clickedButton() == open_dir_button:
                self.open_directory(output_dir)
                
        else:
            # 兼容旧版本，如果传入的是字符串
            if success:
                QMessageBox.information(self, "处理完成", str(stats))
            else:
                QMessageBox.warning(self, "处理失败", str(stats))
        
        # 如果处理失败且没有成功视频，自动打开输出目录以便检查
        if not success and isinstance(stats, dict):
            output_dir = stats.get('output_dir', self.output_dir.text())
            if output_dir and Path(output_dir).exists() and stats.get('success_count', 0) == 0:
                try:
                    self.open_directory(output_dir)
                except Exception:
                    pass  # 忽略打开目录的错误
    
    def disable_ui(self):
        """禁用界面控件"""
        self.tabs.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def enable_ui(self):
        """启用界面控件"""
        self.tabs.setEnabled(True)
        self.progress_bar.setValue(100)
    
    def open_directory(self, directory_path):
        """打开指定目录"""
        try:
            # 使用 pathlib.Path 确保路径格式正确
            path = Path(directory_path)
            if not path.exists():
                QMessageBox.warning(self, "警告", f"目录不存在: {directory_path}")
                return
            
            # 转换为绝对路径
            abs_path = path.resolve()
            
            # 根据不同平台打开目录
            if sys.platform == "win32":
                os.startfile(str(abs_path))
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", str(abs_path)], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            else:  # Linux
                subprocess.run(["xdg-open", str(abs_path)], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"无法打开目录: {str(e)}")
    
    def select_image_folder(self):
        """选择图片文件夹"""
        initial_dir = self.image_path.text() or self.settings.value("last_image_dir", "")
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含图片文件的文件夹",
            initial_dir
        )
        
        if folder_path:
            self.image_path.setText(folder_path)
            self.settings.setValue("last_image_dir", folder_path)
            
            # 检查文件夹中是否有图片文件
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']
            image_count = 0
            
            try:
                for file in os.listdir(folder_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        image_count += 1
                        
                if image_count == 0:
                    QMessageBox.information(self, "提示", "所选文件夹中没有找到图片文件")
                else:
                    QMessageBox.information(self, "成功", f"找到 {image_count} 个图片文件")
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件夹失败: {str(e)}")
    
    def clear_image_path(self):
        """清除图片路径"""
        self.image_path.clear()
    
    def open_font_dir(self):
        """打开字体目录"""
        font_dir = get_data_path("fonts")
        os.makedirs(font_dir, exist_ok=True)
        
        # 根据不同平台打开目录
        try:
            # 使用 pathlib.Path 确保路径格式正确
            path = Path(font_dir)
            if not path.exists():
                QMessageBox.warning(self, "警告", f"字体目录不存在: {font_dir}")
                return
            
            # 转换为绝对路径
            abs_path = path.resolve()
            
            # 根据不同平台打开目录
            if sys.platform == "win32":
                os.startfile(str(abs_path))
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", str(abs_path)], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            else:  # Linux
                subprocess.run(["xdg-open", str(abs_path)], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"无法打开字体目录: {str(e)}")
    

    
    def open_style_config(self):
        """打开样式配置文件"""
        style_config_path = get_data_path("config") / "subtitle_styles.ini"
        style_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not style_config_path.exists():
            QMessageBox.warning(self, "警告", "样式配置文件不存在")
            return
            
        # 根据不同平台打开文件
        try:
            if sys.platform == "win32":
                os.startfile(str(style_config_path))
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", "-t", str(style_config_path)], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            else:  # Linux
                subprocess.run(["xdg-open", str(style_config_path)], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"无法打开配置文件: {str(e)}")
    
    def reload_styles(self):
        """重新加载样式配置"""
        try:
            # 重新加载样式配置
            self.style_config = load_style_config()  # type: ignore
            
            # 重新填充样式下拉框
            self.populate_style_combo(self.style_combo)
            
            # 显示成功消息
            QMessageBox.information(self, "成功", "样式配置已重新加载")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重新加载样式配置失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def load_saved_settings(self):
        """加载保存的设置"""
        # 是否记住路径
        save_paths = self.settings.value("save_paths", True, type=bool)
        self.save_paths_check.setChecked(save_paths)
        
        # QuickTime兼容模式
        quicktime = self.settings.value("default_quicktime", False, type=bool)
        self.default_qt_check.setChecked(quicktime)
        self.quicktime_check.setChecked(quicktime)
        
        # 路径设置
        if save_paths:
            # 输出目录
            saved_output_dir = self.settings.value("output_dir", "")
            if saved_output_dir:
                self.output_dir.setText(saved_output_dir)
            else:
                self.output_dir.setText(self.default_output_dir)
        else:
            # 使用默认输出目录
            self.output_dir.setText(self.default_output_dir)
        
        # 样式和语言
        style_idx = self.settings.value("style_idx", 0, type=int)
        if 0 <= style_idx < self.style_combo.count():
            self.style_combo.setCurrentIndex(style_idx)
        
        lang_idx = self.settings.value("lang_idx", 0, type=int)
        if 0 <= lang_idx < self.lang_combo.count():
            self.lang_combo.setCurrentIndex(lang_idx)
                
        # 图片位置
        self.img_x.setValue(self.settings.value("img_x", 100, type=int))
        self.img_y.setValue(self.settings.value("img_y", 1280, type=int)) # 更新为1280
        
        # 字体大小
        self.font_size.setValue(self.settings.value("font_size", 70, type=int))
        
        # 字幕宽度
        self.subtitle_width.setValue(self.settings.value("subtitle_width", 600, type=int))
        
        # 字幕位置
        self.subtitle_text_x.setValue(self.settings.value("subtitle_text_x", 0, type=int))
        self.subtitle_text_y.setValue(self.settings.value("subtitle_text_y", 1190, type=int))
        
        # 背景大小
        self.bg_width.setValue(self.settings.value("bg_width", 1000, type=int))
        self.bg_height.setValue(self.settings.value("bg_height", 180, type=int))
        
        # 图片大小
        self.img_size.setValue(self.settings.value("img_size", 420, type=int))
        
        # 字幕位置随机化
        self.random_subtitle_position.setChecked(self.settings.value("random_subtitle_position", False, type=bool))
        
        # 素材选择
        self.enable_subtitle.setChecked(self.settings.value("enable_subtitle", True, type=bool))
        self.enable_background.setChecked(self.settings.value("enable_background", True, type=bool))
        self.enable_image.setChecked(self.settings.value("enable_image", True, type=bool))
        self.enable_voice.setChecked(self.settings.value("enable_voice", False, type=bool))
        self.enable_gif.setChecked(self.settings.value("enable_gif", False, type=bool))
        
        # GIF设置
        self.gif_path.setText(self.settings.value("gif_path", ""))
        self.gif_loop_count.setValue(self.settings.value("gif_loop_count", -1, type=int))
        self.gif_scale.setValue(self.settings.value("gif_scale", 1.0, type=float))
        self.gif_x.setValue(self.settings.value("gif_x", 800, type=int))
        self.gif_y.setValue(self.settings.value("gif_y", 100, type=int))
        
        # 去水印设置
        self.scale_factor.setValue(self.settings.value("scale_factor", 1.1, type=float))
        
        # 音乐设置
        self.enable_music.setChecked(self.settings.value("enable_music", False, type=bool))
        self.music_path.setText(self.settings.value("music_path", ""))
        music_mode_idx = self.settings.value("music_mode_idx", 0, type=int)
        if 0 <= music_mode_idx < self.music_mode.count():
            self.music_mode.setCurrentIndex(music_mode_idx)
        self.music_volume.setValue(self.settings.value("music_volume", 50, type=int))
        
        # 智能配音设置
        voice_api_idx = self.settings.value("voice_api_idx", 0, type=int)
        if 0 <= voice_api_idx < self.voice_api_combo.count():
            self.voice_api_combo.setCurrentIndex(voice_api_idx)
        
        # 删除语言、音色、性别参数
        self.api_key_input.setText(self.settings.value("api_key", ""))
        
        auto_match_duration = self.settings.value("auto_match_duration", True, type=bool)
        self.auto_match_duration.setChecked(auto_match_duration)
        
        # 同步视频处理标签页和设置标签页中的自动匹配时长控件
        if hasattr(self, 'material_group') and self.material_group.findChild(QCheckBox, "auto_match_duration"):
            material_auto_match = self.material_group.findChild(QCheckBox, "auto_match_duration")
            material_auto_match.setChecked(auto_match_duration)
        
        # 文档路径
        self.document_path.setText(self.settings.value("document_path", ""))
        
        # 图片路径
        if hasattr(self, 'image_path'):
            self.image_path.setText(self.settings.value("image_path", ""))
        
        # 动态字幕设置
        self.enable_dynamic_subtitle.setChecked(self.settings.value("enable_dynamic_subtitle", False, type=bool))
        animation_style_idx = self.settings.value("animation_style_idx", 0, type=int)
        if 0 <= animation_style_idx < self.animation_style_combo.count():
            self.animation_style_combo.setCurrentIndex(animation_style_idx)
            
        self.animation_intensity.setValue(self.settings.value("animation_intensity", 1.5, type=float))
        
        highlight_color_idx = self.settings.value("highlight_color_idx", 0, type=int)
        if 0 <= highlight_color_idx < self.highlight_color_combo.count():
            self.highlight_color_combo.setCurrentIndex(highlight_color_idx)
            
        match_mode_idx = self.settings.value("match_mode_idx", 0, type=int)
        if 0 <= match_mode_idx < self.match_mode_combo.count():
            self.match_mode_combo.setCurrentIndex(match_mode_idx)
        
        # 加载质量设置参数
        if hasattr(self, 'crf_value'):
            self.crf_value.setValue(self.settings.value("crf_value", 18, type=int))
            
            preset_value = self.settings.value("preset_value", "slow", type=str)
            preset_index = self.preset_combo.findData(preset_value)
            if preset_index >= 0:
                self.preset_combo.setCurrentIndex(preset_index)
                
            profile_value = self.settings.value("profile_value", "high", type=str)
            profile_index = self.profile_combo.findData(profile_value)
            if profile_index >= 0:
                self.profile_combo.setCurrentIndex(profile_index)
                
            level_value = self.settings.value("level_value", "4.1", type=str)
            level_index = self.level_combo.findData(level_value)
            if level_index >= 0:
                self.level_combo.setCurrentIndex(level_index)
                
            self.maxrate_spin.setValue(self.settings.value("maxrate_value", 8000, type=int))
            self.bufsize_spin.setValue(self.settings.value("bufsize_value", 16000, type=int))
            self.gop_spin.setValue(self.settings.value("gop_value", 30, type=int))
            
            tune_value = self.settings.value("tune_value", "film", type=str)
            tune_index = self.tune_combo.findData(tune_value)
            if tune_index >= 0:
                self.tune_combo.setCurrentIndex(tune_index)
                
            pixfmt_value = self.settings.value("pixfmt_value", "yuv420p", type=str)
            pixfmt_index = self.pixfmt_combo.findData(pixfmt_value)
            if pixfmt_index >= 0:
                self.pixfmt_combo.setCurrentIndex(pixfmt_index)
    
    def on_auto_match_duration_changed(self, state):
        """处理自动匹配时长勾选框状态变化"""
        # 同步设置标签页和视频处理标签页中的自动匹配时长控件
        is_checked = state == Qt.CheckState.Checked
        
        # 更新设置标签页中的控件（如果存在）
        if hasattr(self, 'voice_group'):
            settings_auto_match = self.voice_group.findChild(QCheckBox, "auto_match_duration")
            if settings_auto_match and settings_auto_match.isChecked() != is_checked:
                settings_auto_match.setChecked(is_checked)
        
        # 更新视频处理标签页中的控件（如果存在）
        if hasattr(self, 'material_group'):
            material_auto_match = self.material_group.findChild(QCheckBox, "auto_match_duration")
            if material_auto_match and material_auto_match.isChecked() != is_checked:
                material_auto_match.setChecked(is_checked)
        
        print(f"【自动匹配时长】状态变化: checked={is_checked}")
        
        # 更新音乐控件状态
        self.on_music_enabled_changed(Qt.CheckState.Checked if self.enable_music.isChecked() else Qt.CheckState.Unchecked)
    
    def save_settings(self):
        """保存设置"""
        self.settings.setValue("save_paths", self.save_paths_check.isChecked())
        self.settings.setValue("default_quicktime", self.default_qt_check.isChecked())
        
        # 应用QuickTime兼容模式设置
        quicktime = self.default_qt_check.isChecked()
        self.quicktime_check.setChecked(quicktime)
        
        # 保存当前设置
        self.save_current_settings()
        
        QMessageBox.information(self, "设置已保存", "设置已成功保存")
    
    def save_current_settings(self):
        """保存当前设置"""
        # 保存路径设置
        self.settings.setValue("save_paths", self.save_paths_check.isChecked())
        self.settings.setValue("default_quicktime", self.default_qt_check.isChecked())
        
        # 保存目录设置（仅在启用保存路径时）
        if self.save_paths_check.isChecked():
            self.settings.setValue("output_dir", self.output_dir.text())
        
        # 保存样式和语言选择
        self.settings.setValue("style_idx", self.style_combo.currentIndex())
        self.settings.setValue("lang_idx", self.lang_combo.currentIndex())
        
        # 保存位置设置
        self.settings.setValue("img_x", self.img_x.value())
        self.settings.setValue("img_y", self.img_y.value())
        self.settings.setValue("font_size", self.font_size.value())
        self.settings.setValue("subtitle_width", self.subtitle_width.value())
        self.settings.setValue("subtitle_text_x", self.subtitle_text_x.value())
        self.settings.setValue("subtitle_text_y", self.subtitle_text_y.value())
        self.settings.setValue("bg_width", self.bg_width.value())
        self.settings.setValue("bg_height", self.bg_height.value())
        self.settings.setValue("img_size", self.img_size.value())
        self.settings.setValue("random_subtitle_position", self.random_subtitle_position.isChecked())
        
        # 保存素材选择设置
        self.settings.setValue("enable_subtitle", self.enable_subtitle.isChecked())
        self.settings.setValue("enable_background", self.enable_background.isChecked())
        self.settings.setValue("enable_image", self.enable_image.isChecked())
        self.settings.setValue("enable_voice", self.enable_voice.isChecked())
        self.settings.setValue("enable_gif", self.enable_gif.isChecked())
        
        # 保存GIF设置
        self.settings.setValue("gif_path", self.gif_path.text())
        self.settings.setValue("gif_loop_count", self.gif_loop_count.value())
        self.settings.setValue("gif_scale", self.gif_scale.value())
        self.settings.setValue("gif_x", self.gif_x.value())
        self.settings.setValue("gif_y", self.gif_y.value())
        
        # 保存去水印设置
        self.settings.setValue("scale_factor", self.scale_factor.value())
        
        # 保存音乐设置
        self.settings.setValue("enable_music", self.enable_music.isChecked())
        self.settings.setValue("music_path", self.music_path.text())
        self.settings.setValue("music_mode_idx", self.music_mode.currentIndex())
        self.settings.setValue("music_volume", self.music_volume.value())
        
        # 保存智能配音设置
        self.settings.setValue("voice_api_idx", self.voice_api_combo.currentIndex())
        self.settings.setValue("api_key", self.api_key_input.text())
        self.settings.setValue("auto_match_duration", self.auto_match_duration.isChecked())
        
        # 保存文档和图片路径
        self.settings.setValue("document_path", self.document_path.text())
        if hasattr(self, 'image_path'):
            self.settings.setValue("image_path", self.image_path.text())
        
        # 保存动态字幕设置
        self.settings.setValue("enable_dynamic_subtitle", self.enable_dynamic_subtitle.isChecked())
        self.settings.setValue("animation_style_idx", self.animation_style_combo.currentIndex())
        self.settings.setValue("animation_intensity", self.animation_intensity.value())
        self.settings.setValue("highlight_color_idx", self.highlight_color_combo.currentIndex())
        self.settings.setValue("match_mode_idx", self.match_mode_combo.currentIndex())
        
        # 保存质量设置参数
        if hasattr(self, 'crf_value'):
            self.settings.setValue("crf_value", self.crf_value.value())
            self.settings.setValue("preset_value", self.preset_combo.currentData())
            self.settings.setValue("profile_value", self.profile_combo.currentData())
            self.settings.setValue("level_value", self.level_combo.currentData())
            self.settings.setValue("maxrate_value", self.maxrate_spin.value())
            self.settings.setValue("bufsize_value", self.bufsize_spin.value())
            self.settings.setValue("gop_value", self.gop_spin.value())
            self.settings.setValue("tune_value", self.tune_combo.currentData())
            self.settings.setValue("pixfmt_value", self.pixfmt_combo.currentData())
    
    def on_random_position_changed(self, state):
        """处理字幕位置随机化勾选框状态变化"""
        # 当勾选随机位置时，禁用手动位置输入框
        enabled = state != Qt.CheckState.Checked
        self.subtitle_text_x.setEnabled(enabled)
        self.subtitle_text_y.setEnabled(enabled)
        
        # 添加调试信息
        if state == Qt.CheckState.Checked:
            print("🎲 启用字幕随机位置，禁用手动位置设置")
        else:
            print("✏️ 禁用字幕随机位置，启用手动位置设置")
    
    def browse_material_dir(self):
        """浏览选择素材目录"""
        initial_dir = self.material_dir.text() or self.settings.value("last_material_dir", "")
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择素材目录",
            initial_dir
        )
        
        if dir_path:
            self.material_dir.setText(dir_path)
            self.settings.setValue("last_material_dir", dir_path)
    
    def select_document_file(self):
        """选择文档文件"""
        initial_dir = self.settings.value("last_document_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文档文件",
            initial_dir,
            "All Supported (*.csv *.xlsx *.xls *.md *.txt);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;Markdown Files (*.md);;Text Files (*.txt);;所有文件 (*)"
        )
        
        if file_path:
            self.document_path.setText(file_path)
            self.settings.setValue("last_document_dir", str(Path(file_path).parent))
            
            # 验证文档格式和内容
            self.validate_document(file_path)
    
    def clear_document(self):
        """清除文档选择"""
        self.document_path.clear()
    
    def validate_document(self, file_path):
        """验证文档格式和内容"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.csv':
                df = pd.read_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_ext == '.md':
                # 简单的Markdown表格解析（这里可以扩展）
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                QMessageBox.information(self, "提示", "Markdown文件已选择，请确保包含正确的表格格式")
                return
            elif file_ext == '.txt':
                # 简单的文本文件解析（逗号分隔）
                df = pd.read_csv(file_path, delimiter='\t')
            else:
                QMessageBox.warning(self, "错误", f"不支持的文件格式: {file_ext}")
                return
            
            # 检查必需列
            required_columns = ['name', 'style', 'malay_title', 'title_thai', 'zn']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                QMessageBox.warning(
                    self, "缺少列", 
                    f"文档缺少必需列: {', '.join(missing_columns)}\n\n必需列包括: {', '.join(required_columns)}"
                )
            else:
                QMessageBox.information(
                    self, "成功", 
                    f"文档验证成功！\n共找到 {len(df)} 条记录"
                )
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文档失败: {str(e)}")
    
    def on_music_enabled_changed(self, state):
        """处理音乐启用状态变化"""
        enabled = state == Qt.CheckState.Checked
        self.music_path.setEnabled(enabled)
        self.music_file_btn.setEnabled(enabled)
        self.music_folder_btn.setEnabled(enabled)
        self.music_mode.setEnabled(enabled)
        self.music_volume.setEnabled(enabled)
        print(f"【音乐设置】音乐启用状态变化: enabled={enabled}")

    def select_gif_file(self):
        """选择GIF文件"""
        initial_dir = self.settings.value("last_gif_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择GIF文件",
            initial_dir,
            "GIF文件 (*.gif);;WebP文件 (*.webp);;所有文件 (*)"
        )
        
        if file_path:
            self.gif_path.setText(file_path)
            self.settings.setValue("last_gif_dir", str(Path(file_path).parent))
    
    def select_music_file(self):
        """选择音乐文件"""
        initial_dir = self.settings.value("last_music_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音乐文件",
            initial_dir,
            "Audio Files (*.mp3 *.wav *.m4a *.aac *.flac);;All Files (*)"
        )
        
        if file_path:
            self.music_path.setText(file_path)
            self.settings.setValue("last_music_dir", str(Path(file_path).parent))
    
    def select_music_folder(self):
        """选择音乐文件夹"""
        initial_dir = self.settings.value("last_music_dir", "")
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择音乐文件夹",
            initial_dir
        )
        
        if folder_path:
            self.music_path.setText(folder_path)
            self.settings.setValue("last_music_dir", folder_path)
    
    def on_volume_changed(self, value):
        """处理音量滑块变化"""
        self.volume_label.setText(f"{value}%")
    
    def populate_voice_languages(self):
        """填充语言选项（根据API平台）"""
        self.voice_language_combo.clear()
        
        api_platform = self.voice_api_combo.currentData() if hasattr(self, 'voice_api_combo') else "edge_tts"
        
        if api_platform == "edge_tts":
            # Edge-TTS 支持的语言
            languages = [
                ("zh-CN", "中文（中国大陆）"),
                ("zh-TW", "中文（台湾）"),
                ("zh-HK", "中文（香港）"),
                ("en-US", "英语（美国）"),
                ("en-GB", "英语（英国）"),
                ("ja-JP", "日语"),
                ("ko-KR", "韩语"),
                ("es-ES", "西班牙语"),
                ("fr-FR", "法语"),
                ("de-DE", "德语"),
                ("ms-MY", "马来语"),  # 添加马来语支持
                ("th-TH", "泰语"),    # 添加泰语支持
            ]
        else:  # elevenlabs
            # ElevenLabs 支持的语言
            languages = [
                ("en", "英语"),
                ("zh", "中文"),
                ("es", "西班牙语"),
                ("fr", "法语"),
                ("de", "德语"),
                ("it", "意大利语"),
                ("pt", "葡萄牙语"),
                ("pl", "波兰语"),
                ("ms", "马来语"),     # 添加马来语支持
                ("th", "泰语"),       # 添加泰语支持
            ]
        
        for lang_code, lang_name in languages:
            self.voice_language_combo.addItem(lang_name, lang_code)
    
    def on_api_platform_changed(self):
        """处理API平台切换"""
        # 重新填充语言选项
        self.populate_voice_languages()
        # 重新填充音色选项
        self.populate_voice_types()
    
    def on_voice_language_changed(self):
        """处理语音语言切换"""
        # 重新填充音色选项
        self.populate_voice_types()
    
    def populate_voice_types(self):
        """填充音色选项（根据API平台和语言）"""
        self.voice_type_combo.clear()
        
        api_platform = self.voice_api_combo.currentData() if hasattr(self, 'voice_api_combo') else "edge_tts"
        language = self.voice_language_combo.currentData() if hasattr(self, 'voice_language_combo') else "zh-CN"
        
        if api_platform == "edge_tts":
            # Edge-TTS 的音色（根据语言筛选）
            voice_types = []
            
            if language in ["zh-CN", "zh"]:
                voice_types = [
                    ("zh-CN-XiaoxiaoNeural", "小晓(中文女声)"),
                    ("zh-CN-YunyangNeural", "云扬(中文男声)"),
                    ("zh-CN-XiaohanNeural", "小韩(中文女声)"),
                    ("zh-CN-XiaomengNeural", "小梦(中文女声)"),
                    ("zh-CN-XiaomoNeural", "小墨(中文女声)"),
                    ("zh-CN-XiaoxuanNeural", "小轩(中文女声)"),
                    ("zh-CN-XiaoruiNeural", "小蕊(中文女声)"),
                    ("zh-CN-YunjianNeural", "云健(中文男声)"),
                ]
            elif language in ["en-US", "en-GB", "en"]:
                voice_types = [
                    ("en-US-AriaNeural", "Aria(英文女声)"),
                    ("en-US-DavisNeural", "Davis(英文男声)"),
                    ("en-US-JennyNeural", "Jenny(英文女声)"),
                    ("en-US-GuyNeural", "Guy(英文男声)"),
                    ("en-GB-LibbyNeural", "Libby(英式英语女声)"),
                    ("en-GB-RyanNeural", "Ryan(英式英语男声)"),
                ]
            elif language == "ja-JP":
                voice_types = [
                    ("ja-JP-NanamiNeural", "Nanami(日语女声)"),
                    ("ja-JP-KeitaNeural", "Keita(日语男声)"),
                ]
            elif language == "ko-KR":
                voice_types = [
                    ("ko-KR-SunHiNeural", "SunHi(韩语女声)"),
                    ("ko-KR-InJoonNeural", "InJoon(韩语男声)"),
                ]
            elif language == "ms-MY":  # 马来语
                voice_types = [
                    ("ms-MY-YasminNeural", "Yasmin(马来语女声)"),
                    ("ms-MY-OsmanNeural", "Osman(马来语男声)"),
                ]
            elif language == "th-TH":  # 泰语
                voice_types = [
                    ("th-TH-PremwadeeNeural", "Premwadee(泰语女声)"),
                    ("th-TH-NiwatNeural", "Niwat(泰语男声)"),
                ]
            else:
                # 其他语言的默认音色
                voice_types = [
                    (f"{language}-Standard-A", f"标准音色 A"),
                    (f"{language}-Standard-B", f"标准音色 B"),
                ]
        else:  # elevenlabs
            # ElevenLabs 的音色（通用）
            voice_types = [
                ("21m00Tcm4TlvDq8ikWAM", "Rachel(英语女声)"),
                ("AZnzlk1XvdvUeBnXmlld", "Domi(英语女声)"),
                ("EXAVITQu4vr4xnSDxMaL", "Bella(英语女声)"),
                ("ErXwobaYiN019PkySvjV", "Antoni(英语男声)"),
                ("MF3mGyEYCl7XYWbV9V6O", "Elli(英语女声)"),
                ("TxGEqnHWrfWFTfGW9XjX", "Josh(英语男声)"),
            ]
        
        for voice_id, voice_name in voice_types:
            self.voice_type_combo.addItem(voice_name, voice_id)
    
    def test_api_connection(self):
        """测试API连接"""
        api_platform = self.voice_api_combo.currentData()
        api_key = self.api_key_input.text().strip()
        
        if not api_key and api_platform == "elevenlabs":
            QMessageBox.warning(self, "警告", "ElevenLabs 需要 API Key")
            return
        
        try:
            if api_platform == "edge_tts":
                # Edge-TTS 不需要 API Key，可以直接返回成功
                QMessageBox.information(self, "成功", "Edge-TTS 不需要 API Key，可以直接使用")
            elif api_platform == "elevenlabs":
                # 这里可以添加真实的 ElevenLabs API 测试
                QMessageBox.information(self, "成功", "API 连接测试成功（模拟）")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"API 连接测试失败: {str(e)}")

    def close_event(self, event):
        """处理窗口关闭事件"""
        # 如果有正在运行的线程，提示用户确认
        if hasattr(self, 'processing_thread') and self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self, '确认退出', 
                '有正在进行的处理任务，确定要退出吗？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 尝试结束线程
                if self.processing_thread.isRunning():
                    self.processing_thread.terminate()
                    self.processing_thread.wait(3000)  # 等待最多3秒
                    
                # 保存设置
                self.save_current_settings()
                if event is not None:
                    event.accept()
            else:
                if event is not None:
                    event.ignore()
        else:
            # 保存设置
            self.save_current_settings()
            if event is not None:
                event.accept()


if __name__ == "__main__":
    # 启用高DPI缩放
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 设置全局字体大小
    font = app.font()
    if sys.platform == 'win32':
        # Windows系统下增大字体
        font.setPointSize(10)  # 默认字体大小
    app.setFont(font)
    
    window = VideoProcessorApp()
    window.show()
    sys.exit(app.exec_())