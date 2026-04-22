# import_medical.py 讲解

## 1. 这个文件是做什么的

`import_medical.py` 的作用是把本地的 `medical.json` 数据导入 MongoDB。

这不是网页爬虫脚本，而是一个“本地数据入库脚本”。

适合下面这种场景：

1. 已经有整理好的 JSON 数据
2. 不想重新爬虫
3. 想快速把数据导入数据库进行测试或演示

---

## 2. 这个文件里用到的库

### `pymongo`

负责连接 MongoDB 并写入数据。

### `bson.json_util`

用于解析 MongoDB 扩展 JSON。  
相比标准 `json`，它对 MongoDB 格式兼容更好。

### `json`

主要用于捕获 JSON 解析异常。

### `os`

用于构造本地文件路径。

---

## 3. 类和函数是做什么的

### 类：`MedicalDataImporter`

负责整个导入过程。

### 类中的函数

#### `__init__()`

完成数据库连接，并确定待导入 JSON 文件路径。

#### `import_data()`

逐行读取 `medical.json`，并写入 MongoDB。

---

## 4. 按代码顺序讲解

```python
import pymongo
from bson import json_util
import json
import os
```

导入程序所需的库。

```python
class MedicalDataImporter:
```

定义导入类。

```python
    def __init__(self):
```

定义初始化函数。

```python
        try:
            self.client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
            self.client.admin.command("ping")
            print("成功连接到MongoDB")
```

这几行做了三件事：

1. 创建 MongoDB 客户端
2. 用 `ping` 测试连接
3. 输出连接成功信息

```python
            self.db = self.client["medical_1"]
            self.collection = self.db["medical_1"]
```

指定数据库和集合。  
这里数据库名和集合名都叫 `medical_1`。

```python
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            self.json_path = os.path.join(cur_dir, "..", "data", "medical.json")
```

获取当前脚本目录，并拼出待导入文件的路径。

```python
            print(f"准备导入数据文件：{self.json_path}")
```

输出文件路径，方便确认。

```python
        except Exception as e:
            print(f"MongoDB连接失败：{e}")
            raise
```

如果 MongoDB 连接失败，就打印错误并抛出异常。

### `import_data()`

```python
    def import_data(self):
```

定义导入主函数。

```python
        try:
```

开始异常处理。

```python
            if not os.path.exists(self.json_path):
                print(f"错误：文件 {self.json_path} 不存在")
                return
```

先检查 JSON 文件是否存在，如果不存在就结束。

```python
            self.collection.delete_many({})
            print("已清空medical集合中的现有数据")
```

导入前先清空当前集合。  
这一行适合课程演示，但实际生产环境中要特别谨慎，因为它会删除已有数据。

```python
            with open(self.json_path, "r", encoding="utf-8") as f:
```

以 UTF-8 编码方式打开 JSON 文件。

```python
                line_count = 0
                success_count = 0
```

初始化统计变量：

1. 总处理行数
2. 成功导入条数

```python
                for line in f:
                    line_count += 1
                    line = line.strip()
                    if not line:
                        continue
```

逐行读取文件，并跳过空行。

```python
                    try:
                        data = json_util.loads(line)
```

把当前这一行 JSON 文本解析成 Python 对象。

```python
                        self.collection.insert_one(data)
                        success_count += 1
```

将解析后的数据写入 MongoDB，并更新成功计数。

```python
                        if success_count % 100 == 0:
                            print(f"已导入 {success_count} 条数据...")
```

每导入 100 条数据就打印一次进度。

```python
                    except json.JSONDecodeError as e:
                        print(f"第 {line_count} 行JSON解析错误：{e}")
                    except Exception as e:
                        print(f"第 {line_count} 行导入失败：{e}")
```

这里区分了两类异常：

1. JSON 格式错误
2. 其他导入异常，比如数据库写入失败

```python
            print(f"数据导入完成！")
            print(f"总处理行数：{line_count}")
            print(f"成功导入：{success_count} 条")
            print(f"失败条数：{line_count - success_count} 条")
```

导入完成后输出统计信息。

```python
        except Exception as e:
            print(f"数据导入过程中发生错误：{e}")
            raise
```

如果整个导入过程出现严重异常，就打印并抛出。

```python
        finally:
            self.client.close()
            print("已关闭MongoDB连接")
```

最后关闭 MongoDB 连接。

### 文件结尾

```python
if __name__ == "__main__":
    print("开始导入medical.json到MongoDB...")
    print("=" * 50)

    importer = MedicalDataImporter()
    importer.import_data()

    print("=" * 50)
    print("导入任务完成！")
```

这部分表示脚本的执行入口：

1. 打印开始提示
2. 创建导入对象
3. 调用导入函数
4. 打印结束提示

---

## 5. 课堂总结

你可以这样总结这个文件：

`import_medical.py` 不是采集程序，而是一个本地 JSON 数据入库工具。它的核心思想是逐行读取文件，然后逐条写入 MongoDB。

讲课时建议重点强调：

1. `json_util` 为什么比普通 `json` 更适合 MongoDB
2. 为什么很多数据导入脚本都采用“逐行读取”的方式
3. `delete_many({})` 这种操作为什么需要格外谨慎
