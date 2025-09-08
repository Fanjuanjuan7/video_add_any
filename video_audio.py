#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频音频处理模块
负责处理视频中的音频，包括背景音乐、TTS等
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
import asyncio
import platform  # 添加platform模块导入

# 导入工具函数
from utils import get_video_info, get_audio_duration, run_ffmpeg_command, get_data_path, ensure_dir, load_style_config, find_font_file, find_matching_image, generate_tts_audio, load_subtitle_config

# 导入日志管理器
from log_manager import init_logging, log_with_capture

# 初始化日志系统
log_manager = init_logging()


def trim_music_to_video_duration(music_path, video_duration, output_path):
    """
    根据视频时长裁剪音乐文件
    
    参数:
        music_path: 音乐文件路径
        video_duration: 视频时长（秒）
        output_path: 裁剪后音乐的输出路径
        
    返回:
        裁剪后的音乐文件路径（字符串格式），失败返回None
    """
    try:
        # 获取音乐文件时长
        music_duration = get_audio_duration(music_path)
        if music_duration is None:
            print(f"无法获取音乐文件时长: {music_path}")
            return None
            
        print(f"音乐原始时长: {music_duration}秒，视频时长: {video_duration}秒")
        
        # 如果音乐时长小于等于视频时长，直接返回原文件（确保返回字符串）
        if music_duration <= video_duration:
            print("音乐时长不超过视频时长，无需裁剪")
            return str(music_path)  # 确保返回字符串格式
            
        # 裁剪音乐到视频时长
        print(f"裁剪音乐从 {music_duration}秒 到 {video_duration}秒")
        
        # 根据操作系统设置不同的音频参数
        if platform.system() == "Windows":
            trim_cmd = [
                "ffmpeg", "-y",  # 覆盖输出文件
                "-i", str(music_path),
                "-t", str(video_duration),  # 设置输出时长
                "-ar", "44100",  # 设置采样率
                "-ac", "2",      # 设置声道数
                "-c:a", "aac",   # 使用AAC编码
                str(output_path)
            ]
        else:
            trim_cmd = [
                "ffmpeg", "-y",  # 覆盖输出文件
                "-i", str(music_path),
                "-t", str(video_duration),  # 设置输出时长
                "-c", "copy",  # 复制编码，避免重新编码
                str(output_path)
            ]
        
        if run_ffmpeg_command(trim_cmd, quiet=True):
            print(f"音乐裁剪成功: {output_path}")
            return str(output_path)  # 确保返回字符串格式
        else:
            print("音乐裁剪失败")
            return None
            
    except Exception as e:
        print(f"音乐裁剪过程中发生错误: {e}")
        return None


@log_with_capture
def add_tts_audio_to_video(video_path, audio_path, output_path, audio_volume=100):
    """
    将TTS音频添加到视频中
    
    参数:
        video_path: 视频文件路径
        audio_path: 音频文件路径
        output_path: 输出文件路径
        audio_volume: 音频音量（百分比，默认100）
        
    返回:
        bool: 是否成功添加音频
    """
    try:
        # 构建FFmpeg命令，将音频混合到视频中
        # 使用volume滤镜调整音频音量
        # 为Windows系统优化音频处理参数
        import platform
        if platform.system() == 'Windows':
            # Windows下使用更稳定的音频滤镜参数
            audio_volume_filter = f"volume={audio_volume/100:.2f}:precision=fixed"
        else:
            # macOS和其他系统使用默认参数
            audio_volume_filter = f"volume={audio_volume/100:.2f}"
        
        # 首先检查视频是否有音频流
        import subprocess
        probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', str(video_path)]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        
        has_audio = False
        if probe_result.returncode == 0:
            import json
            probe_data = json.loads(probe_result.stdout)
            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    has_audio = True
                    break
        
        if has_audio:
            # 视频有音频流，混合音频
            # 使用amix滤镜混合背景音乐和TTS音频，确保两者都能听到
            # 根据操作系统设置不同的amix参数
            if platform.system() == "Windows":
                amix_params = "inputs=2:duration=longest:dropout_transition=0:weights=1 1"
            else:
                amix_params = "inputs=2:duration=first:weights=1 1"
                
            cmd = [
                'ffmpeg', '-y', '-i', str(video_path), '-i', str(audio_path),
                '-filter_complex', f'[1:a]{audio_volume_filter}[tts_audio];[0:a][tts_audio]amix={amix_params}[aout]',
                '-map', '0:v', '-map', '[aout]',
                '-c:v', 'copy',  # 视频流直接复制，不重新编码
                '-c:a', 'aac',   # 音频编码为AAC
                '-ar', '44100',  # 设置音频采样率为44.1kHz
                '-ac', '2',      # 设置音频通道为立体声
                '-b:a', '128k',  # 音频比特率
                '-strict', 'experimental',
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
            print(f"[TTS音频处理] 检测到视频已有音频流（可能包含背景音乐），使用amix混合TTS和现有音频")
        else:
            # 视频没有音频流，直接添加TTS音频
            cmd = [
                'ffmpeg', '-y', '-i', str(video_path), '-i', str(audio_path),
                '-filter_complex', f'[1:a]{audio_volume_filter}[audio]',
                '-map', '0:v', '-map', '[audio]',
                '-c:v', 'copy',  # 视频流直接复制，不重新编码
                '-c:a', 'aac',   # 音频编码为AAC
                '-ar', '44100',  # 设置音频采样率为44.1kHz
                '-ac', '2',      # 设置音频通道为立体声
                '-b:a', '128k',  # 音频比特率
                '-strict', 'experimental',
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
        
        print(f"执行音频混合命令: {' '.join(cmd)}")
        if run_ffmpeg_command(cmd):
            print(f"成功将TTS音频添加到视频: {output_path}")
            return True
        else:
            print("添加TTS音频失败")
            return False
    except Exception as e:
        print(f"添加TTS音频时出错: {e}")
        return False


@log_with_capture
def generate_subtitle_tts(subtitle_text, voice, output_path):
    """
    生成字幕的TTS音频
    
    参数:
        subtitle_text: 字幕文本
        voice: TTS语音
        output_path: 输出音频文件路径
        
    返回:
        bool: 是否成功生成音频
    """
    try:
        # 检测文本语言并选择合适的语音
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in subtitle_text)
        is_thai = any('\u0e00' <= char <= '\u0e7f' for char in subtitle_text)
        is_malay = not (is_chinese or is_thai)  # 简单判断，如果不是中文或泰文，则假设为马来文
        
        # 根据文本语言选择合适的语音
        selected_voice = voice  # 默认使用传入的语音
        if is_chinese and not voice.startswith('zh-'):
            selected_voice = "zh-CN-XiaoxiaoNeural"  # 中文默认使用小晓
            print(f"检测到中文文本，自动切换为中文语音: {selected_voice}")
        elif is_thai and not voice.startswith('th-'):
            selected_voice = "th-TH-PremwadeeNeural"  # 泰文默认使用Premwadee
            print(f"检测到泰文文本，自动切换为泰文语音: {selected_voice}")
        elif is_malay and not voice.startswith('ms-'):
            selected_voice = "ms-MY-YasminNeural"  # 马来文默认使用Yasmin
            print(f"检测到马来文文本，自动切换为马来文语音: {selected_voice}")
        
        print(f"使用语音: {selected_voice} 生成TTS音频")
        
        # 使用异步方式生成TTS音频
        # 检查是否已经在事件循环中
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_running_loop()
            # 如果已经在事件循环中，创建一个新的线程来运行asyncio.run()
            import threading
            result = False
            exception = None
            
            def run_in_thread():
                nonlocal result, exception
                try:
                    # 在新线程中运行asyncio.run()
                    result = asyncio.run(generate_tts_audio(subtitle_text, selected_voice, output_path))
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()  # 等待线程完成
            
            if exception:
                raise exception
                
        except RuntimeError:
            # 如果没有运行中的事件循环，使用asyncio.run()
            result = asyncio.run(generate_tts_audio(subtitle_text, selected_voice, output_path))
        return result
    except Exception as e:
        print(f"生成字幕TTS音频失败: {e}")
        import traceback
        traceback.print_exc()
        return False