#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理主协调模块
负责协调调用各个功能模块来完成视频处理任务
"""

import os
import sys
from pathlib import Path
import tempfile
import shutil
import random

# 导入工具函数
from utils import get_video_info, get_audio_duration, run_ffmpeg_command, get_data_path, ensure_dir

# 导入各功能模块
from video_background import create_rounded_rect_background, process_image_for_overlay, create_subtitle_image
from video_audio import trim_music_to_video_duration, add_tts_audio_to_video, generate_subtitle_tts
from video_preprocessing import preprocess_video_by_type
from video_subtitle_processor import VideoSubtitleProcessor

# 导入日志管理器
from log_manager import init_logging, log_with_capture

# 初始化日志系统
log_manager = init_logging()

# 创建全局字幕处理器实例
_subtitle_processor = VideoSubtitleProcessor()


@log_with_capture
def process_video(video_path, output_path=None, style=None, subtitle_lang=None, 
                 quicktime_compatible=False, img_position_x=100, img_position_y=0,
                 font_size=70, subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                 subtitle_text_x=0, subtitle_text_y=1190, random_position=False, enable_subtitle=True,
                 enable_background=True, enable_image=True, enable_music=False, music_path="",
                 music_mode="single", music_volume=50, document_path=None, enable_gif=False, 
                 gif_path="", gif_loop_count=-1, gif_scale=1.0, gif_rotation=0, gif_x=800, gif_y=100, scale_factor=1.1, 
                 image_path=None, subtitle_width=500, quality_settings=None, progress_callback=None,
                 video_index=0, enable_tts=False, tts_voice="zh-CN-XiaoxiaoNeural", 
                 tts_volume=100, tts_text="", auto_match_duration=False,
                 enable_dynamic_subtitle=False, animation_style="高亮放大", animation_intensity=1.5, highlight_color="#FFD700",
                 match_mode="随机样式", position_x=540, position_y=960):
    """
    处理视频的主函数（精处理阶段）
    
    参数:
        video_path: 视频文件路径（已经过预处理的视频）
        output_path: 输出文件路径，默认为None（自动生成）
        style: 字幕样式，如果为None则随机选择
        subtitle_lang: 字幕语言，如果为None则随机选择
        quicktime_compatible: 是否生成QuickTime兼容的视频
        img_position_x: 图片水平位置系数（视频宽度的百分比，默认0.15，即15%）
        img_position_y: 图垂直位置偏移（相对于背景位置，默认120像素向下偏移）
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
        
        # 对视频进行预处理（水印处理、正放倒放等）
        print(f"对视频进行预处理...")
        processed_path = preprocess_video_by_type(video_path, temp_dir, duration)
        
        if not processed_path:
            print("视频预处理失败")
            return None
            
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
        
        # 使用新的VideoSubtitleProcessor类
        final_path = _subtitle_processor.add_subtitle_to_video(
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
        # 清理临时文件，添加异常处理以避免清理失败影响主流程
        try:
            if 'temp_dir' in locals() and temp_dir.exists():
                shutil.rmtree(temp_dir)
                print(f"已清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"清理临时目录失败: {e}")
            # 不抛出异常，避免影响主流程
            pass


def batch_process_videos(style=None, subtitle_lang=None, quicktime_compatible=False, 
                         img_position_x=100, img_position_y=0, font_size=70, 
                         subtitle_x=-50, subtitle_y=1100, bg_width=1000, bg_height=180, img_size=420,
                         subtitle_text_x=0, subtitle_text_y=1190, enable_subtitle=True):
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
        enable_subtitle: 是否启用字幕
        
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
    print(f"字幕启用状态: {enable_subtitle}")
    
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
                subtitle_text_y=subtitle_text_y,
                enable_subtitle=enable_subtitle
            ):
                success_count += 1
                print(f"✅ 视频处理成功: {video_path.name}")
            else:
                print(f"❌ 视频处理失败: {video_path.name}")
        except Exception as e:
            print(f"❌ 处理视频时出错: {e}")
    
    print(f"\n批量处理完成: {success_count}/{len(video_files)} 个视频成功")
    return success_count


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