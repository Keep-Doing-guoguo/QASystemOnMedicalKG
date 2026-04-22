# build_data.py 讲解

## 1. 这个文件是做什么的

`build_data.py` 的作用是把爬虫抓到的原始数据进一步清洗、规范化，并构造成知识图谱后续可使用的结构化数据。

它的主要工作包括：

1. 从 MongoDB 读取爬虫抓到的原始疾病数据
2. 过滤脏数据
3. 统一字段名
4. 将检查项 URL 转成检查项名称
5. 将结果重新写回数据库

简单理解就是：  
`data_spider.py` 负责“抓数据”，`build_data.py` 负责“整理数据”。

---

## 2. 这个文件里用到的库

### `pymongo`

负责连接 MongoDB，读取和写入数据。

### `lxml.etree`

负责解析检查项 HTML。

### `os`

用于处理文件路径，比如读取 `first_name.txt`。

### `re`

用于处理字符串切分，比如拆分并发症字段。

---

## 3. 类和函数是做什么的

### 类：`MedicalGraph`

这个类负责数据构建的整个过程。

### 类中的函数

#### `__init__()`

完成初始化配置，包括数据库连接、停用词加载、字段映射表构建。

#### `collect_medical()`

这是核心函数，用来整理疾病数据。

#### `get_inspect(url)`

根据检查项 URL，去数据库中找到检查项名称。

#### `modify_jc()`

解析检查项网页源码，为检查项补充名称和简介。

---

## 4. 按代码顺序讲解

```python
import pymongo
from lxml import etree
import os
import re
```

导入程序所需的库。

```python
class MedicalGraph:
```

定义一个类，负责医疗数据的结构化整理。

```python
    def __init__(self):
```

初始化函数，在对象创建时自动执行。

```python
        self.conn = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
```

连接本地 MongoDB。

```python
        cur_dir = '/'.join(os.path.abspath(__file__).split('/')[:-1])
```

获取当前脚本所在目录。

```python
        self.db = self.conn['medical']
        self.col = self.db['data']
```

指定数据库 `medical` 和原始数据集合 `data`。

```python
        first_name_path = os.path.join(cur_dir, 'first_name.txt')
        first_words = []
```

确定 `first_name.txt` 路径，并初始化停用词列表。

```python
        if os.path.exists(first_name_path):
            first_words = [i.strip() for i in open(first_name_path, encoding='utf-8') if i.strip()]
```

如果文件存在，就逐行读入停用词。

```python
        alphabets = ['a','b','c',...,'z']
        nums = ['1','2','3',...,'0']
```

这里作者手工定义了字母和数字列表。  
目的是把无意义的单字符过滤掉，避免它们被误当作实体。

```python
        self.stop_words = first_words + alphabets + nums
```

把姓名停用词、字母、数字合并起来，形成统一的停用词集合。

```python
        self.key_dict = {
            '医保疾病' : 'yibao_status',
            ...
            '并发症': 'acompany'
        }
```

这个映射表非常关键。  
它的作用是把中文字段名统一转换成英文键名，方便后续程序处理和图谱构建。

### `collect_medical()`

```python
    def collect_medical(self):
```

定义核心整理函数。

```python
        cates = []
        inspects = []
        count = 0
```

初始化分类列表、检查项列表和计数器。

```python
        for item in self.col.find():
```

遍历 MongoDB 中 `data` 集合的所有原始疾病文档。

```python
            data = {}
            basic_info = item['basic_info']
            name = basic_info['name']
            if not name:
                continue
```

取出疾病基础信息，如果没有疾病名称就跳过。

```python
            data['名称'] = name
```

保存疾病名称。

```python
            data['简介'] = '\n'.join(basic_info['desc']).replace('\r\n\t', '').replace('\r\n\n\n','').replace(' ','').replace('\r\n','\n')
```

把简介列表拼成字符串，并清理掉多余空白和换行。

```python
            category = basic_info['category']
            data['所属类别'] = category
            cates += category
```

保存所属类别，并把类别加入统计列表。

```python
            inspect = item['inspect_info']
            inspects += inspect
```

收集检查项链接。

```python
            attributes = basic_info['attributes']
```

读取原始属性字段。

```python
            data['预防措施'] = item['prevent_info']
            data['成因'] = item['cause_info']
```

直接写入预防措施和成因。

```python
            data['症状'] = list(set([i for i in item["symptom_info"][0] if i[0] not in self.stop_words]))
```

这一行在做症状清洗：

1. 取出症状列表
2. 用停用词过滤
3. 用 `set` 去重
4. 再转回列表

这里可以提醒学生，这里的判断条件是 `i[0]`，也就是只看词的第一个字符，过滤逻辑并不算特别严谨。

```python
            for attr in attributes:
                attr_pair = attr.split('：')
                if len(attr_pair) == 2:
                    key = attr_pair[0]
                    value = attr_pair[1]
                    data[key] = value
```

这一段是在把文本属性解析成键值对。  
例如：

```text
治疗周期：2-4周
治愈率：80%
```

会被拆成：

- `治疗周期`
- `2-4周`

### 处理检查项

```python
            inspects = item['inspect_info']
            jcs = []
            for inspect in inspects:
                jc_name = self.get_inspect(inspect)
                if jc_name:
                    jcs.append(jc_name)
            data['检查'] = jcs
```

这里做的是“检查项名称恢复”：

1. 原始数据里保存的是检查项链接
2. 调用 `get_inspect()` 去 `jc` 集合里查
3. 查出真实检查项名称
4. 最终保存到 `data['检查']`

### 处理食物信息

```python
            food_info = item['food_info']
            if food_info:
                data['宜食'] = food_info['good']
                data['忌食'] = food_info['bad']
                data['推荐'] = food_info['recommand']
```

如果有饮食信息，就分别取出宜食、忌食和推荐食谱。

### 处理药品信息

```python
            drug_info = item['drug_info']
            data['药品推荐'] = list(set([i.split('(')[-1].replace(')','') for i in drug_info]))
            data['药品明细'] = drug_info
```

这里做了两件事：

1. 保存药品完整列表
2. 对药品名称做一次规范化提取，生成推荐药品列表

### 字段统一映射

```python
            data_modify = {}
            for attr, value in data.items():
                attr_en = self.key_dict.get(attr)
                if attr_en:
                    data_modify[attr_en] = value
```

把中文字段名映射成英文键名。

```python
                if attr_en in ['yibao_status', 'get_prob', 'easy_get', 'get_way', "cure_lasttime", "cured_prob"]:
                    data_modify[attr_en] = value.replace(' ','').replace('\t','')
```

对部分字段做格式清洗。

```python
                elif attr_en in ['cure_department', 'cure_way', 'common_drug']:
                    data_modify[attr_en] = [i for i in value.split(' ') if i]
```

对需要拆分成列表的字段按空格切分。

```python
                elif attr_en in ['acompany']:
```

处理并发症字段。

```python
                    if isinstance(value, list):
                        data_modify[attr_en] = [i for i in value if i]
```

如果原始值已经是列表，就过滤空值。

```python
                    elif isinstance(value, str):
                        parts = re.split(r'[，,、;；\s]+', value)
                        data_modify[attr_en] = [i for i in parts if i and len(i) > 1]
```

如果是字符串，就使用正则表达式按中文逗号、英文逗号、顿号、分号、空白符拆分。

```python
                    else:
                        data_modify[attr_en] = []
```

如果既不是字符串也不是列表，就给空列表。

### 写回数据库

```python
            try:
                self.db['medical'].insert_one(data_modify)
                count += 1
                print(count)
```

把整理后的结构化数据插入 `medical` 集合，并打印计数。

```python
            except Exception as e:
                print(e)
```

如果写入失败，就打印错误。

### `get_inspect(url)`

```python
    def get_inspect(self, url):
        res = self.db['jc'].find_one({'url':url})
        if not res:
            return ''
        else:
            return res['name']
```

这个函数的逻辑很直接：

1. 根据 URL 去 `jc` 集合查找记录
2. 找不到就返回空字符串
3. 找到了就返回检查项名称

### `modify_jc()`

```python
    def modify_jc(self):
```

这个函数负责补充检查项结构化信息。

```python
        for item in self.db['jc'].find():
```

遍历 `jc` 集合中所有检查项页面。

```python
            url = item['url']
            content = item['html']
            selector = etree.HTML(content)
```

取出 URL 和 HTML，并解析 HTML。

```python
            name = selector.xpath('//title/text()')[0].split('结果分析')[0]
```

从网页标题中提取检查项名称。

```python
            desc = selector.xpath('//meta[@name="description"]/@content')[0].replace('\r\n\t','')
```

从网页 `meta description` 中提取检查项简介。

```python
            self.db['jc'].update_one({'url':url}, {'$set':{'name':name, 'desc':desc}})
```

把名称和简介更新到数据库。

### 文件结尾

```python
if __name__ == '__main__':
    handler = MedicalGraph()
    #handler.modify_jc()
    handler.collect_medical()
```

默认执行 `collect_medical()`，也就是整理疾病数据。  
如果要先补充检查项名称和简介，可以打开 `modify_jc()`。

---

## 5. 课堂总结

你可以这样总结这个文件：

`build_data.py` 是整个数据处理链路中的“清洗和标准化模块”。它把爬虫抓到的原始数据转换成统一字段、统一格式的结构化结果。

上课时建议强调这三点：

1. 爬虫抓到的数据通常还不能直接用
2. 字段统一映射是知识图谱构建前的重要步骤
3. 结构化数据构建本质上是在做“数据标准化”
