#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复video_subtitle_processor.py中的语法错误
"""

import re
from pathlib import Path

def fix_syntax_error():
    """修复语法错误"""
    file_path = Path("video_subtitle_processor.py")
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找错误的代码段
    # 匹配return dynamic_processor后面一直到下一个elif/else/return语句的部分
    pattern = r'(return dynamic_processor\s*\n)(\s*# 1920高度.*?)(\s*return subtitle_text_x, subtitle_text_y)'
    
    # 替换错误的代码段
    fixed_content = re.sub(pattern, r'\1', content, flags=re.DOTALL)
    
    # 写入修复后的内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("语法错误修复完成")

if __name__ == "__main__":
    fix_syntax_error()