#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态字幕模块
专门处理ASS格式动画字幕的生成和管理
"""

import os
import re
import json
import time
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import subprocess
from log_manager import log_with_capture


class DynamicSubtitleSystem:
    """
    动态字幕系统核心类
    """
    
    def __init__(self):
        self.supported_languages = {
            'chinese': {'column': 'cn_prompt', 'voice': 'zh-CN-XiaoxiaoNeural'},
            'malay': {'column': 'malay_prompt', 'voice': 'ms-MY-OsmanNeural'},
            'thai': {'column': 'thai_prompt', 'voice': 'th-TH-NiwatNeural'}
        }
        
        # 内置3种CapCut风格字幕动画
        self.animation_styles = {
            'highlight': {
                'name': '高亮放大',
                'description': '当前朗读单词放大并变色',
                'scale_factor': 1.3,
                'highlight_color': '#FFD700',
                'transition_duration': 0.2
            },
            'bounce': {
                'name': '弹跳效果',
                'description': '当前单词弹跳动画',
                'scale_factor': 1.5,
                'highlight_color': '#FF6B6B',
                'transition_duration': 0.3,
                'bounce_height': 10
            },
            'glow': {
                'name': '发光效果',
                'description': '当前单词发光并渐变',
                'scale_factor': 1.2,
                'highlight_color': '#4ECDC4',
                'transition_duration': 0.25,
                'glow_radius': 5
            },
            'typewriter': {
                'name': '打字机效果',
                'description': '逐字显示效果',
                'typing_speed': 0.1,
                'highlight_color': '#FFD700',
                'transition_duration': 0.1
            },
            'slide': {
                'name': '滑入效果',
                'description': '从一侧滑入',
                'slide_direction': 'left',
                'slide_speed': 0.3,
                'highlight_color': '#9B59B6',
                'transition_duration': 0.3
            }
        }
        
        # 添加动画属性
        self.animation_style = "高亮放大"
        self.animation_intensity = 1.5
        self.highlight_color = "#FFD700"
    
    @log_with_capture
    def extract_text_from_document(self, document_path: str, language: str, row_index: Optional[int] = None) -> str:
        """
        从文档中提取指定语言的文本
        
        Args:
            document_path: 文档路径
            language: 语言类型 (chinese/malay/thai)
            row_index: 指定行索引，如果为None则随机选择
            
        Returns:
            提取的文本内容
        """
        try:
            if not os.path.exists(document_path):
                raise FileNotFoundError(f"文档文件不存在: {document_path}")
            
            # 读取Excel文件
            df = pd.read_excel(document_path)
            
            # 获取对应语言的列名
            if language not in self.supported_languages:
                raise ValueError(f"不支持的语言: {language}")
            
            column_name = self.supported_languages[language]['column']
            
            if column_name not in df.columns:
                raise ValueError(f"文档中未找到列: {column_name}")
            
            # 过滤有效数据
            valid_data = df[df[column_name].notna() & (df[column_name] != "")]
            
            if valid_data.empty:
                raise ValueError(f"列 {column_name} 中没有有效数据")
            
            # 选择文本
            if row_index is not None and 0 <= row_index < len(valid_data):
                text = str(valid_data.iloc[row_index][column_name])
            else:
                text = str(valid_data.sample(1).iloc[0][column_name])
            
            print(f"✅ 成功提取{language}文本: {text[:50]}...")
            return text.strip()
            
        except Exception as e:
            print(f"❌ 提取文本失败: {e}")
            return self._get_default_text(language)
    
    def _get_default_text(self, language: str) -> str:
        """
        获取默认文本
        """
        defaults = {
            'chinese': '欢迎观看我们的视频内容',
            'malay': 'Selamat datang ke kandungan video kami',
            'thai': 'ยินดีต้อนรับสู่เนื้อหาวิดีโอของเรา'
        }
        return defaults.get(language, 'Welcome to our video content')
    
    @log_with_capture
    def analyze_text_timing(self, text: str, audio_duration: float, language: str) -> List[Dict]:
        """
        分析文本中每个单词的时间戳
        
        Args:
            text: 文本内容
            audio_duration: 音频总时长（秒）
            language: 语言类型
            
        Returns:
            单词时间戳列表 [{'word': str, 'start': float, 'end': float}]
        """
        try:
            # 根据语言类型分词
            if language == 'chinese':
                words = list(text.replace(' ', '').replace('\n', ''))
            else:
                # 马来语和泰语按空格分词
                words = text.replace('\n', ' ').split()
            
            if not words:
                return []
            
            # 计算每个单词的平均时长
            word_duration = audio_duration / len(words)
            
            # 生成时间戳
            word_timings = []
            current_time = 0.0
            
            for word in words:
                if word.strip():  # 跳过空字符
                    word_timings.append({
                        'word': word.strip(),
                        'start': current_time,
                        'end': current_time + word_duration
                    })
                    current_time += word_duration
            
            print(f"✅ 分析完成，共{len(word_timings)}个单词")
            return word_timings
            
        except Exception as e:
            print(f"❌ 文本时间分析失败: {e}")
            return []
    
    @log_with_capture
    def generate_subtitle_file(self, word_timings: List[Dict], output_path: str, 
                             animation_style: str = 'highlight') -> str:
        """
        生成字幕文件（ASS格式）
        
        Args:
            word_timings: 单词时间戳列表
            output_path: 输出路径
            animation_style: 动画样式
            
        Returns:
            字幕文件路径
        """
        try:
            style_config = self.animation_styles.get(animation_style, self.animation_styles['highlight'])
            
            # ASS字幕文件头部
            ass_content = """[Script Info]
Title: Dynamic Subtitle
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,50,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
Style: Highlight,Arial,65,&H00FFD700,&H000000FF,&H00000000,&H80000000,1,0,0,0,130,130,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            
            # 生成字幕事件
            for i, timing in enumerate(word_timings):
                start_time = self._seconds_to_ass_time(timing['start'])
                end_time = self._seconds_to_ass_time(timing['end'])
                
                # 构建完整文本，高亮当前单词
                full_text = ""
                for j, word_info in enumerate(word_timings):
                    if j == i:
                        # 当前单词使用高亮样式
                        full_text += f"{{\\c&H{style_config['highlight_color'][1:]}\\fscx{int(style_config['scale_factor']*100)}\\fscy{int(style_config['scale_factor']*100)}}}{word_info['word']}{{\\r}}"
                    else:
                        full_text += word_info['word']
                    
                    if j < len(word_timings) - 1:
                        full_text += " "
                
                ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{full_text}\n"
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            print(f"✅ 字幕文件生成成功: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 字幕文件生成失败: {e}")
            return ""
    
    def _seconds_to_ass_time(self, seconds: float) -> str:
        """
        将秒数转换为ASS时间格式 (H:MM:SS.CC)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    @log_with_capture
    def create_dynamic_subtitle_video(self, video_path: str, subtitle_file: str, 
                                     output_path: str, subtitle_config: Dict) -> bool:
        """
        将动态字幕应用到视频
        
        Args:
            video_path: 输入视频路径
            subtitle_file: 字幕文件路径
            output_path: 输出视频路径
            subtitle_config: 字幕配置
            
        Returns:
            是否成功
        """
        try:
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"ass={subtitle_file}",
                '-c:a', 'copy',
                output_path
            ]
            
            print(f"🎬 开始应用动态字幕...")
            print(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ 动态字幕应用成功")
                return True
            else:
                print(f"❌ 动态字幕应用失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 动态字幕处理异常: {e}")
            return False
    
    @log_with_capture
    def create_dynamic_subtitle(self, text, width=800, height=500, font_size=None, output_path=None, tts_audio_path=None,
                               font_color="#FFFFFF", outline_size=2, outline_color="#000000", animation_duration=0.3, opacity=100):
        """
        创建动态字幕文件（ASS格式）
        
        Args:
            text: 字幕文本
            width: 视频宽度
            height: 视频高度
            font_size: 字体大小
            output_path: 输出路径
            tts_audio_path: TTS音频文件路径，用于同步分析
            font_color: 字体颜色 (十六进制格式，如 "#FFFFFF")
            outline_size: 描边大小
            outline_color: 描边颜色 (十六进制格式，如 "#000000")
            
        Returns:
            生成的字幕文件路径
        """
        try:
            # 如果提供了TTS音频，进行同步分析
            word_timings = None
            audio_duration = 5.0  # 默认时长
            
            if tts_audio_path and os.path.exists(tts_audio_path):
                word_timings = self._analyze_audio_timing(tts_audio_path, text)
                # 获取音频时长
                try:
                    import librosa
                    y, sr = librosa.load(tts_audio_path)
                    audio_duration = librosa.get_duration(y=y, sr=sr)
                except:
                    # 估算时长
                    audio_duration = len(text) / 3.0
            else:
                # 估算时长
                audio_duration = len(text) / 3.0
            
            # 确定输出路径
            if not output_path:
                output_path = "dynamic_subtitle.ass"
            elif not output_path.endswith('.ass'):
                output_path = output_path.replace('.png', '.ass')
            
            # 生成ASS字幕文件
            ass_content = self._generate_ass_subtitle(text, audio_duration, width, height, font_size, font_color, outline_size, outline_color, animation_duration, opacity)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            print(f"✅ 动态字幕文件生成成功: {output_path}")
            return output_path
                
        except Exception as e:
            print(f"创建动态字幕失败: {e}")
            return ""
    
    def _generate_ass_subtitle(self, text, duration, width, height, font_size, font_color="#FFFFFF", outline_size=2, outline_color="#000000", animation_duration=0.3, opacity=100):
        """
        生成ASS格式的动态字幕内容
        
        Args:
            text: 字幕文本
            duration: 音频时长
            width: 视频宽度
            height: 视频高度
            font_size: 字体大小
            font_color: 字体颜色 (十六进制格式，如 "#FFFFFF")
            outline_size: 描边大小
            outline_color: 描边颜色 (十六进制格式，如 "#000000")
            animation_duration: 动画持续时间
            opacity: 透明度 (0-100)
            
        Returns:
            ASS字幕文件内容
        """
        # 将十六进制颜色转换为ASS格式 (&HBBGGRR格式)
        def hex_to_ass_color(hex_color):
            if hex_color.startswith('#'):
                hex_color = hex_color[1:]
            if len(hex_color) == 6:
                # 转换为 &HBBGGRR 格式
                return f"&H{hex_color[4:6]}{hex_color[2:4]}{hex_color[0:2]}"
            return "&HFFFFFF"  # 默认白色
            
        primary_color = hex_to_ass_color(font_color)
        outline_color_ass = hex_to_ass_color(outline_color)
        
        # 计算透明度值 (&HAA格式，00为不透明，FF为完全透明)
        alpha_value = f"{255 - int(255 * opacity / 100):02X}"
        primary_color_with_alpha = f"&H{alpha_value}{primary_color[2:]}"
        outline_color_with_alpha = f"&H{alpha_value}{outline_color_ass[2:]}"
        
        # ASS文件头部
        ass_header = f"""[Script Info]
Title: Dynamic Subtitle
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{primary_color_with_alpha},&H000000FF,{outline_color_with_alpha},&H80000000,0,0,0,0,100,100,0,0,1,{outline_size},0,2,10,10,10,1
Style: Highlight,Arial,{int(font_size * 1.2)},{primary_color_with_alpha},&H000000FF,{outline_color_with_alpha},&H80000000,1,0,0,0,110,110,0,0,1,{outline_size+1},0,2,10,10,10,1
Style: Bounce,Arial,{font_size},{primary_color_with_alpha},&H000000FF,{outline_color_with_alpha},&H80000000,0,0,0,0,100,100,0,0,1,{outline_size},0,2,10,10,10,1
Style: Glow,Arial,{font_size},{primary_color_with_alpha},&H000000FF,{outline_color_with_alpha},&H80000000,0,0,0,0,100,100,0,0,1,{outline_size+1},0,2,10,10,10,1
Style: Typewriter,Arial,{font_size},{primary_color_with_alpha},&H000000FF,{outline_color_with_alpha},&H80000000,0,0,0,0,100,100,0,0,1,{outline_size},0,2,10,10,10,1
Style: Slide,Arial,{font_size},{primary_color_with_alpha},&H000000FF,{outline_color_with_alpha},&H80000000,0,0,0,0,100,100,0,0,1,{outline_size},0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        # 分析文本并生成事件
        words = self._split_text_to_words(text)
        if not words:
            words = [text]
        
        word_duration = duration / len(words)
        events = []
        
        # 获取动画样式
        animation_style = getattr(self, 'animation_style', '高亮放大')
        
        for i, word in enumerate(words):
            start_time = i * word_duration
            end_time = (i + 1) * word_duration
            
            start_ass = self._seconds_to_ass_time(start_time)
            end_ass = self._seconds_to_ass_time(end_time)
            
            # 根据动画样式选择样式和效果
            if animation_style == "高亮放大":
                style = "Highlight"
                effect = f"{{\\t(0,{int(animation_duration*500)},\\fscx120\\fscy120\\c{hex_to_ass_color(getattr(self, 'highlight_color', '#FFD700'))}&)\\t({int(animation_duration*500)},{int(animation_duration*1000)},\\fscx100\\fscy100\\c{primary_color_with_alpha}&)}}"
            elif animation_style == "弹跳效果":
                style = "Bounce"
                bounce_height = int(10 * getattr(self, 'animation_intensity', 1.5))
                effect = f"{{\\move({width//2},{height-100},{width//2},{height-100-bounce_height},0,{int(animation_duration*500)})\\move({width//2},{height-100-bounce_height},{width//2},{height-100},{int(animation_duration*500)},{int(animation_duration*1000)})}}"
            elif animation_style == "发光效果":
                style = "Glow"
                highlight_color = hex_to_ass_color(getattr(self, 'highlight_color', '#FFD700'))
                effect = f"{{\\t(0,{int(animation_duration*500)},\\3c{highlight_color}&\\3a&H00&)\\t({int(animation_duration*500)},{int(animation_duration*1000)},\\3c{outline_color_with_alpha}&\\3a&H80&)}}"
            elif animation_style == "打字机效果":
                style = "Typewriter"
                # 打字机效果通过逐字显示实现
                effect = f"{{\\alpha&HFF&\\t(0,{int(animation_duration*1000)},\\alpha&H00&)}}"
            elif animation_style == "滑入效果":
                style = "Slide"
                # 从左侧滑入效果
                effect = f"{{\\pos({-100},{height-100})\\t(0,{int(animation_duration*1000)},\\pos({width//2},{height-100}))}}"
            else:
                style = "Default"
                effect = ""
            
            # 创建事件行
            event_line = f"Dialogue: 0,{start_ass},{end_ass},{style},,0,0,0,,{effect}{word}"
            events.append(event_line)
        
        # 添加完整文本显示（作为背景）
        full_start = self._seconds_to_ass_time(0)
        full_end = self._seconds_to_ass_time(duration)
        full_text_event = f"Dialogue: 0,{full_start},{full_end},Default,,0,0,0,,{{\\alpha&H80&}}{text}"
        events.insert(0, full_text_event)
        
        return ass_header + "\n".join(events)
    
    def _split_text_to_words(self, text: str) -> List[str]:
        """
        将文本分割为单词或字符
        """
        import re
        
        # 检测是否包含中文字符
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        has_chinese = bool(chinese_pattern.search(text))
        
        if has_chinese:
            # 中文按字符分割，保留标点符号
            words = []
            current_word = ""
            
            for char in text:
                if char.isspace():
                    if current_word:
                        words.append(current_word)
                        current_word = ""
                elif char in '，。！？；：、':
                    if current_word:
                        words.append(current_word)
                        current_word = ""
                    words.append(char)
                else:
                    current_word += char
            
            # 添加最后一个单词
            if current_word:
                words.append(current_word)
        else:
            # 英文按空格分割
            words = text.split()
        
        return words
    
    def _analyze_audio_timing(self, audio_path: str, text: str) -> List[Dict]:
        """
        分析音频文件，获取精确的单词时间戳
        
        Args:
            audio_path: 音频文件路径
            text: 对应文本
            
        Returns:
            单词时间戳列表
        """
        try:
            import librosa
            import numpy as np
            
            # 加载音频文件
            y, sr = librosa.load(audio_path)
            
            # 检测语音活动区域
            intervals = librosa.effects.split(y, top_db=20)
            
            # 分割文本为单词/字符
            words = self._split_text_to_words(text)
            
            timing_info = []
            
            if len(intervals) > 0 and len(words) > 0:
                # 将语音区间分配给单词
                total_speech_duration = sum([(end - start) / sr for start, end in intervals])
                
                # 计算每个单词的时间分配
                word_durations = []
                total_chars = sum(len(word) for word in words)
                
                for word in words:
                    # 根据字符长度分配时间
                    char_ratio = len(word) / total_chars if total_chars > 0 else 1 / len(words)
                    duration = total_speech_duration * char_ratio
                    word_durations.append(max(duration, 0.1))  # 最小0.1秒
                
                # 分配时间戳
                current_time = intervals[0][0] / sr if len(intervals) > 0 else 0
                
                for i, (word, duration) in enumerate(zip(words, word_durations)):
                    timing_info.append({
                        'word': word,
                        'start': current_time,
                        'end': current_time + duration
                    })
                    current_time += duration
            else:
                # 回退到简单时间分割
                duration = librosa.get_duration(y=y, sr=sr)
                return self.analyze_text_timing(text, duration, 'chinese')
                    
        except ImportError:
            print("警告: librosa未安装，使用估算时间")
            # 估算音频时长（假设每秒3个字符）
            estimated_duration = len(text) / 3.0
            return self.analyze_text_timing(text, estimated_duration, 'chinese')
        except Exception as e:
            print(f"音频时间分析失败: {e}")
            # 回退到简单时间分割
            estimated_duration = len(text) / 3.0
            return self.analyze_text_timing(text, estimated_duration, 'chinese')
        
        return timing_info
    
    def _load_font(self, font_size: int):
        """
        加载字体
        """
        try:
            # 尝试加载系统字体
            return ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                # 尝试加载中文字体
                return ImageFont.truetype("simhei.ttf", font_size)
            except:
                # 使用默认字体
                return ImageFont.load_default()
    
    def _apply_highlight_effect(self, draw, text, x, y, font, word_timings=None):
        """
        应用高亮放大效果 - CapCut风格
        当前朗读的单词会放大并变色
        """
        if word_timings:
            # 根据时间戳分别处理每个单词
            words = text.split()
            current_x = x
            
            for i, word in enumerate(words):
                # 检查当前单词是否正在朗读（这里简化为第一个单词高亮）
                is_current = (i == 0)  # 简化逻辑，实际应根据时间戳判断
                
                if is_current:
                    # 当前朗读单词：放大并高亮
                    highlight_font_size = int(font.size * getattr(self, 'animation_intensity', 1.5))
                    try:
                        highlight_font = ImageFont.truetype(font.path, highlight_font_size)
                    except:
                        highlight_font = font
                    
                    # 绘制发光边框
                    for offset in range(3):
                        draw.text((current_x-offset, y-offset), word, font=highlight_font, 
                                fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), 100))
                        draw.text((current_x+offset, y+offset), word, font=highlight_font, 
                                fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), 100))
                    
                    # 绘制主文本
                    draw.text((current_x, y), word, font=highlight_font, 
                            fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), 255))
                    
                    # 计算下一个单词的位置
                    bbox = draw.textbbox((0, 0), word + " ", font=highlight_font)
                    current_x += bbox[2] - bbox[0]
                else:
                    # 普通单词：正常显示
                    draw.text((current_x, y), word, font=font, fill=(255, 255, 255, 200))
                    
                    # 计算下一个单词的位置
                    bbox = draw.textbbox((0, 0), word + " ", font=font)
                    current_x += bbox[2] - bbox[0]
        else:
            # 没有时间戳，整体高亮
            draw.text((x, y), text, font=font, fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), 255))
     
    def _apply_bounce_effect(self, draw, text, x, y, font, word_timings=None):
        """
        应用弹跳效果 - CapCut风格
        当前朗读的单词会有弹跳动画
        """
        if word_timings:
            words = text.split()
            current_x = x
            
            for i, word in enumerate(words):
                is_current = (i == 0)  # 简化逻辑
                
                if is_current:
                    # 当前单词：弹跳效果（向上偏移）
                    bounce_offset = int(10 * getattr(self, 'animation_intensity', 1.5))
                    bounce_y = y - bounce_offset
                    
                    # 绘制阴影
                    draw.text((current_x+2, y+2), word, font=font, fill=(0, 0, 0, 100))
                    
                    # 绘制弹跳的单词
                    draw.text((current_x, bounce_y), word, font=font, 
                            fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), 255))
                    
                    bbox = draw.textbbox((0, 0), word + " ", font=font)
                    current_x += bbox[2] - bbox[0]
                else:
                    # 普通单词
                    draw.text((current_x, y), word, font=font, fill=(255, 255, 255, 200))
                    
                    bbox = draw.textbbox((0, 0), word + " ", font=font)
                    current_x += bbox[2] - bbox[0]
        else:
            # 整体弹跳
            bounce_offset = int(5 * getattr(self, 'animation_intensity', 1.5))
            draw.text((x, y-bounce_offset), text, font=font, fill=(255, 107, 107, 255))
     
    def _apply_glow_effect(self, draw, text, x, y, font, word_timings=None):
        """
        应用发光效果 - CapCut风格
        当前朗读的单词会有发光光晕
        """
        if word_timings:
            words = text.split()
            current_x = x
            
            for i, word in enumerate(words):
                is_current = (i == 0)  # 简化逻辑
                
                if is_current:
                    # 当前单词：发光效果
                    glow_radius = int(5 * getattr(self, 'animation_intensity', 1.5))
                    
                    # 绘制多层发光效果
                    for radius in range(glow_radius, 0, -1):
                        alpha = int(50 * (glow_radius - radius + 1) / glow_radius)
                        for dx in range(-radius, radius+1):
                            for dy in range(-radius, radius+1):
                                if dx*dx + dy*dy <= radius*radius:
                                    draw.text((current_x+dx, y+dy), word, font=font, 
                                            fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), alpha))
                    
                    # 绘制主文本
                    draw.text((current_x, y), word, font=font, 
                            fill=self._hex_to_rgba(getattr(self, 'highlight_color', '#FFD700'), 255))
                    
                    bbox = draw.textbbox((0, 0), word + " ", font=font)
                    current_x += bbox[2] - bbox[0]
                else:
                    # 普通单词
                    draw.text((current_x, y), word, font=font, fill=(255, 255, 255, 200))
                    
                    bbox = draw.textbbox((0, 0), word + " ", font=font)
                    current_x += bbox[2] - bbox[0]
        else:
            # 整体发光
            for offset in range(3):
                draw.text((x+offset, y+offset), text, font=font, fill=(78, 205, 196, 128))
            draw.text((x, y), text, font=font, fill=(78, 205, 196, 255))
     
    def _hex_to_rgba(self, hex_color: str, alpha: int = 255) -> tuple:
        """
        将十六进制颜色转换为RGBA元组
        
        Args:
            hex_color: 十六进制颜色值，如 '#FFD700'
            alpha: 透明度值 (0-255)
            
        Returns:
            RGBA颜色元组
        """
        try:
            # 移除 # 符号
            hex_color = hex_color.lstrip('#')
            
            # 转换为RGB
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (r, g, b, alpha)
            else:
                # 默认返回金色
                return (255, 215, 0, alpha)
        except:
            # 出错时返回默认颜色
            return (255, 215, 0, alpha)
    
    def get_animation_styles(self) -> Dict:
        """
        获取可用的动画样式
        """
        return self.animation_styles
    
    def get_supported_languages(self) -> Dict:
        """
        获取支持的语言
        """
        return self.supported_languages


# 动态字幕处理器类
class DynamicSubtitleProcessor:
    """
    动态字幕处理器
    用于与video_core.py集成
    """
    
    def __init__(self, animation_style="高亮放大", animation_intensity=1.5, highlight_color="#FFD700", match_mode="指定样式", position_x=50, position_y=50,
                 font_size=70, font_color="#FFFFFF", outline_size=2, outline_color="#000000", animation_duration=0.3, opacity=100):
        self.system = DynamicSubtitleSystem()
        self.animation_style = animation_style
        self.animation_intensity = animation_intensity
        self.highlight_color = highlight_color
        self.match_mode = match_mode
        self.position_x = position_x  # X坐标位置（百分比，0-100）
        self.position_y = position_y  # Y坐标位置（百分比，0-100）
        self.style_cycle_index = 0  # 用于循环样式模式
        self.available_styles = ["高亮放大", "弹跳效果", "发光效果", "打字机效果", "滑入效果"]
        # 新增的字体和样式参数
        self.font_size = font_size
        self.font_color = font_color
        self.outline_size = outline_size
        self.outline_color = outline_color
        # 新增的动画参数
        self.animation_duration = animation_duration
        self.opacity = opacity
    
    def _get_animation_style_for_word(self, word_index):
        """
        根据匹配模式获取单词的动画样式
        """
        if self.match_mode == "随机样式":
            import random
            return random.choice(self.available_styles)
        elif self.match_mode == "循环样式":
            style = self.available_styles[self.style_cycle_index % len(self.available_styles)]
            self.style_cycle_index += 1
            return style
        else:  # 指定样式
            return self.animation_style
    
    def _split_text_to_words(self, text):
        """
        将文本分割为单词列表
        """
        import re
        # 支持中文、英文、数字的分词
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+|[0-9]+', text)
        return words
    
    def generate_subtitle_with_timing(self, text, total_duration):
        """
        生成带时间轴的字幕
        """
        words = self._split_text_to_words(text)
        if not words:
            return []
            
        word_duration = total_duration / len(words)
        subtitle_events = []
        
        for i, word in enumerate(words):
            start_time = i * word_duration
            end_time = (i + 1) * word_duration
            
            # 根据匹配模式获取动画样式
            current_style = self._get_animation_style_for_word(i)
            
            # 创建字幕事件
            event = {
                'start': start_time,
                'end': end_time,
                'text': word,
                'word_index': i,
                'style': current_style
            }
            subtitle_events.append(event)
            
        return subtitle_events
    
    def create_dynamic_subtitle(self, text, width=800, height=500, font_size=None, output_path=None, tts_audio_path=None):
        """
        创建动态字幕
        """
        # 使用传入的font_size参数，如果没有传入则使用实例变量
        if font_size is None:
            font_size = self.font_size
            
        # 设置动画参数
        self.system.animation_style = self.animation_style
        self.system.animation_intensity = self.animation_intensity
        self.system.highlight_color = self.highlight_color
        
        return self.system.create_dynamic_subtitle(
            text=text,
            width=width,
            height=height,
            font_size=font_size,
            output_path=output_path,
            tts_audio_path=tts_audio_path,
            font_color=self.font_color,
            outline_size=self.outline_size,
            outline_color=self.outline_color,
            animation_duration=self.animation_duration,
            opacity=self.opacity
        )


class AnimatedSubtitleProcessor:
    """动态字幕处理器"""
    
    def __init__(self):
        """初始化动态字幕处理器"""
        self.system = DynamicSubtitleSystem()
    
    def get_animated_subtitle_text(self, subtitle_df, language, video_index=0):
        """
        从配置数据中获取动态字幕文本
        
        参数:
            subtitle_df: 字幕配置DataFrame
            language: 语言选择 (chinese, malay, thai)
            video_index: 视频索引（从0开始）
            
        返回:
            对应视频的动态字幕文本
        """
        if subtitle_df is None or subtitle_df.empty:
            print("字幕配置为空")
            return ""
        
        # 定义语言到列名的映射（动态字幕使用特定的列）
        lang_to_column = {
            "chinese": "cn_prompt",
            "malay": "malay_prompt", 
            "thai": "thai_prompt"
        }
        
        # 获取对应的列名
        column_name = lang_to_column.get(language, "cn_prompt")
        print(f"获取动态字幕文本: 语言={language}, 列名={column_name}, 视频索引={video_index}")
        
        # 检查列是否存在
        if column_name not in subtitle_df.columns:
            print(f"列 '{column_name}' 不存在于字幕配置中")
            print(f"可用列名: {list(subtitle_df.columns)}")
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
        subtitle_text = str(valid_texts.iloc[video_index][column_name])
        print(f"获取到动态字幕文本: {subtitle_text}")
        
        return subtitle_text
    
    def create_animated_subtitle(self, text, width=1080, height=1920, output_path=None,
                                animation_style="高亮放大", animation_intensity=1.5, 
                                highlight_color="#FFD700", match_mode="指定样式",
                                font_size=70, font_color="#FFFFFF", outline_size=2, 
                                outline_color="#000000", position_x=0, position_y=1200,
                                animation_duration=0.3, opacity=100):
        """
        创建动态字幕
        
        参数:
            text: 字幕文本
            width: 视频宽度
            height: 视频高度
            output_path: 输出路径
            animation_style: 动画样式
            animation_intensity: 动画强度
            highlight_color: 高亮颜色
            match_mode: 匹配模式
            font_size: 字体大小
            font_color: 字体颜色
            outline_size: 描边大小
            outline_color: 描边颜色
            position_x: 字幕X坐标
            position_y: 字幕Y坐标
            animation_duration: 动画持续时间
            opacity: 透明度
            
        返回:
            字幕文件路径
        """
        # 创建动态字幕处理器
        processor = DynamicSubtitleProcessor(
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
        
        # 生成动态字幕
        return processor.create_dynamic_subtitle(
            text=text,
            width=width,
            height=height,
            font_size=font_size,
            output_path=output_path
        )


# 兼容旧接口的函数
def get_animated_subtitle_text(subtitle_df, language, video_index=0):
    """兼容旧接口的动态字幕文本获取函数"""
    processor = AnimatedSubtitleProcessor()
    return processor.get_animated_subtitle_text(subtitle_df, language, video_index)


def create_animated_subtitle(text, width=1080, height=1920, output_path=None,
                            animation_style="高亮放大", animation_intensity=1.5, 
                            highlight_color="#FFD700", match_mode="指定样式",
                            font_size=70, font_color="#FFFFFF", outline_size=2, 
                            outline_color="#000000", position_x=0, position_y=1200,
                            animation_duration=0.3, opacity=100):
    """兼容旧接口的动态字幕创建函数"""
    processor = AnimatedSubtitleProcessor()
    return processor.create_animated_subtitle(
        text, width, height, output_path,
        animation_style, animation_intensity, highlight_color, match_mode,
        font_size, font_color, outline_size, outline_color, position_x, position_y,
        animation_duration, opacity
    )