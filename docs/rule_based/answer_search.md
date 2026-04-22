# answer_search.py 讲解

当前代码位置：

```text
rule_based/answer_search.py
```

`AnswerSearcher` 负责执行 `QuestionPaser` 生成的 Cypher 查询，并把 Neo4j 返回的结构化结果整理成用户能读懂的自然语言答案。

它的核心作用是：

```text
输入 Cypher 查询列表
  -> 连接 Neo4j
  -> 执行查询
  -> 收集查询结果
  -> 根据 question_type 套用回答模板
  -> 输出最终答案文本
```

例如输入：

```python
[
    {
        "question_type": "disease_check",
        "sql": [
            "MATCH (m:Disease)-[r:need_check]->(n:Check) where m.name = '脑膜炎' return m.name, r.name, n.name"
        ]
    }
]
```

会输出类似：

```text
脑膜炎通常可以通过以下方式检查出来：脑脊液检查；尿常规；脑脊液细菌培养
```

## 1. 整体定位

在规则版问答系统中，完整链路是：

```text
用户问题
  -> QuestionClassifier 识别实体和问题类型
  -> QuestionPaser 生成 Cypher 查询
  -> AnswerSearcher 查询 Neo4j 并生成回答
```

`AnswerSearcher` 是规则版链路的最后一层。

它不负责问题分类，也不负责生成 Cypher。它只负责：

```text
执行查询 + 整理答案
```

## 2. 初始化 Neo4j 连接

初始化代码：

```python
from py2neo import Graph

class AnswerSearcher:
    def __init__(self):
        self.g = Graph("bolt://127.0.0.1:7687", auth=("neo4j", "12341234"))
        self.num_limit = 20
```

这里使用 `py2neo.Graph` 连接 Neo4j：

```text
地址：bolt://127.0.0.1:7687
用户名：neo4j
密码：12341234
```

如果你的 Neo4j 密码不是 `12341234`，需要修改这里。

`self.num_limit = 20` 表示每类答案最多返回 20 个结果，避免输出过长。

## 3. search_main 的主流程

核心方法：

```python
def search_main(self, sqls):
```

输入是 `QuestionPaser.parser_main()` 返回的查询列表。

处理流程：

```text
1. 遍历每个 question_type 对应的查询块
2. 取出 question_type
3. 取出 sql 列表
4. 逐条执行 Cypher
5. 合并 Neo4j 返回结果
6. 调用 answer_prettify() 生成自然语言答案
7. 收集所有最终答案
```

对应代码：

```python
final_answers = []
for sql_ in sqls:
    question_type = sql_['question_type']
    queries = sql_['sql']
    answers = []
    for query in queries:
        ress = self.g.run(query).data()
        answers += ress
    final_answer = self.answer_prettify(question_type, answers)
    if final_answer:
        final_answers.append(final_answer)
return final_answers
```

这里的关键是：

```python
self.g.run(query).data()
```

它会执行 Cypher，并把结果转成 Python 字典列表。

## 4. answers 的数据结构

假设执行的是：

```cypher
MATCH (m:Disease)-[r:has_symptom]->(n:Symptom)
where m.name = '乳腺癌'
return m.name, r.name, n.name
```

Neo4j 返回后，`answers` 可能类似：

```python
[
    {"m.name": "乳腺癌", "r.name": "症状", "n.name": "乳房肿块"},
    {"m.name": "乳腺癌", "r.name": "症状", "n.name": "胸痛"}
]
```

所以 `answer_prettify()` 会根据字段名取值：

```python
desc = [i['n.name'] for i in answers]
subject = answers[0]['m.name']
```

最后组织成：

```text
乳腺癌的症状包括：乳房肿块；胸痛
```

## 5. answer_prettify 的作用

核心方法：

```python
def answer_prettify(self, question_type, answers):
```

它根据不同的 `question_type` 使用不同的回答模板。

如果查询结果为空，直接返回空字符串：

```python
if not answers:
    return ''
```

这意味着：

```text
没有图谱结果 -> 不生成答案
```

最后由 `chatbot_graph.py` 统一返回兜底话术。

## 6. 常见回答模板

### 6.1 疾病查症状

代码：

```python
if question_type == 'disease_symptom':
    desc = [i['n.name'] for i in answers]
    subject = answers[0]['m.name']
    final_answer = '{0}的症状包括：{1}'.format(
        subject,
        '；'.join(list(set(desc))[:self.num_limit])
    )
```

输入问题：

```text
乳腺癌的症状有哪些？
```

输出类似：

```text
乳腺癌的症状包括：乳房肿块；胸痛；乳头溢液
```

### 6.2 症状反查疾病

代码：

```python
elif question_type == 'symptom_disease':
    desc = [i['m.name'] for i in answers]
    subject = answers[0]['n.name']
    final_answer = '症状{0}可能染上的疾病有：{1}'.format(
        subject,
        '；'.join(list(set(desc))[:self.num_limit])
    )
```

输入问题：

```text
流鼻涕可能是什么病？
```

输出类似：

```text
症状流鼻涕可能染上的疾病有：感冒；慢性鼻炎；急性上呼吸道感染
```

### 6.3 疾病查原因

代码：

```python
elif question_type == 'disease_cause':
    desc = [i['m.cause'] for i in answers]
    subject = answers[0]['m.name']
    final_answer = '{0}可能的成因有：{1}'.format(
        subject,
        '；'.join(list(set(desc))[:self.num_limit])
    )
```

这类答案来自 `Disease` 节点属性，不是关系节点。

### 6.4 疾病查饮食

忌口食物：

```python
elif question_type == 'disease_not_food':
    desc = [i['n.name'] for i in answers]
    subject = answers[0]['m.name']
    final_answer = '{0}忌食的食物包括有：{1}'.format(
        subject,
        '；'.join(list(set(desc))[:self.num_limit])
    )
```

宜食和推荐食谱：

```python
elif question_type == 'disease_do_food':
    do_desc = [i['n.name'] for i in answers if i['r.name'] == '宜吃']
    recommand_desc = [i['n.name'] for i in answers if i['r.name'] == '推荐食谱']
    subject = answers[0]['m.name']
```

这里会根据关系上的 `r.name` 区分：

```text
宜吃
推荐食谱
```

### 6.5 疾病查药品

代码：

```python
elif question_type == 'disease_drug':
    desc = [i['n.name'] for i in answers]
    subject = answers[0]['m.name']
    final_answer = '{0}通常的使用的药品包括：{1}'.format(
        subject,
        '；'.join(list(set(desc))[:self.num_limit])
    )
```

这里的 `answers` 可能来自两条关系：

```text
common_drug
recommand_drug
```

但模板会统一合并成药品列表。

## 7. 去重和限制数量

多数模板都有类似逻辑：

```python
list(set(desc))[:self.num_limit]
```

它做两件事：

```text
1. set(desc)：去重
2. [:self.num_limit]：最多保留 20 个
```

这样可以避免重复答案，也避免一次输出过多内容。

需要注意的是，`set` 会打乱原始顺序，所以每次答案顺序可能不完全一致。

## 8. 一个完整例子

输入 `search_main()` 的 SQL：

```python
[
    {
        "question_type": "disease_drug",
        "sql": [
            "MATCH (m:Disease)-[r:common_drug]->(n:Drug) where m.name = '感冒' return m.name, r.name, n.name",
            "MATCH (m:Disease)-[r:recommand_drug]->(n:Drug) where m.name = '感冒' return m.name, r.name, n.name"
        ]
    }
]
```

第一步，执行两条查询：

```python
ress = self.g.run(query).data()
answers += ress
```

第二步，合并结果：

```python
answers = [
    {"m.name": "感冒", "r.name": "常用药品", "n.name": "板蓝根颗粒"},
    {"m.name": "感冒", "r.name": "好评药品", "n.name": "感冒灵颗粒"}
]
```

第三步，调用：

```python
self.answer_prettify("disease_drug", answers)
```

第四步，生成答案：

```text
感冒通常的使用的药品包括：板蓝根颗粒；感冒灵颗粒
```

## 9. 这个模块的特点

优点：

```text
查询执行逻辑简单
模板固定，输出稳定
方便针对 question_type debug
和 QuestionPaser 的返回结构匹配清楚
```

缺点：

```text
回答模板比较硬
不同 question_type 都要手写格式化逻辑
set 去重会导致顺序不稳定
不能根据上下文生成更自然的回答
数据库连接参数写死在代码里
```

## 10. 和 LLM 分支的关系

`AnswerSearcher` 是规则版链路的一部分。

规则版答案生成方式是：

```text
Neo4j 查询结果 -> 固定模板回答
```

LLM 分支不复用这个模块。LLM 分支使用：

```text
GraphClient 查询 Neo4j
AnswerGenerator 基于图谱结果生成自然语言回答
```

两者都坚持同一个原则：

```text
答案事实来源必须来自 Neo4j 图谱
```

区别是：

```text
rule_based：模板组织答案
llm_based：LLM 基于图谱结果组织答案
```

## 11. 总结

`AnswerSearcher` 的作用可以概括为：

```text
执行 QuestionPaser 生成的 Cypher，并把 Neo4j 的结构化结果包装成自然语言答案
```

它是规则版问答系统的最后一层，也是用户最终看到答案之前的最后一个处理模块。
