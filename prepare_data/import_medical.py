#!/usr/bin/env python3
# coding: utf-8
# File: import_medical.py
# Purpose: Import medical.json to MongoDB

import pymongo
from bson import json_util
import json
import os

class MedicalDataImporter:
    def __init__(self):
        # 连接MongoDB
        try:
            self.client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
            self.client.admin.command("ping")  # 测试连接
            print("成功连接到MongoDB")
            
            # 获取数据库和集合
            self.db = self.client["medical_1"]
            self.collection = self.db["medical_1"]
            
            # 获取JSON文件路径
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            self.json_path = os.path.join(cur_dir, "..", "data", "medical.json")
            
            print(f"准备导入数据文件：{self.json_path}")
            
        except Exception as e:
            print(f"MongoDB连接失败：{e}")
            raise
    
    def import_data(self):
        """导入medical.json数据到MongoDB"""
        try:
            # 检查JSON文件是否存在
            if not os.path.exists(self.json_path):
                print(f"错误：文件 {self.json_path} 不存在")
                return
            
            # 清空现有集合（可选）
            self.collection.delete_many({})
            print("已清空medical集合中的现有数据")
            
            # 导入数据
            with open(self.json_path, "r", encoding="utf-8") as f:
                line_count = 0
                success_count = 0
                
                for line in f:
                    line_count += 1
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        # 解析JSON行（支持MongoDB扩展JSON格式）
                        data = json_util.loads(line)
                        
                        # 插入到MongoDB
                        self.collection.insert_one(data)
                        success_count += 1
                        
                        # 显示进度
                        if success_count % 100 == 0:
                            print(f"已导入 {success_count} 条数据...")
                            
                    except json.JSONDecodeError as e:
                        print(f"第 {line_count} 行JSON解析错误：{e}")
                    except Exception as e:
                        print(f"第 {line_count} 行导入失败：{e}")
            
            print(f"数据导入完成！")
            print(f"总处理行数：{line_count}")
            print(f"成功导入：{success_count} 条")
            print(f"失败条数：{line_count - success_count} 条")
            
        except Exception as e:
            print(f"数据导入过程中发生错误：{e}")
            raise
        finally:
            # 关闭数据库连接
            self.client.close()
            print("已关闭MongoDB连接")

if __name__ == "__main__":
    print("开始导入medical.json到MongoDB...")
    print("=" * 50)
    
    importer = MedicalDataImporter()
    importer.import_data()
    
    print("=" * 50)
    print("导入任务完成！")
