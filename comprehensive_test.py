#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试重构后的视频字幕处理代码
"""

import os
import sys
from pathlib import Path
import tempfile
import shutil

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 导入重构后的模块
from video_subtitle_processor import VideoSubtitleProcessor


def test_video_subtitle_processor_comprehensive():
    """全面测试VideoSubtitleProcessor类的功能"""
    print("开始全面测试VideoSubtitleProcessor类...")
    
    # 创建处理器实例
    processor = VideoSubtitleProcessor()
    
    # 检查类是否存在
    assert processor is not None, "无法创建VideoSubtitleProcessor实例"
    print("✓ 成功创建VideoSubtitleProcessor实例")
    
    # 检查主要方法是否存在
    methods_to_check = [
        'add_subtitle_to_video',
        '_initialize_params',
        '_get_video_info',
        '_load_subtitle_config',
        '_process_dynamic_subtitle',
        '_process_random_position',
        '_process_image',
        '_process_gif',
        '_process_animated_gif_for_video',
        '_process_subtitle_materials',
        '_process_music',
        '_process_with_ffmpeg'
    ]
    
    for method_name in methods_to_check:
        assert hasattr(processor, method_name), f"缺少{method_name}方法"
        print(f"✓ {method_name}方法存在")
    
    print("✓ 所有预期方法都存在")
    
    # 测试兼容性函数
    # from video_subtitle import add_subtitle_to_video
    # assert callable(add_subtitle_to_video), "兼容性函数add_subtitle_to_video不可调用"
    # print("✓ 兼容性函数add_subtitle_to_video可用")
    
    # 测试新的VideoSubtitleProcessor类
    # processor已经在函数开始时创建了
    assert callable(processor.add_subtitle_to_video), "VideoSubtitleProcessor.add_subtitle_to_video不可调用"
    print("✓ VideoSubtitleProcessor.add_subtitle_to_video可用")
    
    # 创建一个临时视频文件用于测试
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # 创建一个简单的测试视频文件
        test_video_path = temp_dir / "test_video.mp4"
        test_output_path = temp_dir / "output_video.mp4"
        
        # 创建一个简单的测试文件（实际视频处理需要真实的视频文件）
        with open(test_video_path, 'w') as f:
            f.write("This is a test video file content")
        
        print(f"✓ 创建测试文件: {test_video_path}")
        
        # 测试参数初始化方法
        params = processor._initialize_params(
            video_path=str(test_video_path),
            output_path=str(test_output_path),
            style=None,
            subtitle_lang="chinese",
            original_video_path=None,
            quicktime_compatible=False,
            img_position_x=100,
            img_position_y=0,
            font_size=70,
            subtitle_x=-50,
            subtitle_y=1100,
            bg_width=1000,
            bg_height=180,
            img_size=420,
            subtitle_text_x=0,
            subtitle_text_y=1190,
            random_position=False,
            enable_subtitle=True,
            enable_background=True,
            enable_image=True,
            enable_music=False,
            music_path="",
            music_mode="single",
            music_volume=50,
            document_path=None,
            enable_gif=False,
            gif_path="",
            gif_loop_count=-1,
            gif_scale=1.0,
            gif_rotation=0,
            gif_x=800,
            gif_y=100,
            scale_factor=1.1,
            image_path=None,
            subtitle_width=500,
            quality_settings=None,
            progress_callback=None,
            video_index=0,
            enable_dynamic_subtitle=False,
            animation_style="高亮放大",
            animation_intensity=1.5,
            highlight_color="#FFD700",
            match_mode="随机样式",
            position_x=540,
            position_y=960
        )
        
        assert isinstance(params, dict), "参数初始化应返回字典"
        print("✓ 参数初始化方法工作正常")
        
        # 测试随机位置处理
        new_x, new_y = processor._process_random_position(
            random_position=False,
            subtitle_x=-50,
            subtitle_y=1100,
            subtitle_text_x=0,
            subtitle_text_y=1190,
            subtitle_width=500,
            width=1080,
            height=1920,
            enable_subtitle=True
        )
        
        # 当random_position为False时，应该返回原始位置
        assert new_x == 0 and new_y == 1190, "随机位置处理不正确"
        print("✓ 随机位置处理方法工作正常")
        
        print("所有综合测试通过！")
        
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"✓ 清理临时目录: {temp_dir}")


if __name__ == "__main__":
    test_video_subtitle_processor_comprehensive()