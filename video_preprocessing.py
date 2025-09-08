#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频预处理模块
负责视频预处理功能，包括视频拼接、水印处理、正放倒放等
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
import uuid
from PIL import Image, ImageDraw, ImageFont

# 导入工具函数
from utils import get_video_info, get_audio_duration, run_ffmpeg_command, get_data_path, ensure_dir, load_style_config, find_font_file, find_matching_image, generate_tts_audio, load_subtitle_config

# 导入日志管理器
from log_manager import init_logging, log_with_capture

# 初始化日志系统
log_manager = init_logging()


def process_short_video_reverse_effect(video_path, output_path, temp_dir):
    """
    处理短视频（5秒以下），进行正放+倒放拼接
    
    参数:
        video_path: 输入视频路径
        output_path: 输出视频路径
        temp_dir: 临时目录
        
    返回:
        处理后的视频路径
    """
    output_path_file = temp_dir / "forward_reverse.mp4"
    
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
        str(output_path_file)
    ]
    
    if run_ffmpeg_command(cmd):
        return output_path_file
    
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

    # 3. 创建循环视频
    concat_file = temp_dir / "concat.txt"
    concat_file.write_text(f"file '{forward_path}'\nfile '{reverse_path}'\n")

    cmd_concat = [
        'ffmpeg', '-y', 
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_file),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-profile:v', 'main', '-level', '3.1',
        '-preset', 'ultrafast',
        '-brand', 'mp42',  # 设置兼容的品牌标记
        '-tag:v', 'avc1',  # 使用标准AVC标记
        # '-an',  # 不要音频 - 移除这行以保留音频轨道
        str(output_path_file)
    ]
    if not run_ffmpeg_command(cmd_concat):
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
        str(output_path_file)
    ]
    
    if run_ffmpeg_command(cmd_concat):
        return output_path_file
    
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
    
    # 创建转换后的临时文件，使用唯一文件名避免冲突
    resized_path = temp_dir / f"resized_{uuid.uuid4().hex}.mp4"
    
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
        str(resized_path)
    ]
    
    print(f"【去水印】执行命令: {' '.join(resize_cmd)}")
    if not run_ffmpeg_command(resize_cmd):
        print("去水印处理失败，使用原始视频")
        return video_path
    
    print(f"【去水印】处理成功: {resized_path}")
    return resized_path


def preprocess_video_without_reverse(video_path, temp_dir, duration=None):
    """
    视频预处理函数 - 仅进行水印处理，不进行正放倒放处理
    
    参数:
        video_path: 视频文件路径
        temp_dir: 临时目录路径
        duration: 视频时长（秒），如果为None则自动获取
        
    返回:
        预处理后的视频路径，失败返回None
    """
    from pathlib import Path
    import uuid
    
    print(f"开始预处理视频（不进行正放倒放）: {video_path}")
    
    # 获取视频信息
    if duration is None:
        video_info = get_video_info(video_path)
        if not video_info:
            print("无法获取视频信息")
            return None
        width, height, duration = video_info
    
    print(f"视频时长: {duration}秒")
    
    # 对所有视频都进行水印处理（缩放裁剪去水印），但不进行正放倒放处理
    # 使用唯一文件名避免冲突
    unique_id = uuid.uuid4().hex
    temp_output_path = temp_dir / f"processed_{unique_id}.mp4"
    print(f"进行水印处理，缩放系数: 1.1，输出路径: {temp_output_path}")
    processed_path = process_normal_video(video_path, temp_dir, scale_factor=1.1)
    
    if not processed_path:
        print("水印处理失败")
        return None
    
    # 如果处理后的文件名不是我们期望的唯一文件名，则重命名
    if processed_path != str(temp_output_path):
        try:
            shutil.move(processed_path, temp_output_path)
            processed_path = str(temp_output_path)
            print(f"重命名处理后的视频: {processed_path}")
        except Exception as e:
            print(f"重命名处理后的视频失败: {e}")
            return None
    
    print(f"预处理完成: {processed_path}")
    return processed_path


def preprocess_video_by_type(video_path, temp_dir, duration=None):
    """
    根据视频时长类型进行预处理
    
    参数:
        video_path: 视频文件路径
        temp_dir: 临时目录路径
        duration: 视频时长（秒），如果为None则自动获取
        
    返回:
        预处理后的视频路径，失败返回None
    """
    from pathlib import Path
    
    print(f"开始预处理视频: {video_path}")
    
    # 获取视频信息
    if duration is None:
        video_info = get_video_info(video_path)
        if not video_info:
            print("无法获取视频信息")
            return None
        width, height, duration = video_info
    
    print(f"视频时长: {duration}秒")
    
    # 对所有视频都进行水印处理（缩放裁剪去水印）
    print(f"进行水印处理，缩放系数: 1.1")
    processed_path = process_normal_video(video_path, temp_dir, scale_factor=1.1)
    
    if not processed_path:
        print("水印处理失败")
        return None
    
    # 如果是短视频，需要进行正放+倒放处理
    if duration < 9.0:
        print(f"短视频: 将进行正放+倒放处理")
        # 将已处理过水印的视频进行正放+倒放处理
        reversed_path = temp_dir / "forward_reverse.mp4"
        if process_short_video_reverse_effect(processed_path, reversed_path, temp_dir):
            processed_path = reversed_path
    
    print(f"预处理完成: {processed_path}")
    return processed_path


def process_folder_videos(folder_path, temp_dir, transition_duration=0.3):
    """
    处理文件夹中的所有视频文件，按文件名排序后拼接成一个视频，每两个视频之间添加叠化转场
    
    参数:
        folder_path: 包含视频文件的文件夹路径
        temp_dir: 临时目录路径
        transition_duration: 转场持续时间（秒），默认0.3秒
        
    返回:
        拼接后的视频路径，失败返回None
    """
    from pathlib import Path
    import os
    import subprocess
    
    print(f"开始处理文件夹中的视频: {folder_path}")
    print(f"转场持续时间: {transition_duration}秒")
    
    # 支持的视频扩展名
    video_extensions = {'.mp4', '.mov', '.avi', '.wmv', '.mkv'}
    
    # 获取文件夹中的所有视频文件并按文件名排序
    video_files = []
    folder_path_obj = Path(folder_path)
    
    if not folder_path_obj.exists() or not folder_path_obj.is_dir():
        print(f"错误: 指定的路径不是有效文件夹: {folder_path}")
        return None
    
    for file_path in folder_path_obj.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in video_extensions:
            video_files.append(file_path)
    
    # 按文件名排序
    video_files.sort(key=lambda x: x.name)
    
    if not video_files:
        print(f"文件夹中没有找到视频文件: {folder_path}")
        return None
    
    print(f"找到 {len(video_files)} 个视频文件:")
    for i, video_file in enumerate(video_files):
        print(f"  {i+1}. {video_file.name}")
    
    # 如果只有一个视频文件，直接返回该文件路径（但仍需要进行水印处理，但不进行正放倒放处理）
    if len(video_files) == 1:
        print("只有一个视频文件，进行水印处理后返回（不进行正放倒放处理）")
        # 对于文件夹中的单个视频，不进行正放倒放处理
        return preprocess_video_without_reverse(str(video_files[0]), temp_dir)
    
    # 对文件夹中的每个视频先进行预处理（仅水印处理，不进行正放倒放处理）
    processed_videos = []
    for i, video_file in enumerate(video_files):
        # 获取视频信息
        video_info = get_video_info(str(video_file))
        if video_info:
            width, height, duration = video_info
            print(f"处理视频: {video_file.name}, 时长: {duration:.2f}秒")
            # 对每个视频进行预处理（仅水印处理，不进行正放倒放处理）
            processed_video = preprocess_video_without_reverse(str(video_file), temp_dir)
            if processed_video:
                processed_videos.append(processed_video)
            else:
                print(f"视频预处理失败: {video_file.name}")
                return None
        else:
            print(f"无法获取视频信息: {video_file.name}")
            return None
    
    print(f"准备拼接 {len(processed_videos)} 个预处理后的视频文件")
    
    # 使用ffmpeg拼接视频，添加叠化转场
    output_path = temp_dir / f"{folder_path_obj.name}_merged.mp4"
    print(f"拼接后的视频将保存到: {output_path}")
    
    # 构建带有叠化转场的拼接命令
    if len(processed_videos) == 2:
        # 两个视频的简单情况
        print("处理两个视频的拼接")
        # 获取第一个视频的时长，以便正确设置转场偏移
        first_video_duration = 5.0  # 默认值
        try:
            duration_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', processed_videos[0]
            ]
            result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
            first_video_duration = float(result.stdout.strip())
            print(f"获取第一个视频时长成功: {processed_videos[0]} -> {first_video_duration:.2f}秒")
        except Exception as e:
            print(f"获取第一个视频时长失败，使用默认值5秒: {e}")
        
        # 正确设置转场偏移，使其在第一个视频结束时开始
        filter_complex = f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset={first_video_duration-transition_duration}[vout]"
        print(f"滤镜命令: {filter_complex}")
    else:
        # 多个视频的情况 - 构建正确的xfade链
        filter_complex_parts = []
        
        # 首先获取每个视频的时长，以便正确计算转场偏移
        video_durations = []
        for video_path in processed_videos:
            # 使用ffprobe获取视频时长
            duration_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', video_path
            ]
            try:
                result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
                duration = float(result.stdout.strip())
                video_durations.append(duration)
                print(f"获取视频时长成功: {video_path} -> {duration:.2f}秒")
            except Exception as e:
                print(f"获取视频时长失败 {video_path}: {e}")
                # 如果获取失败，使用默认值5秒
                video_durations.append(5.0)
        
        # 计算累积时间偏移
        cumulative_offset = 0.0
        print(f"开始计算转场偏移...")
        
        # 对于多个视频，需要链式应用xfade
        for i in range(len(processed_videos) - 1):
            if i == 0:
                # 第一个xfade
                filter_complex_parts.append(f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset={cumulative_offset}[tmp0]")
                print(f"第1个转场: 偏移={cumulative_offset:.2f}秒")
            else:
                # 后续的xfade，使用前一个结果
                filter_complex_parts.append(f"[tmp{i-1}][{i+1}:v]xfade=transition=fade:duration={transition_duration}:offset={cumulative_offset}[tmp{i}]")
                print(f"第{i+1}个转场: 偏移={cumulative_offset:.2f}秒")
            
            # 更新累积偏移：前一个视频的时长减去转场时间
            cumulative_offset += video_durations[i] - transition_duration
            print(f"  更新累积偏移: {cumulative_offset:.2f}秒 (前一个视频时长: {video_durations[i]:.2f}秒)")
        
        # 最后一个tmp是最终输出
        filter_complex = ";".join(filter_complex_parts)
        # 将最后一个tmp替换为vout
        filter_complex = filter_complex.replace(f"[tmp{len(processed_videos)-2}]", "[vout]")
        print(f"完整滤镜命令: {filter_complex}")
    
    # 构建完整的ffmpeg命令
    cmd = [
        'ffmpeg', '-y'
    ]
    
    # 添加所有输入文件
    for video_path in processed_videos:
        cmd.extend(['-i', str(video_path)])
    
    # 添加滤镜
    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[vout]',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-profile:v', 'main',
        '-level', '3.1',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-b:v', '4M',
        '-movflags', '+faststart',
        '-brand', 'mp42',
        '-tag:v', 'avc1',
        '-an',  # 不要音频
        str(output_path)
    ])
    
    print(f"执行拼接命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if output_path.exists():
            print(f"文件夹视频拼接成功: {output_path}")
            # 获取拼接后视频的信息
            merged_info = get_video_info(str(output_path))
            if merged_info:
                width, height, duration = merged_info
                print(f"拼接后视频信息: 时长: {duration:.2f}秒, 分辨率: {width}x{height}")
            return str(output_path)
        else:
            print("拼接失败：输出文件不存在")
            return None
    except subprocess.CalledProcessError as e:
        print(f"拼接失败: {e}")
        print(f"错误输出: {e.stderr.decode()}")
        # 如果xfade滤镜失败，尝试使用简单的concat滤镜
        print("尝试使用简单拼接方式...")
        
        # 创建concat文件列表
        concat_file = temp_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for video_path in processed_videos:
                # 转义特殊字符
                escaped_path = str(video_path).replace("'", "'\"'\"'")
                f.write(f"file '{escaped_path}'\n")
        
        # 使用concat demuxer方式拼接
        simple_concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main',
            '-level', '3.1',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-b:v', '4M',
            '-movflags', '+faststart',
            '-brand', 'mp42',
            '-tag:v', 'avc1',
            '-an',
            str(output_path)
        ]
        
        try:
            subprocess.run(simple_concat_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if output_path.exists():
                print(f"文件夹视频简单拼接成功: {output_path}")
                # 获取拼接后视频的信息
                merged_info = get_video_info(str(output_path))
                if merged_info:
                    width, height, duration = merged_info
                    print(f"简单拼接后视频信息: 时长: {duration:.2f}秒, 分辨率: {width}x{height}")
                return str(output_path)
        except subprocess.CalledProcessError as e2:
            print(f"简单拼接也失败了: {e2}")
            print(f"错误输出: {e2.stderr.decode()}")
            return None
    except Exception as e:
        print(f"拼接过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        return None