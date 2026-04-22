# 算法说明与示例

本项目是典型的“规则 + 词典”驱动。核心逻辑简单但实用，主要包含：

1. Aho-Corasick 多关键词匹配（实体抽取）
2. 基于词典的最大匹配分词（CutWords）
3. 基于触发词 + 实体类型的意图分类
4. 固定 Cypher 模板查询图谱

下面给出简要说明与示例。

## 1) Aho-Corasick（AC 自动机）

用途：
在问题中高效匹配大量实体词（一次扫描，匹配多个关键词）。

示例关键词：
- "糖尿病"
- "2型糖尿病"
- "心绞痛"

问题：
```
2型糖尿病患者常见并发症有哪些
```

AC 匹配结果：
- "2型糖尿病"
- "糖尿病"

代码位置：`question_classifier.py`  
流程是：
- 把所有词典词构建成 AC 自动机
- 用 `actree.iter(question)` 一次性找出命中词

## 2) CutWords（最大匹配分词）

用途：
把一段文本切分成词，优先匹配更长的词条。

示例词典：
- "心脏病"
- "冠心病"
- "心"

文本：
```
冠心病患者
```

最大匹配结果：
- "冠心病"
- "患者"

代码位置：`prepare_data/max_cut.py`  
流程是：
- 加载 `dict/disease.txt`
- 使用最大匹配规则进行切分

## 3) 规则式意图分类

用途：
根据“触发词 + 实体类型”判断问题类型。

示例：
```
感冒有哪些症状
```

实体：`感冒` -> disease  
触发词：`症状`  
意图：`disease_symptom`

代码位置：`question_classifier.py`  
流程是：
- `check_medical()` 抽实体
- `classify()` 根据触发词决定意图

## 4) Cypher 模板查询

用途：
把意图类型转成固定的图查询语句。

示例意图：
`disease_symptom`

模板（简化）：
```
MATCH (d:Disease {name: $name})-[:has_symptom]->(s:Symptom)
RETURN s.name
```

代码位置：`question_parser.py`（生成查询）  
执行位置：`answer_search.py`

