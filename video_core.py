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
import time
import logging
import asyncio

# 导入工具函数
from utils import get_video_info, get_audio_duration, run_ffmpeg_command, get_data_path, ensure_dir, load_style_config, find_font_file, find_matching_image, generate_tts_audio, load_subtitle_config

# 导入日志管理器
from log_manager import init_logging, log_with_capture

# 初始化日志系统
log_manager = init_logging()

# 全局变量已移除，现在直接使用video_index计算音乐索引


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
import uuid
from PIL import Image, ImageDraw, ImageFont


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
def process_video(video_path, output_path=None, style=None, subtitle_lang=None, 
                 quicktime_compatible=False, img_position_x=100, img_position_y=0,
                 font_size=70, subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                 subtitle_text_x=0, subtitle_text_y=1190, random_position=False, enable_subtitle=True,
                 enable_background=True, enable_image=True, enable_music=False, music_path="",
                 music_mode="single", music_volume=50, document_path=None, enable_gif=False, 
                 gif_path="", gif_loop_count=-1, gif_scale=1.0, gif_rotation=0, gif_x=800, gif_y=100, scale_factor=1.1, 
                 image_path=None, subtitle_width=800, quality_settings=None, progress_callback=None,
                 video_index=0, enable_tts=False, tts_voice="zh-CN-XiaoxiaoNeural", 
                 tts_volume=100, tts_text="", auto_match_duration=False,
                 enable_dynamic_subtitle=False, animation_style="高亮放大", animation_intensity=1.5, highlight_color="#FFD700",
                 match_mode="随机样式", position_x=540, position_y=960):  # 添加动态字幕参数
    """
    处理视频的主函数（精处理阶段）
    
    参数:
        video_path: 视频文件路径（已经过预处理的视频）
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
        progress_callback: 进度回调函数，用于报告处理进度
        enable_tts: 是否启用TTS功能
        tts_voice: TTS语音
        tts_volume: TTS音量（百分比）
        tts_text: TTS文本
        auto_match_duration: 是否自动匹配视频时长（根据视频时长和配音时长计算变速系数）
        
    返回:
        处理后的视频路径，失败返回None
    """
    print(f"开始精处理视频: {video_path}")
    print(f"图片位置设置: 水平={img_position_x}（宽度比例）, 垂直={img_position_y}（像素偏移）")
    
    # 添加背景音乐详细日志 - process_video函数接收参数阶段
    print(f"[背景音乐日志] process_video函数接收参数:")
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
            print(f"[背景音乐日志] process_video警告: 启用了背景音乐但音乐路径为空")
        else:
            music_file_path = Path(music_path)
            if music_file_path.exists():
                print(f"[背景音乐日志] process_video确认音乐文件存在: {music_file_path.absolute()}")
                print(f"[背景音乐日志] 音乐文件大小: {music_file_path.stat().st_size} 字节")
            else:
                print(f"[背景音乐日志] process_video错误: 音乐文件不存在: {music_file_path.absolute()}")
    else:
        print(f"[背景音乐日志] process_video: 背景音乐功能未启用")
    
    # 如果未指定输出路径，则生成一个
    if not output_path:
        video_name = Path(video_path).stem
        # 使用相对路径的output目录
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{video_name}_processed.mp4"
    else:
        # 确保输出路径的目录存在
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
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
        
        # 直接使用预处理后的视频，不再进行额外的预处理
        processed_path = video_path
        print(f"使用预处理后的视频: {processed_path}")
        
        # 如果启用了TTS，先生成TTS音频
        tts_audio_path = None
        if enable_tts and tts_text:
            print("生成TTS音频...")
            tts_audio_path = temp_dir / "tts_audio.mp3"
            if generate_subtitle_tts(tts_text, tts_voice, str(tts_audio_path)):
                print(f"TTS音频生成成功: {tts_audio_path}")
                # 检查生成的音频文件是否存在且不为空
                if tts_audio_path.exists() and tts_audio_path.stat().st_size > 0:
                    print(f"TTS音频文件验证成功: {tts_audio_path}")
                    
                    # 如果启用了自动匹配时长，计算并应用变速系数
                    if auto_match_duration:
                        print("[自动匹配时长] 开始计算变速系数...")
                        audio_duration = get_audio_duration(str(tts_audio_path))
                        if audio_duration and audio_duration > 0:
                            # 计算变速系数：音频时长 / 视频时长
                            speed_ratio = audio_duration / duration
                            print(f"[自动匹配时长] 视频时长: {duration}秒, 配音时长: {audio_duration}秒")
                            print(f"[自动匹配时长] 计算变速系数: {speed_ratio:.3f}")
                            
                            # 如果变速系数不等于1，应用变速处理
                            if abs(speed_ratio - 1.0) > 0.01:  # 允许1%的误差
                                print(f"[自动匹配时长] 应用变速处理，系数: {speed_ratio:.3f}")
                                adjusted_audio_path = temp_dir / "tts_audio_adjusted.mp3"
                                
                                # 使用FFmpeg的atempo滤镜调整音频速度
                                # atempo的有效范围是0.5-100，如果超出范围需要多次应用
                                tempo_cmd = ['ffmpeg', '-y', '-i', str(tts_audio_path)]
                                
                                # 构建atempo滤镜链
                                filter_parts = []
                                remaining_ratio = speed_ratio
                                
                                while remaining_ratio > 2.0:
                                    filter_parts.append('atempo=2.0')
                                    remaining_ratio /= 2.0
                                while remaining_ratio < 0.5:
                                    filter_parts.append('atempo=0.5')
                                    remaining_ratio /= 0.5
                                
                                if remaining_ratio != 1.0:
                                    filter_parts.append(f'atempo={remaining_ratio:.3f}')
                                
                                if filter_parts:
                                    filter_complex = ','.join(filter_parts)
                                    tempo_cmd.extend(['-filter:a', filter_complex])
                                
                                tempo_cmd.extend(['-c:a', 'mp3', str(adjusted_audio_path)])
                                
                                print(f"[自动匹配时长] 执行变速命令: {' '.join(tempo_cmd)}")
                                if run_ffmpeg_command(tempo_cmd):
                                    if adjusted_audio_path.exists() and adjusted_audio_path.stat().st_size > 0:
                                        tts_audio_path = adjusted_audio_path
                                        print(f"[自动匹配时长] 变速处理成功: {tts_audio_path}")
                                        
                                        # 验证调整后的音频时长
                                        new_duration = get_audio_duration(str(tts_audio_path))
                                        if new_duration:
                                            print(f"[自动匹配时长] 调整后音频时长: {new_duration:.2f}秒")
                                    else:
                                        print("[自动匹配时长] 变速处理失败，使用原始音频")
                                else:
                                    print("[自动匹配时长] 变速命令执行失败，使用原始音频")
                            else:
                                print(f"[自动匹配时长] 变速系数接近1.0，无需调整")
                        else:
                            print("[自动匹配时长] 无法获取音频时长，跳过变速处理")
                else:
                    print("TTS音频文件不存在或为空")
                    tts_audio_path = None
            else:
                print("TTS音频生成失败")
                tts_audio_path = None
        
        # 3. 添加字幕和其他效果，传递所有参数
        print(f"[背景音乐日志] process_video调用add_subtitle_to_video前:")
        print(f"  - 传递enable_music: {enable_music}")
        print(f"  - 传递music_path: '{music_path}'")
        print(f"  - 传递music_mode: {music_mode}")
        print(f"  - 传递music_volume: {music_volume}")
        print(f"  - 视频索引: {video_index}")
        
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
            gif_rotation=gif_rotation,
            gif_x=gif_x,
            gif_y=gif_y,
            scale_factor=scale_factor,
            image_path=image_path,
            subtitle_width=subtitle_width,
            quality_settings=quality_settings,
            progress_callback=progress_callback,  # 添加进度回调函数
            video_index=video_index,  # 传递视频索引参数
            enable_dynamic_subtitle=enable_dynamic_subtitle,
            animation_style=animation_style,
            animation_intensity=animation_intensity,
            highlight_color=highlight_color,
            match_mode=match_mode,
            position_x=position_x,
            position_y=position_y
        )
        
        if not final_path:
            print("添加字幕失败")
            return None
            
        # 如果生成了TTS音频，将其添加到视频中
        if tts_audio_path and tts_audio_path.exists() and tts_audio_path.stat().st_size > 0:
            print("将TTS音频添加到视频中...")
            final_with_tts_path = temp_dir / "final_with_tts.mp4"
            if add_tts_audio_to_video(final_path, str(tts_audio_path), str(final_with_tts_path), tts_volume):
                # 如果成功添加TTS音频，使用带TTS的版本作为最终输出
                final_path = str(final_with_tts_path)
                print(f"TTS音频已添加到视频中: {final_path}")
                # 验证输出文件是否存在
                if Path(final_path).exists():
                    print(f"带TTS的视频文件已生成: {final_path}")
                    # 将最终文件复制到输出路径，确保不会在临时目录被清理时删除
                    import shutil
                    shutil.copy2(final_path, output_path)
                    final_path = str(output_path)
                else:
                    print("带TTS的视频文件生成失败")
                    final_path = final_path.replace("_with_tts", "")  # 回退到原始文件
            else:
                print("添加TTS音频到视频失败，使用无TTS版本")
        elif tts_audio_path:
            print("TTS音频文件不存在或为空，跳过添加TTS音频步骤")
        
        print(f"视频处理完成: {final_path}")
        return final_path
        
    except Exception as e:
        print(f"处理视频时出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 记录详细的错误信息
        error_msg = f"视频处理失败 - 文件: {video_path}, 错误: {str(e)}"
        print(error_msg)
        
        # 如果有进度回调，报告错误
        if progress_callback:
            progress_callback(f"处理失败: {str(e)}", 0.0)
        
        return None
    finally:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass


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


def process_animated_gif_for_video(gif_path, temp_dir, scale_factor=1.0, loop_count=-1, video_duration=None, gif_rotation=0):
    """
    为视频处理专门优化的动画GIF处理函数
    
    参数:
        gif_path: 原始GIF文件路径
        temp_dir: 临时目录路径
        scale_factor: 缩放因子
        loop_count: 循环次数 (-1表示无限循环)
        video_duration: 视频时长（秒），用于确保GIF持续整个视频时长
        gif_rotation: 旋转角度（度），0-359度
        
    返回:
        处理后的GIF文件路径，失败返回None
    """
    try:
        if not Path(gif_path).exists():
            print(f"GIF文件不存在: {gif_path}")
            return None
        
        # 输出路径
        processed_gif_path = temp_dir / "processed_animated_gif.gif"
        
        # 如果提供了视频时长，计算需要的循环次数
        if video_duration is not None:
            # 获取原始GIF的持续时间
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
        gif_cmd = [
            'ffmpeg', '-y',
            '-stream_loop', str(required_loops),  # 循环播放
            '-i', str(gif_path)
        ]
        
        # 如果提供了视频时长，限制GIF时长
        if video_duration is not None:
            gif_cmd.extend(['-t', str(video_duration)])
        
        # 添加缩放和旋转过滤器（如果需要）
        filters = []
        if scale_factor != 1.0:
            filters.append(f"scale=iw*{scale_factor}:ih*{scale_factor}")
        
        # 添加旋转过滤器（总是添加以确保正确方向）
        # FFmpeg的rotate滤镜是逆时针旋转，需要取负值来实现顺时针旋转
        # 将角度转换为弧度，并取负值
        # 只有在UI中调整了参数时才应用旋转角度
        base_rotation = 0  # 不再使用基础旋转角度，只使用用户设置的旋转角度
        actual_rotation = base_rotation + gif_rotation
        rotation_radians = -actual_rotation * 3.14159265359 / 180
        filters.append(f"rotate={rotation_radians}:fillcolor=none:bilinear=0")
        print(f"【GIF旋转】应用旋转角度: {actual_rotation}度 (基础: {base_rotation}度 + 用户设置: {gif_rotation}度)")
        
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
            cmd = [
                'ffmpeg', '-y', '-i', str(video_path), '-i', str(audio_path),
                '-filter_complex', f'[1:a]{audio_volume_filter}[tts_audio];[0:a][tts_audio]amix=inputs=2:duration=first:weights=1 1[aout]',
                '-map', '0:v', '-map', '[aout]',
                '-c:v', 'copy',  # 视频流直接复制，不重新编码
                '-c:a', 'aac',   # 音频编码为AAC
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


@log_with_capture
def add_subtitle_to_video(video_path, output_path, style=None, subtitle_lang=None, 
                        original_video_path=None, quicktime_compatible=False, 
                        img_position_x=100, img_position_y=0, font_size=70, 
                        subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                        subtitle_text_x=0, subtitle_text_y=1190, random_position=False, enable_subtitle=True,
                        enable_background=True, enable_image=True, enable_music=False, music_path="",
                        music_mode="single", music_volume=50, document_path=None, enable_gif=False, 
                        gif_path="", gif_loop_count=-1, gif_scale=1.0, gif_rotation=0, gif_x=800, gif_y=100, scale_factor=1.1, 
                        image_path=None, subtitle_width=800, quality_settings=None, progress_callback=None,
                        video_index=0, enable_dynamic_subtitle=False, animation_style="高亮放大", 
                        animation_intensity=1.5, highlight_color="#FFD700", match_mode="随机样式", 
                        position_x=540, position_y=960):  # 添加动态字幕参数
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
        progress_callback: 进度回调函数，用于报告处理进度
        
    返回:
        处理后的视频路径
    """
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())
    print(f"使用临时目录: {temp_dir}")
    
    try:
        # 添加背景音乐详细日志 - add_subtitle_to_video函数接收参数阶段
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
        
        # 报告进度：开始处理
        if progress_callback:
            progress_callback("开始处理视频", 5.0)
            
        # 1. 获取视频信息
        video_info = get_video_info(video_path)
        if not video_info:
            print("无法获取视频信息")
            return None
            
        width, height, duration = video_info
        print(f"视频信息: {width}x{height}, {duration}秒")
        
        # 报告进度：获取视频信息完成
        if progress_callback:
            progress_callback("获取视频信息", 10.0)
        
        # 2. 加载字幕配置
        subtitle_df = None
        
        # 检查是否启用动态字幕
        if enable_dynamic_subtitle:
            print(f"[动态字幕] 启用动态字幕功能")
            print(f"[动态字幕] 动画样式: {animation_style}")
            print(f"[动态字幕] 动画强度: {animation_intensity}")
            print(f"[动态字幕] 高亮颜色: {highlight_color}")
            
            # 导入动态字幕模块
            try:
                from dynamic_subtitle import DynamicSubtitleProcessor
                dynamic_processor = DynamicSubtitleProcessor(
                    animation_style=animation_style,
                    animation_intensity=animation_intensity,
                    highlight_color=highlight_color,
                    match_mode=match_mode,
                    position_x=position_x,
                    position_y=position_y
                )
                print(f"[动态字幕] 动态字幕处理器初始化成功")
            except ImportError as e:
                print(f"[动态字幕] 导入动态字幕模块失败: {e}")
                enable_dynamic_subtitle = False
        
        # 检查GIF文件是否存在
        if enable_gif and gif_path and Path(gif_path).exists():
            print(f"GIF文件存在: {gif_path}")
        elif enable_gif and gif_path:
            print(f"GIF文件不存在: {gif_path}")
            
        # 尝试加载用户指定的文档
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
                # 加载默认的字幕配置文件
                subtitle_df = load_subtitle_config()
                if subtitle_df is not None and not subtitle_df.empty:
                    print(f"成功加载默认字幕配置: {len(subtitle_df)} 条记录")
                    print(f"默认配置列名: {list(subtitle_df.columns)}")
                else:
                    print("默认字幕配置为空或不存在")
                    # 创建一个简单的默认配置（使用新的列名）
                    default_data = {
                        'name': ['default'],
                        'title': ['特价促销\n现在下单立即享受优惠'],
                        'cn_prompt': ['特价促销\n现在下单立即享受优惠'],  # 修改列名
                        'malay_prompt': ['Grab cepat\nStok laris seperti roti canai'],  # 修改列名
                        'thai_prompt': ['ราคาพิเศษ\nซื้อเลยอย่ารอช้า']  # 修改列名
                    }
                    subtitle_df = pd.DataFrame(default_data)
                    print("使用默认字幕数据")
            except Exception as e:
                print(f"加载默认字幕配置失败: {e}")
                # 创建一个简单的默认配置（使用新的列名）
                default_data = {
                    'name': ['default'],
                    'title': ['特价促销\n现在下单立即享受优惠'],
                    'cn_prompt': ['特价促销\n现在下单立即เข้าร่วม'],  # 修改列名
                    'malay_prompt': ['Grab cepat\nStok laris seperti roti canai'],  # 修改列名
                    'thai_prompt': ['ราคาพิเศษ\nซื้อเลยอย่ารอช้า']  # 修改列名
                }
                subtitle_df = pd.DataFrame(default_data)
                print("使用默认字幕データ")
        
        # 获取视频目录
        videos_dir = get_data_path("input/videos")
        # 使用相对路径的output目录
        output_dir = Path("output")
        
        # 确保目录存在
        if not Path(videos_dir).exists():
            print(f"视频目录不存在: {videos_dir}")
            return None
        
        # 确保输出路径的目录存在
        if output_path:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        else:
            print("输出路径为空")
            return None
        
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                print(f"创建输出目录: {output_dir}")
            except Exception as e:
                print(f"创建输出目录失败: {e}")
                return None

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
        
        # 报告进度：样式和语言选择完成
        if progress_callback:
            progress_callback("样式和语言选择完成", 20.0)
            
        # 4. 处理随机位置逻辑
        if random_position:
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
            logging.info(f"🎲 随机字幕位置: 原始({subtitle_text_x}, {subtitle_text_y}) -> 随机({new_subtitle_text_x}, {new_subtitle_text_y})")
            logging.info(f"📎 随机范围: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
            
            # 更新位置参数
            subtitle_text_x = new_subtitle_text_x
            subtitle_text_y = new_subtitle_text_y
        else:
            print(f"📍 使用固定字幕位置: ({subtitle_text_x}, {subtitle_text_y})")
            logging.info(f"📍 使用固定字幕位置: ({subtitle_text_x}, {subtitle_text_y})")
        
        # 报告进度：位置处理完成
        if progress_callback:
            progress_callback("位置处理完成", 25.0)
            
        # 5. 查找匹配的图片（仅在启用图片时）
        has_image = False
        matched_image_path = None
        final_image_path = None  # 初始化final_image_path变量
        processed_img_path = None  # 初始化processed_img_path变量
        
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
                print(f"📁 调用find_matching_image参数: video_name={original_video_name}, custom_image_path={image_path}")
                matched_image_path = find_matching_image(original_video_name, custom_image_path=image_path)
                print(f"📁 find_matching_image返回结果: {matched_image_path}")
                
            # 如果没有找到，使用当前视频路径
            if not matched_image_path:
                video_name = Path(video_path).stem
                print(f"📁 使用当前视频名查找图片: {video_name}")
                print(f"📁 调用find_matching_image参数: video_name={video_name}, custom_image_path={image_path}")
                matched_image_path = find_matching_image(video_name, custom_image_path=image_path)
                print(f"📁 find_matching_image返回结果: {matched_image_path}")
                
            # 使用匹配的图片路径
            final_image_path = matched_image_path
            print(f"📁 最终图片路径: {final_image_path}")
            
            if final_image_path:
                print(f"✅ 找到匹配的图片: {final_image_path}")
                # 验证图片文件是否真实存在
                if Path(final_image_path).exists():
                    print(f"✅ 图片文件确实存在: {final_image_path}")
                else:
                    print(f"❌ 图片文件不存在: {final_image_path}")
                    final_image_path = None
            else:
                print("⚠️ 没有找到匹配的图片")
        else:
            print("❌ 图片功能已禁用，跳过图片查找")
            
        if final_image_path and enable_image:
            print(f"✅ 找到匹配的图片: {final_image_path}")
            # 6. 处理图片
            print(f"【图片流程】开始处理图片 {final_image_path}，大小设置为 {img_size}x{img_size}")
            processed_img_path = temp_dir / "processed_image.png"
            print(f"【图片流程】临时处理图片路径: {processed_img_path}")
            
            # 调用图片处理函数
            print(f"【图片流程】调用process_image_for_overlay参数: input={final_image_path}, output={processed_img_path}, size=({img_size}, {img_size})")
            processed_img = process_image_for_overlay(
                final_image_path,
                str(processed_img_path),
                size=(img_size, img_size)  # 使用传入的img_size参数
            )
            print(f"【图片流程】process_image_for_overlay返回结果: {processed_img}")
            
            if not processed_img:
                print("❌ 处理图片失败，跳过图片叠加")
                has_image = False
            else:
                print(f"✅ 【图片流程】图片处理成功: {processed_img}")
                # 验证处理后的图片文件是否存在
                if Path(processed_img).exists():
                    print(f"✅ 处理后的图片文件确实存在: {processed_img}")
                    file_size = Path(processed_img).stat().st_size
                    print(f"✅ 处理后的图片文件大小: {file_size} 字节")
                else:
                    print(f"❌ 处理后的图片文件不存在: {processed_img}")
                has_image = True
        elif enable_image and not final_image_path:
            print("⚠️ 图片功能已启用但没有找到匹配的图片")
            print("📁 尝试使用默认图片...")
            
            # 检查图片目录是否存在
            image_dir = get_data_path("input/images")
            image_dir_path = Path(image_dir)
            print(f"📁 【图片目录调试】默认图片目录路径: {image_dir}")
            print(f"📁 【图片目录调试】图片目录是否存在: {image_dir_path.exists()}")
            
            if enable_image and image_dir_path.exists():
                print(f"图片目录存在: {image_dir}")
                # 列出目录中的文件
                try:
                    image_files = [f.name for f in image_dir_path.iterdir() if f.is_file()]
                    print(f"图片目录中的文件数量: {len(image_files)}")
                    if image_files:
                        print(f"图片目录中的文件: {image_files[:5]}{'...' if len(image_files) > 5 else ''}")
                    else:
                        print("图片目录为空")
                except Exception as e:
                    print(f"列出图片目录文件时出错: {e}")
            elif enable_image:
                print(f"图片目录不存在: {image_dir}")
                
            # 如果用户指定了图片路径，也检查该路径
            if image_path:
                user_image_path = Path(image_path)
                print(f"📁 【用户图片路径调试】用户指定图片路径: {image_path}")
                print(f"📁 【用户图片路径调试】用户图片路径是否存在: {user_image_path.exists()}")
                if user_image_path.exists():
                    try:
                        user_image_files = [f.name for f in user_image_path.iterdir() if f.is_file()]
                        print(f"📁 【用户图片路径调试】用户图片目录中的文件数量: {len(user_image_files)}")
                        if user_image_files:
                            print(f"📁 【用户图片路径调试】用户图片目录中的文件: {user_image_files[:5]}{'...' if len(user_image_files) > 5 else ''}")
                    except Exception as e:
                        print(f"📁 【用户图片路径调试】列出用户图片目录文件时出错: {e}")
            
            # 尝试从图片目录获取任意图片
            try:
                print("📁 【默认图片流程】开始尝试获取默认图片...")
                image_dir = get_data_path("input/images")
                print(f"📁 【默认图片流程】图片目录路径: {image_dir}")
                
                if Path(image_dir).exists():
                    print(f"📁 【默认图片流程】图片目录存在，开始搜索图片文件...")
                    image_files = []
                    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        found_files = list(Path(image_dir).glob(f"*{ext}"))
                        found_files_upper = list(Path(image_dir).glob(f"*{ext.upper()}"))
                        print(f"📁 【默认图片流程】扩展名 {ext}: 找到 {len(found_files)} 个文件")
                        print(f"📁 【默认图片流程】扩展名 {ext.upper()}: 找到 {len(found_files_upper)} 个文件")
                        image_files.extend(found_files)
                        image_files.extend(found_files_upper)
                    
                    print(f"📁 【默认图片流程】总共找到 {len(image_files)} 个图片文件")
                    
                    if image_files:
                        default_image = str(image_files[0])
                        print(f"📁 【默认图片流程】使用默认图片: {default_image}")
                        
                        processed_img_path = temp_dir / "processed_image.png"
                        print(f"📁 【默认图片流程】处理图片到: {processed_img_path}")
                        
                        processed_img = process_image_for_overlay(
                            default_image,
                            str(processed_img_path),
                            size=(img_size, img_size)
                        )
                        print(f"📁 【默认图片流程】process_image_for_overlay返回: {processed_img}")
                        
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
                import traceback
                traceback.print_exc()
                has_image = False
        else:
            if not enable_image:
                print("图片功能已禁用")
            has_image = False
        
        # 报告进度：图片处理完成
        if progress_callback:
            progress_callback("图片处理完成", 30.0)
            
        # 6. 处理GIF（仅在启用GIF时）
        has_gif = False
        processed_gif_path = None
        
        if enable_gif and gif_path and Path(gif_path).exists():
            print(f"【GIF流程】处理GIF {gif_path}，缩放系数: {gif_scale}，位置: ({gif_x}, {gif_y})，循环次数: {gif_loop_count}")
            
            # 检查文件格式
            file_ext = Path(gif_path).suffix.lower()
            if file_ext in ['.gif', '.webp']:
                # 使用改进的GIF处理函数，传递视频时长确保GIF持续整个视频时长
                processed_gif_path = process_animated_gif_for_video(gif_path, temp_dir, gif_scale, gif_loop_count, duration, gif_rotation)
                
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
            
        # 报告进度：GIF处理完成
        if progress_callback:
            progress_callback("GIF处理完成", 35.0)
            
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
            print(f"  中文 (chinese) → zn列（字幕标题）")  # 修改为正确的列名
            print(f"  马来语 (malay) → malay_title列（字幕标题）")  # 修改为正确的列名
            print(f"  泰语 (thai) → title_thai列（字幕标题）")  # 修改为正确的列名
            print(f"当前文档可用列: {available_columns}")
            print(f"=========================\n")
            
            # 根据语言随机选择一条字幕
            subtitle_text = None
            
            print(f"可用的文档列: {available_columns}")
            
            if subtitle_lang == "chinese":
                # 中文：明确指定使用zn列（字幕标题文本）
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
                # 马来语：明确指定使用malay_title列（字幕标题文本）
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
                # 泰语：明确指定使用title_thai列（字幕标题文本）
                thai_col = 'title_thai'
                
                if thai_col in available_columns:
                    available_subtitles = subtitle_df[subtitle_df[thai_col].notna() & (subtitle_df[thai_col] != "")][thai_col].tolist()
                    if available_subtitles:
                        subtitle_text = str(random.choice(available_subtitles))
                        # 替换下划线为空格（如果泰文使用下划线占位）
                        if "_" in subtitle_text:
                            subtitle_text = subtitle_text.replace("_", " ")
                        print(f"✅ 泰สั่งซื้อเลยอย่ารอช้า")
                    else:
                        print(f"❌ '{thai_col}' 列中没有有效数据")
                        subtitle_text = "ราคาพิเศษ\nซื้อเลยอย่ารอช้า"  # 泰文示例
                        print("ใช้ข้อความเริ่มต้นภาษาไทย")
                else:
                    print(f"❌ 文档中ไม่มีคอลัมน์ภาษาไทย: {thai_col}")
                    subtitle_text = "ราคาพิเศษ\nซื้อเลยอย่ารอช้า"  # 泰文示例
                    print("ใช้ข้อความเริ่มต้นภาษาไทย")
            
            # 创建字幕图片
            subtitle_height = 500  # 字幕高度
            subtitle_img_path = temp_dir / "subtitle.png"
            
            # 调试信息：打印字体大小
            print(f"ขนาดตัวอักษรที่ส่งไปยัง create_subtitle_image: {font_size}")
            
            # 检查是否使用动态字幕
            if enable_dynamic_subtitle and 'dynamic_processor' in locals():
                print(f"[动态字幕] 使用动态字幕处理器生成字幕")
                try:
                    # 使用动态字幕处理器生成ASS字幕文件
                    subtitle_ass_path = temp_dir / "subtitle.ass"
                    subtitle_file = dynamic_processor.create_dynamic_subtitle(
                        text=subtitle_text,
                        width=subtitle_width,
                        height=subtitle_height,
                        font_size=font_size,
                        output_path=str(subtitle_ass_path)
                    )
                    print(f"[动态字幕] 动态字幕生成成功: {subtitle_file}")
                    # 标记使用ASS字幕
                    use_ass_subtitle = True
                    subtitle_img = subtitle_file
                except Exception as e:
                    print(f"[动态字幕] 动态字幕生成失败: {e}")
                    # 回退到静态字幕
                    subtitle_img = create_subtitle_image(
                        subtitle_text, 
                        style=style, 
                        width=subtitle_width, 
                        height=subtitle_height, 
                        font_size=font_size,
                        output_path=str(subtitle_img_path)
                    )
                    print(f"[动态字幕] 回退到静态字幕: {subtitle_img}")
                    use_ass_subtitle = False
            else:
                # 使用静态字幕
                print(f"[字幕] 使用静态字幕生成")
                subtitle_img = create_subtitle_image(
                    subtitle_text, 
                    style=style, 
                    width=subtitle_width, 
                    height=subtitle_height, 
                    font_size=font_size,
                    output_path=str(subtitle_img_path)
                )
                print(f"[字幕] 静态字幕生成: {subtitle_img}")
                use_ass_subtitle = False
            
            # ใช้พารามิเตอร์ขนาดตัวอักษรที่ส่งมาแทนการกำหนดขนาดตัวอักษรโดยตรง
            # ปรับความกว้างของภาพตัวอักษรให้ตรงกับความกว้างของข้อความตัวอักษร ไม่ใช่ความกว้างของวิดีโอ เพื่อป้องกันการคำนวณตำแหน่งผิดพลาด
            subtitle_img = create_subtitle_image(
                text=subtitle_text,
                style=style,
                width=subtitle_width + 100,  # ใช้ความกว้างของข้อความตัวอักษร+ขอบ แทนความกว้างของวิดีโอ
                height=subtitle_height,
                font_size=font_size,
                output_path=str(subtitle_img_path),
                subtitle_width=subtitle_width  # ส่งพารามิเตอร์ความกว้างของข้อความตัวอักษร
            )
            
            # ตรวจสอบผลการสร้างภาพตัวอักษร
            if subtitle_img:
                print(f"สร้างภาพตัวอักษรสำเร็จ ตำแหน่ง: {subtitle_img}")
            else:
                print("คำเตือน: ไม่สามารถสร้างภาพตัวอักษรได้")
                return None
        else:
            print("ปิดใช้งานฟังก์ชันตัวอักษร ข้ามการสร้างภาพตัวอักษร")
        
        # รายงานความคืบหน้า: ประมวลผลตัวอักษรเสร็จสิ้น
        if progress_callback:
            progress_callback("ประมวลผลตัวอักษรเสร็จสิ้น", 40.0)
            
        # 9. 处理พื้นหลัง (หากเปิดใช้งานพื้นหลัง)
        sample_frame = None
        bg_img = None
        
        if enable_background:
            # ดึงเฟรมวิดีโอเพื่อใช้ในการเลือกสี
            sample_frame_path = temp_dir / "sample_frame.jpg"
            
            # ดึงเฟรมจากจุดกลางของวิดีโอ หรือจุดที่ไม่เกิน 5 วินาที
            middle_time = min(duration / 2, 5.0)  # จุดกลางของวิดีโอ หรือไม่เกิน 5 วินาที
            
            sample_frame_cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-ss', str(middle_time),  # ใช้รูปแบบวินาที แทนรูปแบบชั่วโมง:นาที:วินาที
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
        
        # 报告进度：背景处理完成
        if progress_callback:
            progress_callback("背景处理完成", 45.0)
            
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
            # 确保processed_img_path已定义且文件存在
            if 'processed_img_path' in locals() and processed_img_path and Path(processed_img_path).exists():
                ffmpeg_command.extend(['-i', str(processed_img_path)])
                img_index = input_index
                input_index += 1
                logging.info(f"  📸 添加图片输入: 索引{img_index}, 文件{processed_img_path}")
            else:
                logging.warning(f"  ⚠️ 图片启用但processed_img_path未定义或文件不存在")
                img_index = None
                has_image = False
            
        if enable_gif and has_gif:
            ffmpeg_command.extend(['-i', str(processed_gif_path)])
            gif_index = input_index
            input_index += 1
            logging.info(f"  🎞️ 添加GIF输入: 索引{gif_index}, 文件{processed_gif_path}")
        
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
            
        # 叠加字幕（如果启用）
        if enable_subtitle:
            if use_ass_subtitle and subtitle_ass_path:
                # 使用ASS字幕文件
                # ASS字幕不需要作为输入流，直接在过滤器中使用
                # 确保跨平台路径格式正确
                ass_path_str = str(subtitle_ass_path)
                if os.name == 'nt':  # Windows系统
                    # 将反斜杠替换为正斜杠，保持驱动器字母格式 (C:/path/to/file)
                    ass_path_str = ass_path_str.replace('\\', '/')
                else:
                    # Unix/Linux/macOS系统，确保使用正斜杠
                    ass_path_str = ass_path_str.replace('\\', '/')
                ass_filter = f"[{current_stream}]ass=filename={ass_path_str}[v]"
                filter_complex_parts.append(ass_filter)
                logging.info(f"  📝 添加ASS字幕: {current_stream} -> v")
                logging.info(f"    ASS文件: {subtitle_ass_path}")
                current_stream = "v"
                # stream_index += 1  # 不需要增加，因为直接输出到[v]
            elif subtitle_index is not None:
                # 使用PNG图片字幕（回退模式）
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
                logging.info(f"    随机位置: {random_position}")
                current_stream = f"v{stream_index}"
                stream_index += 1
            else:
                logging.warning(f"  ⚠️ 字幕启用但没有可用的字幕文件")
        
        # 检查是否有任何素材需要处理
        has_any_overlay = (enable_subtitle and subtitle_img) or (enable_background and bg_img) or (enable_image and has_image) or (enable_gif and has_gif)
        
        # 组合过滤器链，并确保最终输出端点正确设置
        if has_any_overlay:
             # 确保最终输出有一个明确的标签[v]
             if current_stream != "v1" and current_stream != "v":
                 # 如果有叠加操作且不是最终输出，将最终流标记为[v]
                 filter_complex_parts.append(f"[{current_stream}]null[v]")
             elif current_stream == "v1":
                 # 如果没有叠加操作，直接将基础视频流标记为[v]
                 filter_complex_parts.append("[v1]null[v]")
             # 如果current_stream已经是"v"，则不需要添加null过滤器
        
        filter_complex = ";".join(filter_complex_parts)
        logging.info(f"  🔗 最终过滤器链: {filter_complex}")
        
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
                logging.info(f"  📸 图片大小: {Path(final_image_path).stat().st_size} 字节")
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
                if music_path is not None:
                    logging.info(f"  🎵 音乐路径存在: {Path(music_path).exists()}")
                else:
                    logging.info(f"  🎵 音乐路径不存在")
                exists = Path(final_image_path).exists()
                if Path(final_image_path).exists():
                    logging.info(f"  📸 图片大小: {Path(final_image_path).stat().st_size} 字节")
                    
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
        
        if enable_music:
            print(f"【音乐处理】开始处理音乐，视频索引: {video_index}")
            print(f"【音乐处理】音乐参数: enable_music={enable_music}, music_path={music_path}, music_mode={music_mode}, music_volume={music_volume}")
            # 如果启用了音乐但没有指定音乐路径，则尝试使用默认音乐目录
            if not music_path:
                # 尝试使用默认音乐目录
                default_music_dir = get_data_path("music")
                if Path(default_music_dir).exists():
                    music_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.flac']
                    music_files = []
                    for ext in music_extensions:
                        music_files.extend(list(Path(default_music_dir).glob(f"*{ext}")))
                        music_files.extend(list(Path(default_music_dir).glob(f"*{ext.upper()}")))
                    
                    if music_files:
                        # 默认使用第一个音乐文件
                        selected_music_path = str(music_files[0])
                        print(f"【音乐处理】使用默认音乐目录中的音乐: {selected_music_path}")
                    else:
                        print(f"【音乐处理】默认音乐目录中没有找到音乐文件: {default_music_dir}")
                        selected_music_path = None
                else:
                    print(f"【音乐处理】默认音乐目录不存在: {default_music_dir}")
                    selected_music_path = None
            else:
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
                    
                    print(f"【音乐处理】在音乐文件夹中找到 {len(music_files)} 个音乐文件")
                    for i, file in enumerate(music_files):
                        print(f"  [{i}] {file.name}")
                    
                    if music_files:
                        print(f"【音乐处理】音乐模式: {music_mode}")
                        if music_mode == "random":
                            selected_music_path = str(random.choice(music_files))
                            print(f"【音乐处理】随机选择音乐: {selected_music_path}")
                        elif music_mode == "sequence":
                            # 顺序模式：直接根据视频索引选择音乐文件
                            # 确保索引不会超出范围
                            music_file_index = video_index % len(music_files)
                            selected_music_path = str(music_files[music_file_index])
                            print(f"【音乐处理】按顺序选择音乐: {selected_music_path} (音乐索引: {music_file_index}/{len(music_files)-1}, 视频索引: {video_index})")
                            
                            # 添加额外的调试信息
                            print(f"【音乐处理】调试信息 - 音乐文件列表:")
                            for idx, music_file in enumerate(music_files):
                                marker = "<<< 选中" if idx == music_file_index else ""
                                print(f"  [{idx}] {music_file.name} {marker}")
                        else:  # single模式，选择第一个
                            selected_music_path = str(music_files[0])
                            print(f"【音乐处理】选择第一个音乐: {selected_music_path}")
                            # 添加调试信息
                            print(f"【音乐处理】调试信息 - 音乐文件列表:")
                            for idx, music_file in enumerate(music_files):
                                marker = "<<< 选中" if idx == 0 else ""
                                print(f"  [{idx}] {music_file.name} {marker}")
                    else:
                        print(f"【音乐处理】音乐文件夹中没有找到音乐文件: {music_path}")
                        selected_music_path = None
                else:
                    print(f"【音乐处理】音乐路径不是有效的文件或文件夹: {music_path}")
                    selected_music_path = None
        else:
            print(f"【音乐处理】音乐功能未启用")

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
        
        # 构建FFmpeg命令
        input_index = 1  # 视频输入为0，从1开始计算其他输入
        
        # 音乐输入
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
            if has_any_overlay:
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
                        '-map', f'{music_index}:a',  # 映射音乐的音频流
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
                    
                    audio_params = [
                        '-map', '0:v',  # 映射视频流
                        '-map', f'{music_input_index}:a',  # 映射音乐的音频流
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-af', f'volume={volume_ratio}',  # 调节音量
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
                if enable_subtitle and subtitle_img:
                    return fallback_static_subtitle(video_path, subtitle_img, output_path, temp_dir, quicktime_compatible, 
                                                   enable_music, selected_music_path, music_volume)
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
                
                copy_with_music_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-i', selected_music_path,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-af', f'volume={volume_ratio}',
                    '-map', '0:v',  # 映射视频流
                    '-map', '1:a',   # 映射音频流，强制映射
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
        
        # 报告进度：视频处理完成
        if progress_callback:
            progress_callback("视频处理完成", 90.0)
            
        # 10. 添加QuickTime兼容性（如果需要）
        if _apply_final_conversion(output_with_subtitle, output_path, progress_callback):
            print(f"成功添加字幕动画，输出到: {output_path}")
            # 报告进度：处理完成
            if progress_callback:
                progress_callback("处理完成", 100.0)
            return output_path
        else:
            print("最终转换失败")
            return None
    
    except FileNotFoundError as e:
        error_msg = f"文件未找到错误: {e}"
        print(error_msg)
        logging.error(error_msg)
        if progress_callback:
            progress_callback(f"错误: {error_msg}", -1)
        return None
    except PermissionError as e:
        error_msg = f"权限错误: {e}"
        print(error_msg)
        logging.error(error_msg)
        if progress_callback:
            progress_callback(f"错误: {error_msg}", -1)
        return None
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg命令执行失败: {e}"
        print(error_msg)
        logging.error(error_msg)
        if progress_callback:
            progress_callback(f"错误: {error_msg}", -1)
        return None
    except Exception as e:
        error_msg = f"添加字幕时出现未知错误: {e}"
        print(error_msg)
        logging.error(error_msg)
        import traceback
        traceback.print_exc()
        if progress_callback:
            progress_callback(f"错误: {error_msg}", -1)
        return None
    finally:
        # 清理临时文件
        try:
            import shutil
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir)
                print(f"已清理临时目录: {temp_dir}")
                logging.info(f"已清理临时目录: {temp_dir}")
        except Exception as cleanup_error:
            print(f"清理临时文件时出错: {cleanup_error}")
            logging.warning(f"清理临时文件时出错: {cleanup_error}")


def fallback_static_subtitle(video_path, subtitle_img_path, output_path, temp_dir, quicktime_compatible=False, 
                           enable_music=False, music_path="", music_volume=50):
    """
    静态字幕备用方案
    当动画字幕失败时使用
    
    参数:
        video_path: 视频路径
        subtitle_img_path: 字幕图片路径
        output_path: 输出路径
        temp_dir: 临时目录
        quicktime_compatible: 是否生成QuickTime兼容的视频
        enable_music: 是否启用背景音乐
        music_path: 音乐文件路径
        music_volume: 音乐音量(0-100)
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
    
    # 处理音频
    if enable_music and music_path and Path(music_path).exists():
        print(f"【fallback音乐处理】添加背景音乐: {music_path}")
        
        # 根据视频时长自动裁剪音乐
        print(f"【fallback音乐处理】开始根据视频时长裁剪音乐")
        print(f"【fallback音乐处理】视频时长: {duration}秒")
        
        # 创建临时裁剪音乐文件路径
        trimmed_music_path = temp_dir / f"fallback_trimmed_music_{uuid.uuid4().hex[:8]}.mp3"
        
        # 调用音乐裁剪函数
        trimmed_result = trim_music_to_video_duration(music_path, duration, trimmed_music_path)
        
        if trimmed_result:
            music_path = trimmed_result
            print(f"【fallback音乐处理】音乐裁剪成功，使用裁剪后的音乐: {music_path}")
        else:
            print(f"【fallback音乐处理】音乐裁剪失败，使用原始音乐文件")
        
        volume_ratio = music_volume / 100.0
        
        # 构建包含音乐的FFmpeg命令
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-i', str(subtitle_img_path),
            '-i', str(music_path),
            '-filter_complex', f'{filter_complex}[v];[2:a]volume={volume_ratio}[a]',
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264',
            '-c:a', 'aac',  # 指定音频编码器
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main', '-level', '3.1',
            '-preset', 'ultrafast',
            '-movflags', '+faststart',
        ]
    else:
        # 不包含音乐的FFmpeg命令 - 保留原视频音频流
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-i', str(subtitle_img_path),
            '-filter_complex', f'{filter_complex}[v]',
            '-map', '[v]',   # 映射处理后的视频流
            '-map', '0:a?',  # 保留原视频音频流（如果存在）
            '-c:v', 'libx264',
            '-c:a', 'copy',  # 复制原音频编码
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main', '-level', '3.1',
            '-preset', 'ultrafast',
            '-movflags', '+faststart',
        ]
    
    # 添加QuickTime兼容性参数
    if quicktime_compatible:
        cmd.extend([
            '-brand', 'mp42',
            '-tag:v', 'avc1',
        ])
        print("应用静态字幕的QuickTime兼容性参数")
    
    # 添加输出文件路径
    cmd.append(str(output_with_subtitle))
    
    if not run_ffmpeg_command(cmd):
        print("静态字幕添加失败")
        return None
    
    # 复制到最终输出路径
    if _apply_final_conversion(output_with_subtitle, output_path):
        print(f"成功添加静态字幕，输出到: {output_path}")
        return output_path
    else:
        print(f"复制最终视频失败，尝试直接复制文件")
        ensure_dir(Path(output_path).parent)
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


def preprocess_video(video_path, temp_dir, duration=None):
    """
    视频预处理函数 - 根据视频时长进行不同的预处理
    
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
    # 使用相对路径的output目录
    output_dir = Path("output")
    
    # 确保目录存在
    if not Path(videos_dir).exists():
        Path(videos_dir).mkdir(parents=True, exist_ok=True)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
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
                         output_path=None, subtitle_width=800):
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
        image_width = min(width, subtitle_width + 100)  # 添加一些边距
        image = Image.new('RGBA', (image_width, height), (0, 0, 0, 0))
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
            # 修改为左对齐，而不是居中对齐
            x = 50  # 固定左边距
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
