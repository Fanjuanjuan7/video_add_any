#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试GIF持续时间问题
"""

import subprocess
from pathlib import Path

def get_gif_info(gif_path):
    """获取GIF文件信息"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(gif_path)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        duration = float(result.stdout.decode().strip())
        print(f"GIF持续时间: {duration} 秒")
        return duration
    except Exception as e:
        print(f"获取GIF信息失败: {e}")
        return None

def create_looping_gif(input_gif, output_gif, target_duration):
    """创建循环播放到指定时长的GIF"""
    # 获取原始GIF的持续时间
    original_duration = get_gif_info(input_gif)
    if original_duration is None:
        return False
    
    # 计算需要循环的次数
    loop_count = int(target_duration / original_duration) + 1
    
    print(f"原始GIF时长: {original_duration}秒")
    print(f"目标时长: {target_duration}秒")
    print(f"需要循环次数: {loop_count}")
    
    # 创建循环播放的GIF
    cmd = [
        'ffmpeg', '-y',
        '-stream_loop', str(loop_count),
        '-i', str(input_gif),
        '-t', str(target_duration),
        '-vf', 'split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128',
        '-loop', '0',
        '-f', 'gif',
        str(output_gif)
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"循环GIF创建成功: {output_gif}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"循环GIF创建失败: {e}")
        print(f"stderr: {e.stderr.decode()}")
        return False

def test_gif_in_video(video_path, gif_path, output_path, x=100, y=100):
    """测试GIF在视频中的表现"""
    # 获取视频时长
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        video_duration = float(result.stdout.decode().strip())
        print(f"视频时长: {video_duration} 秒")
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        return False
    
    # 创建持续整个视频时长的循环GIF
    looping_gif = Path(gif_path).parent / "looping_test.gif"
    if not create_looping_gif(gif_path, looping_gif, video_duration):
        return False
    
    # 将循环GIF叠加到视频
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-i', str(looping_gif),
        '-filter_complex', f'[0:v][1:v]overlay=x={x}:y={y}:shortest=1',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',
        str(output_path)
    ]
    
    print(f"叠加命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"视频合成成功: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"视频合成失败: {e}")
        print(f"stderr: {e.stderr.decode()}")
        return False

if __name__ == "__main__":
    project_dir = Path(__file__).parent
    video_path = project_dir / "video" / "1.mp4"
    gif_path = project_dir / "data" / "gif" / "1.gif"
    output_path = project_dir / "output" / "gif_duration_test.mp4"
    
    # 确保输出目录存在
    output_path.parent.mkdir(exist_ok=True)
    
    print("开始调试GIF持续时间问题...")
    
    # 获取GIF信息
    get_gif_info(gif_path)
    
    # 测试GIF在视频中的表现
    if test_gif_in_video(video_path, gif_path, output_path):
        print("测试完成")
    else:
        print("测试失败")