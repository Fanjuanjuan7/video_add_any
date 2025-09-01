#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复GIF循环播放问题的脚本
"""

import subprocess
from pathlib import Path

def fix_gif_looping():
    """修复GIF循环播放问题"""
    # 获取项目路径
    project_dir = Path(__file__).parent
    gif_dir = project_dir / "data" / "gif"
    
    if not gif_dir.exists():
        print(f"GIF目录不存在: {gif_dir}")
        return False
    
    # 处理目录中的所有GIF文件
    gif_files = list(gif_dir.glob("*.gif"))
    
    print(f"找到 {len(gif_files)} 个GIF文件")
    
    for gif_path in gif_files:
        print(f"\n处理GIF文件: {gif_path.name}")
        
        # 创建处理后的GIF路径
        processed_gif_path = gif_path.parent / f"fixed_{gif_path.name}"
        
        # 使用FFmpeg处理GIF，确保循环播放
        # 使用更完整的GIF处理命令，确保循环和透明度
        gif_cmd = [
            'ffmpeg', '-y',
            '-i', str(gif_path),
            '-vf', 'split[a][b];[a]palettegen=reserve_transparent=on:transparency_color=ffffff[p];[b][p]paletteuse=alpha_threshold=128',
            '-loop', '0',  # 0 表示无限循环
            '-f', 'gif',
            str(processed_gif_path)
        ]
        
        print(f"执行命令: {' '.join(gif_cmd)}")
        
        try:
            result = subprocess.run(gif_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"GIF处理成功: {processed_gif_path}")
            
            # 验证处理后的文件
            if processed_gif_path.exists():
                print(f"处理后文件大小: {processed_gif_path.stat().st_size} 字节")
            else:
                print("处理后的文件未创建")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"GIF处理失败: {e}")
            print(f"stderr: {e.stderr.decode()}")
            return False
    
    print("\n所有GIF文件处理完成")
    return True

def test_gif_in_video():
    """测试GIF在视频中的循环播放"""
    project_dir = Path(__file__).parent
    test_gif_path = project_dir / "data" / "gif" / "1.gif"
    fixed_gif_path = project_dir / "data" / "gif" / "fixed_1.gif"
    
    if not fixed_gif_path.exists():
        print(f"修复后的GIF文件不存在: {fixed_gif_path}")
        return False
    
    # 创建测试视频的命令
    temp_dir = Path(__file__).parent / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # 创建一个简单的测试视频（纯色背景）
    test_video_path = temp_dir / "test_video.mp4"
    output_video_path = temp_dir / "output_with_gif.mp4"
    
    # 创建测试视频
    create_video_cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', 'color=c=blue:s=1280x720:d=10',  # 10秒蓝色背景视频
        '-c:v', 'libx264',
        '-t', '10',
        str(test_video_path)
    ]
    
    print(f"创建测试视频: {' '.join(create_video_cmd)}")
    
    try:
        subprocess.run(create_video_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"测试视频创建成功: {test_video_path}")
    except subprocess.CalledProcessError as e:
        print(f"测试视频创建失败: {e}")
        return False
    
    # 将GIF叠加到视频上
    overlay_cmd = [
        'ffmpeg', '-y',
        '-i', str(test_video_path),
        '-i', str(fixed_gif_path),
        '-filter_complex', '[0:v][1:v]overlay=100:100',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        str(output_video_path)
    ]
    
    print(f"叠加GIF到视频: {' '.join(overlay_cmd)}")
    
    try:
        subprocess.run(overlay_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"GIF叠加成功: {output_video_path}")
        print(f"输出视频大小: {output_video_path.stat().st_size} 字节")
        return True
    except subprocess.CalledProcessError as e:
        print(f"GIF叠加失败: {e}")
        print(f"stderr: {e.stderr.decode()}")
        return False
    finally:
        # 清理临时文件
        try:
            test_video_path.unlink()
            output_video_path.unlink()
            temp_dir.rmdir()
        except:
            pass

if __name__ == "__main__":
    print("开始修复GIF循环播放问题...")
    
    # 修复GIF循环
    if fix_gif_looping():
        print("\nGIF循环修复完成")
        
        # 测试GIF在视频中的表现
        print("\n开始测试GIF在视频中的循环播放...")
        if test_gif_in_video():
            print("GIF循环播放测试成功")
        else:
            print("GIF循环播放测试失败")
    else:
        print("GIF循环修复失败")