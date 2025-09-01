#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份管理器 - 提供代码版本备份和恢复功能
"""

import os
import shutil
import time
import json
from pathlib import Path
import zipfile


class BackupManager:
    """代码备份管理器类"""
    
    def __init__(self, app_root=None):
        """初始化备份管理器"""
        if app_root is None:
            self.app_root = Path(__file__).parent
        else:
            self.app_root = Path(app_root)
        
        # 创建备份目录
        self.backup_dir = self.app_root / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # 备份记录文件
        self.backup_record = self.backup_dir / "backup_records.json"
        self.records = self._load_records()
        
    def _load_records(self):
        """加载备份记录"""
        if not self.backup_record.exists():
            return []
        
        try:
            with open(self.backup_record, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载备份记录失败: {e}")
            return []
    
    def _save_records(self):
        """保存备份记录"""
        try:
            with open(self.backup_record, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存备份记录失败: {e}")
    
    def create_backup(self, description=""):
        """
        创建代码备份
        
        参数:
            description: 备份描述
        
        返回:
            备份ID
        """
        # 生成备份ID和时间戳
        timestamp = int(time.time())
        backup_id = f"backup_{timestamp}"
        date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        
        # 创建备份文件
        backup_file = self.backup_dir / f"{backup_id}.zip"
        
        # 要备份的文件类型
        file_types = ['.py', '.json', '.csv', '.txt']
        
        # 要排除的目录
        exclude_dirs = ['__pycache__', 'backups', 'data/input', 'data/output']
        
        try:
            # 创建ZIP文件
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.app_root):
                    # 排除不需要备份的目录
                    root_path = Path(root)
                    rel_path = root_path.relative_to(self.app_root)
                    if any(exclude_dir in str(rel_path).split(os.sep) for exclude_dir in exclude_dirs):
                        continue
                    
                    # 添加文件到ZIP
                    for file in files:
                        if any(file.endswith(ext) for ext in file_types):
                            file_path = root_path / file
                            arc_name = file_path.relative_to(self.app_root)
                            zipf.write(str(file_path), str(arc_name))
            
            # 记录备份信息
            backup_info = {
                "id": backup_id,
                "timestamp": timestamp,
                "date": date_str,
                "description": description,
                "file": str(backup_file.name)
            }
            
            self.records.append(backup_info)
            self._save_records()
            
            print(f"备份创建成功: {date_str} - {description}")
            return backup_id
            
        except Exception as e:
            print(f"创建备份失败: {e}")
            if backup_file.exists():
                backup_file.unlink()
            return None
    
    def list_backups(self):
        """
        列出所有备份
        
        返回:
            备份列表
        """
        return self.records
    
    def restore_backup(self, backup_id):
        """
        恢复指定备份
        
        参数:
            backup_id: 备份ID
            
        返回:
            是否成功
        """
        # 查找备份记录
        backup_info = None
        for record in self.records:
            if record["id"] == backup_id:
                backup_info = record
                break
        
        if not backup_info:
            print(f"找不到备份: {backup_id}")
            return False
        
        # 备份文件路径
        backup_file = self.backup_dir / backup_info["file"]
        if not backup_file.exists():
            print(f"备份文件不存在: {backup_file}")
            return False
        
        try:
            # 先创建当前状态的临时备份
            temp_backup_id = self.create_backup("恢复前的自动备份")
            
            # 清理要恢复的文件
            for root, dirs, files in os.walk(self.app_root):
                # 排除不需要清理的目录
                root_path = Path(root)
                rel_path = root_path.relative_to(self.app_root)
                if str(rel_path) == "." or str(rel_path).startswith("backups") or \
                   str(rel_path).startswith("data/input") or str(rel_path).startswith("data/output"):
                    continue
                
                # 清理Python文件
                for file in files:
                    if file.endswith('.py'):
                        file_path = root_path / file
                        file_path.unlink()
            
            # 解压备份文件
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(self.app_root)
            
            print(f"成功恢复备份: {backup_info['date']} - {backup_info['description']}")
            print(f"恢复前的状态已保存为: {temp_backup_id}")
            return True
            
        except Exception as e:
            print(f"恢复备份失败: {e}")
            return False
    
    def delete_backup(self, backup_id):
        """
        删除指定备份
        
        参数:
            backup_id: 备份ID
            
        返回:
            是否成功
        """
        # 查找备份记录
        backup_info = None
        index = -1
        for i, record in enumerate(self.records):
            if record["id"] == backup_id:
                backup_info = record
                index = i
                break
        
        if not backup_info:
            print(f"找不到备份: {backup_id}")
            return False
        
        # 备份文件路径
        backup_file = self.backup_dir / backup_info["file"]
        
        try:
            # 删除备份文件
            if backup_file.exists():
                backup_file.unlink()
            
            # 删除记录
            self.records.pop(index)
            self._save_records()
            
            print(f"成功删除备份: {backup_info['date']} - {backup_info['description']}")
            return True
            
        except Exception as e:
            print(f"删除备份失败: {e}")
            return False


# 命令行工具
def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="代码备份管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 创建备份
    create_parser = subparsers.add_parser("create", help="创建备份")
    create_parser.add_argument("-d", "--description", default="", help="备份描述")
    
    # 列出备份
    subparsers.add_parser("list", help="列出所有备份")
    
    # 恢复备份
    restore_parser = subparsers.add_parser("restore", help="恢复备份")
    restore_parser.add_argument("backup_id", help="备份ID")
    
    # 删除备份
    delete_parser = subparsers.add_parser("delete", help="删除备份")
    delete_parser.add_argument("backup_id", help="备份ID")
    
    args = parser.parse_args()
    
    # 创建备份管理器
    manager = BackupManager()
    
    if args.command == "create":
        manager.create_backup(args.description)
    elif args.command == "list":
        backups = manager.list_backups()
        if not backups:
            print("没有找到备份")
        else:
            print("备份列表:")
            for backup in backups:
                print(f"{backup['id']} - {backup['date']} - {backup['description']}")
    elif args.command == "restore":
        manager.restore_backup(args.backup_id)
    elif args.command == "delete":
        manager.delete_backup(args.backup_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 