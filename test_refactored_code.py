#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的视频字幕处理代码
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 导入重构后的模块
from video_subtitle_processor import VideoSubtitleProcessor


def test_video_subtitle_processor():
    """测试VideoSubtitleProcessor类的基本功能"""
    print("开始测试VideoSubtitleProcessor类...")
    
    # 创建处理器实例
    processor = VideoSubtitleProcessor()
    
    # 检查类是否存在
    assert processor is not None, "无法创建VideoSubtitleProcessor实例"
    print("✓ 成功创建VideoSubtitleProcessor实例")
    
    # 检查主要方法是否存在
    assert hasattr(processor, 'add_subtitle_to_video'), "缺少add_subtitle_to_video方法"
    assert hasattr(processor, '_initialize_params'), "缺少_initialize_params方法"
    assert hasattr(processor, '_get_video_info'), "缺少_get_video_info方法"
    assert hasattr(processor, '_load_subtitle_config'), "缺少_load_subtitle_config方法"
    assert hasattr(processor, '_process_dynamic_subtitle'), "缺少_process_dynamic_subtitle方法"
    assert hasattr(processor, '_process_random_position'), "缺少_process_random_position方法"
    assert hasattr(processor, '_process_image'), "缺少_process_image方法"
    assert hasattr(processor, '_process_gif'), "缺少_process_gif方法"
    assert hasattr(processor, '_process_animated_gif_for_video'), "缺少_process_animated_gif_for_video方法"
    assert hasattr(processor, '_process_subtitle_materials'), "缺少_process_subtitle_materials方法"
    assert hasattr(processor, '_process_music'), "缺少_process_music方法"
    assert hasattr(processor, '_process_with_ffmpeg'), "缺少_process_with_ffmpeg方法"
    
    print("✓ 所有预期方法都存在")
    
    # 测试兼容性函数
    # from video_subtitle import add_subtitle_to_video
    # assert callable(add_subtitle_to_video), "兼容性函数add_subtitle_to_video不可调用"
    # print("✓ 兼容性函数add_subtitle_to_video可用")
    
    # 测试新的VideoSubtitleProcessor类
    # processor已经在函数开始时创建了
    assert callable(processor.add_subtitle_to_video), "VideoSubtitleProcessor.add_subtitle_to_video不可调用"
    print("✓ VideoSubtitleProcessor.add_subtitle_to_video可用")
    
    print("所有测试通过！")


if __name__ == "__main__":
    test_video_subtitle_processor()