#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码检查工具 - 检测项目中的重复代码、逻辑冲突、无用代码等问题
"""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter
import re


class CodeChecker:
    """代码检查器类"""
    
    def __init__(self, project_root="."):
        """初始化代码检查器"""
        self.project_root = Path(project_root)
        self.issues = []
        self.file_stats = {}
        # 忽略的目录
        self.ignore_dirs = {'venv', '__pycache__', '.git', 'backups', 'logs'}
        
    def check_project(self):
        """检查整个项目"""
        print("🔍 开始检查项目代码...")
        
        # 查找所有Python文件（排除忽略的目录）
        python_files = []
        for py_file in self.project_root.rglob("*.py"):
            # 检查是否在忽略目录中
            if not any(ignore_dir in str(py_file) for ignore_dir in self.ignore_dirs):
                python_files.append(py_file)
        
        print(f"找到 {len(python_files)} 个Python文件")
        
        # 检查每个文件
        for file_path in python_files:
            self.check_file(file_path)
        
        # 生成报告
        self.generate_report()
        
    def check_file(self, file_path):
        """检查单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 文件统计信息
            lines = content.split('\n')
            self.file_stats[str(file_path)] = {
                'lines': len(lines),
                'functions': 0,
                'classes': 0
            }
            
            # 解析AST
            tree = ast.parse(content)
            
            # 检查各种问题
            self.check_duplicate_code(file_path, content)
            self.check_unused_code(file_path, tree)
            self.check_logic_conflicts(file_path, tree)
            self.check_duplicate_functions(file_path, tree)
            self.check_complex_functions(file_path, tree)
            self.check_naming_conventions(file_path, tree)
            
        except Exception as e:
            self.issues.append({
                'type': 'parse_error',
                'file': str(file_path),
                'line': 0,
                'message': f'无法解析文件: {e}'
            })
    
    def check_duplicate_code(self, file_path, content):
        """检查重复代码块"""
        lines = content.split('\n')
        # 检查连续相同的行（至少3行）
        for i in range(len(lines) - 2):
            if (lines[i].strip() and 
                lines[i].strip() == lines[i+1].strip() == lines[i+2].strip()):
                self.issues.append({
                    'type': 'duplicate_code',
                    'file': str(file_path),
                    'line': i + 1,
                    'message': f'发现连续重复的代码行: {lines[i].strip()}'
                })
    
    def check_unused_code(self, file_path, tree):
        """检查无用代码"""
        # 检查未使用的导入
        imports = set()
        used_names = set()
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                else:  # ImportFrom
                    for alias in node.names:
                        imports.add(alias.name)
            elif isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # 检查属性访问，如 pd.read_csv
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
        
        # 检查未使用的导入
        for imp in imports:
            if imp not in used_names and not imp.startswith('_'):
                # 忽略一些常见的内置导入
                if imp not in {'sys', 'os', 'pathlib', 'time', 'random', 'json', 'subprocess', 'shutil'}:
                    self.issues.append({
                        'type': 'unused_import',
                        'file': str(file_path),
                        'line': node.lineno if 'node' in locals() and hasattr(node, 'lineno') else 0,
                        'message': f'未使用的导入: {imp}'
                    })
    
    def check_logic_conflicts(self, file_path, tree):
        """检查逻辑冲突"""
        for node in ast.walk(tree):
            # 检查恒真/恒假条件
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Constant):
                    if isinstance(node.test.value, bool):
                        self.issues.append({
                            'type': 'logic_conflict',
                            'file': str(file_path),
                            'line': node.lineno,
                            'message': f'恒{"真" if node.test.value else "假"}条件: {ast.dump(node.test)}'
                        })
            
            # 检查空的if/else块
            if isinstance(node, ast.If):
                if (isinstance(node.body, list) and len(node.body) == 0) or \
                   (isinstance(node.orelse, list) and len(node.orelse) == 0 and node.orelse):
                    self.issues.append({
                        'type': 'empty_block',
                        'file': str(file_path),
                        'line': node.lineno,
                        'message': '发现空的if/else块'
                    })
    
    def check_duplicate_functions(self, file_path, tree):
        """检查重复函数"""
        functions = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 获取函数体的字符串表示（简化版）
                func_name = node.name
                
                # 计算函数体的简单哈希
                func_lines = []
                for child in ast.iter_child_nodes(node):
                    func_lines.append(ast.dump(child))
                
                func_body_hash = hash(''.join(func_lines))
                
                if func_name in functions and functions[func_name] == func_body_hash:
                    self.issues.append({
                        'type': 'duplicate_function',
                        'file': str(file_path),
                        'line': node.lineno,
                        'message': f'发现重复函数定义: {func_name}'
                    })
                else:
                    functions[func_name] = func_body_hash
    
    def check_complex_functions(self, file_path, tree):
        """检查复杂函数"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 计算函数复杂度（基于分支数量）
                complexity = 1  # 基础复杂度
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)):
                        complexity += 1
                
                # 也计算函数长度
                func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
                
                if complexity > 15 or func_lines > 100:  # 复杂度阈值或行数阈值
                    self.issues.append({
                        'type': 'complex_function',
                        'file': str(file_path),
                        'line': node.lineno,
                        'message': f'函数 {node.name} 复杂度过高: 复杂度={complexity}, 行数={func_lines}'
                    })
    
    def check_naming_conventions(self, file_path, tree):
        """检查命名规范"""
        for node in ast.walk(tree):
            # 检查函数命名（应该使用下划线命名法）
            if isinstance(node, ast.FunctionDef):
                if not self.is_snake_case(node.name) and not node.name.startswith('__'):
                    self.issues.append({
                        'type': 'naming_convention',
                        'file': str(file_path),
                        'line': node.lineno,
                        'message': f'函数命名不规范: {node.name} (建议使用下划线命名法)'
                    })
            
            # 检查变量命名
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if not self.is_snake_case(node.id) and not node.id.isupper() and not node.id.startswith('_'):
                    # 忽略一些特殊情况
                    if node.id not in {'Qt', 'QApplication', 'QWidget', 'QMainWindow'}:
                        self.issues.append({
                            'type': 'naming_convention',
                            'file': str(file_path),
                            'line': node.lineno,
                            'message': f'变量命名不规范: {node.id} (建议使用下划线命名法)'
                        })
    
    def is_snake_case(self, name):
        """检查是否为下划线命名法"""
        return re.match(r'^[a-z_][a-z0-9_]*$', name) is not None
    
    def generate_report(self):
        """生成检查报告"""
        print("\n" + "="*60)
        print("📊 代码检查报告")
        print("="*60)
        
        if not self.issues:
            print("✅ 未发现明显问题！")
            return
        
        # 按类型分类问题
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            issues_by_type[issue['type']].append(issue)
        
        # 输出各类问题
        for issue_type, issues in issues_by_type.items():
            print(f"\n🔴 {self.get_issue_type_name(issue_type)} ({len(issues)} 个)")
            print("-" * 40)
            
            # 按文件分组
            issues_by_file = defaultdict(list)
            for issue in issues:
                issues_by_file[issue['file']].append(issue)
            
            for file_path, file_issues in issues_by_file.items():
                print(f"  📄 {Path(file_path).name}:")
                for issue in file_issues:
                    line_info = f"第{issue['line']}行: " if issue['line'] > 0 else ""
                    print(f"    {line_info}{issue['message']}")
        
        # 输出统计信息
        print(f"\n📈 统计信息:")
        print(f"  - 总共发现 {len(self.issues)} 个问题")
        print(f"  - 涉及 {len(set(issue['file'] for issue in self.issues))} 个文件")
        
        # 按类型统计
        type_counts = Counter(issue['type'] for issue in self.issues)
        print(f"  - 问题类型分布:")
        for issue_type, count in type_counts.items():
            print(f"    * {self.get_issue_type_name(issue_type)}: {count} 个")
        
        # 输出建议
        print(f"\n💡 优化建议:")
        if type_counts['unused_import']:
            print(f"  - 清理未使用的导入语句，减少不必要的依赖")
        if type_counts['complex_function']:
            print(f"  - 考虑将复杂函数拆分为多个小函数，提高代码可读性")
        if type_counts['duplicate_code']:
            print(f"  - 消除重复代码，提高代码维护性")
        if type_counts['naming_convention']:
            print(f"  - 统一命名规范，提高代码一致性")
    
    def get_issue_type_name(self, issue_type):
        """获取问题类型的中文名称"""
        names = {
            'duplicate_code': '重复代码',
            'unused_import': '未使用导入',
            'logic_conflict': '逻辑冲突',
            'empty_block': '空代码块',
            'duplicate_function': '重复函数',
            'complex_function': '复杂函数',
            'parse_error': '解析错误',
            'naming_convention': '命名规范问题'
        }
        return names.get(issue_type, issue_type)


def main():
    """主函数"""
    print("🔍 VideoApp 代码检查工具")
    print("="*40)
    
    # 创建检查器并运行检查
    checker = CodeChecker(".")
    checker.check_project()


if __name__ == "__main__":
    main()