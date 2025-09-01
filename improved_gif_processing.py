#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的GIF处理模块
"""

import subprocess
from pathlib import Path

def process_animated_gif(gif_path, output_path, scale_factor=1.0, loop_count=-1):
    """
    处理动画GIF以确保在视频中正确播放
    
    参数:
        gif_path: 原始GIF文件路径
        output_path: 处理后的GIF文件路径
        scale_factor: 缩放因子
        loop_count: 循环次数 (-1表示无限循环)
        
    返回:
        成功返回True，失败返回False
    """
    if not Path(gif_path).exists():
        print(f"GIF文件不存在: {gif_path}")
        return False
    
    # 构建FFmpeg命令来处理GIF
    gif_cmd = [
        'ffmpeg', '-y',
        '-i', str(gif_path)
    ]
    
    # 添加缩放过滤器（如果需要）
    filters = []
    if scale_factor != 1.0:
        filters.append(f"scale=iw*{scale_factor}:ih*{scale_factor}")
    
    # 添加GIF处理过滤器
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
        str(output_path)
    ])
    
    print(f"处理GIF命令: {' '.join(gif_cmd)}")
    
    try:
        result = subprocess.run(gif_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"GIF处理成功: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"GIF处理失败: {e}")
        print(f"stderr: {e.stderr.decode()}")
        return False

def create_video_with_animated_gif(video_path, gif_path, output_path, x=0, y=0):
    """
    创建包含动画GIF的视频
    
    参数:
        video_path: 输入视频路径
        gif_path: GIF文件路径
        output_path: 输出视频路径
        x, y: GIF在视频中的位置
        
    返回:
        成功返回True，失败返回False
    """
    if not Path(video_path).exists():
        print(f"视频文件不存在: {video_path}")
        return False
        
    if not Path(gif_path).exists():
        print(f"GIF文件不存在: {gif_path}")
        return False
    
    # 构建FFmpeg命令来叠加动画GIF到视频
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-i', str(gif_path),
        '-filter_complex', f'[0:v][1:v]overlay={x}:{y}:shortest=0',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',
        str(output_path)
    ]
    
    print(f"叠加GIF到视频命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"视频合成成功: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"视频合成失败: {e}")
        print(f"stderr: {e.stderr.decode()}")
        return False

def test_gif_processing():
    """测试GIF处理功能"""
    project_dir = Path(__file__).parent
    gif_path = project_dir / "data" / "gif" / "1.gif"
    processed_gif_path = project_dir / "data" / "gif" / "processed_test.gif"
    test_video_path = project_dir / "video" / "1.mp4"
    output_video_path = project_dir / "output" / "test_with_gif.mp4"
    
    # 确保输出目录存在
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("开始测试GIF处理...")
    
    # 处理GIF
    if process_animated_gif(gif_path, processed_gif_path, scale_factor=0.5, loop_count=-1):
        print("GIF处理测试通过")
        
        # 测试将GIF叠加到视频
        if test_video_path.exists():
            if create_video_with_animated_gif(test_video_path, processed_gif_path, output_video_path, x=100, y=100):
                print("视频合成测试通过")
                print(f"输出视频: {output_video_path}")
                return True
            else:
                print("视频合成测试失败")
                return False
        else:
            print(f"测试视频不存在: {test_video_path}")
            return False
    else:
        print("GIF处理测试失败")
        return False

if __name__ == "__main__":
    test_gif_processing()