# question_parser.py 讲解

当前代码位置：

```text
rule_based/question_parser.py
```

`QuestionPaser` 负责把 `QuestionClassifier` 的分类结果转换成 Neo4j 可以执行的 Cypher 查询语句。

注意：代码里的类名是 `QuestionPaser`，少了一个 `r`。正常英文拼写应该是 `QuestionParser`，但项目中保持了原写法。

它的核心作用是：

```text
输入分类结果
  -> 按实体类型重新组织实体
  -> 根据 question_type 选择查询模板
  -> 把实体填入 Cypher
  -> 输出待执行的 Cypher 列表
```

例如输入：

```python
{
    "args": {
        "高血压": ["disease"]
    },
    "question_types": ["disease_not_food"]
}
```

会生成：

```python
[
    {
        "question_type": "disease_not_food",
        "sql": [
            "MATCH (m:Disease)-[r:no_eat]->(n:Food) where m.name = '高血压' return m.name, r.name, n.name"
        ]
    }
]
```

## 1. 整体定位

在规则版问答系统中，完整链路是：

```text
用户问题
  -> QuestionClassifier 识别实体和问题类型
  -> QuestionPaser 生成 Cypher 查询
  -> AnswerSearcher 查询 Neo4j 并生成回答
```

`QuestionPaser` 位于中间层。它不负责理解自然语言，也不负责访问数据库，只负责：

```text
把已经识别好的 question_type 转换为图数据库查询语句
```

## 2. 输入数据结构

`parser_main()` 的输入来自 `QuestionClassifier.classify()`。

标准格式如下：

```python
{
    "args": {
        "感冒": ["disease"]
    },
    "question_types": ["disease_drug"]
}
```

其中：

| 字段 | 含义 |
| --- | --- |
| `args` | 问句中识别出的实体以及实体类型 |
| `question_types` | 问题类型列表 |

为什么 `question_types` 是列表？因为一个问题可能同时命中多个意图。

例如：

```text
高血压有什么症状，怎么治疗？
```

可能得到：

```python
["disease_symptom", "disease_cureway"]
```

所以 `QuestionPaser` 需要循环处理每一个 `question_type`。

## 3. build_entitydict 的作用

代码：

```python
def build_entitydict(self, args):
    entity_dict = {}
    for arg, types in args.items():
        for type in types:
            if type not in entity_dict:
                entity_dict[type] = [arg]
            else:
                entity_dict[type].append(arg)

    return entity_dict
```

`QuestionClassifier` 输出的是：

```python
{
    "高血压": ["disease"],
    "板蓝根颗粒": ["drug"]
}
```

但生成 Cypher 时，更方便按类型取实体。

所以 `build_entitydict()` 会把它转换成：

```python
{
    "disease": ["高血压"],
    "drug": ["板蓝根颗粒"]
}
```

这一步的目的可以理解为：

```text
从“实体 -> 类型”
转换为“类型 -> 实体”
```

## 4. parser_main 的主流程

核心方法是：

```python
def parser_main(self, res_classify):
```

它的处理流程是：

```text
1. 取出 args
2. 调用 build_entitydict() 重组实体
3. 取出 question_types
4. 遍历每一个 question_type
5. 根据 question_type 选择对应实体类型
6. 调用 sql_transfer() 生成 Cypher
7. 组装为统一格式返回
```

关键代码：

```python
args = res_classify['args']
entity_dict = self.build_entitydict(args)
question_types = res_classify['question_types']
sqls = []
```

然后遍历问题类型：

```python
for question_type in question_types:
    sql_ = {}
    sql_['question_type'] = question_type
    sql = []
```

不同问题类型会取不同实体。

例如疾病查症状：

```python
if question_type == 'disease_symptom':
    sql = self.sql_transfer(question_type, entity_dict.get('disease'))
```

症状反查疾病：

```python
elif question_type == 'symptom_disease':
    sql = self.sql_transfer(question_type, entity_dict.get('symptom'))
```

药品反查疾病：

```python
elif question_type == 'drug_disease':
    sql = self.sql_transfer(question_type, entity_dict.get('drug'))
```

检查项目反查疾病：

```python
elif question_type == 'check_disease':
    sql = self.sql_transfer(question_type, entity_dict.get('check'))
```

所以 `parser_main()` 主要做的是：

```text
根据 question_type 决定应该使用哪一种实体类型来生成查询
```

## 5. sql_transfer 的作用

真正生成 Cypher 的函数是：

```python
def sql_transfer(self, question_type, entities):
```

如果没有实体，直接返回空列表：

```python
if not entities:
    return []
```

如果有实体，就根据 `question_type` 套用固定的 Cypher 模板。

例如疾病原因：

```python
if question_type == 'disease_cause':
    sql = [
        "MATCH (m:Disease) where m.name = '{0}' return m.name, m.cause".format(i)
        for i in entities
    ]
```

如果实体是：

```python
["高血压"]
```

生成：

```cypher
MATCH (m:Disease) where m.name = '高血压' return m.name, m.cause
```

## 6. 属性查询和关系查询

`QuestionPaser` 生成的 Cypher 可以分为两类。

### 6.1 属性查询

属性查询只查某个 `Disease` 节点上的属性。

例如：

```python
disease_cause -> m.cause
disease_prevent -> m.prevent
disease_lasttime -> m.cure_lasttime
disease_cureprob -> m.cured_prob
disease_cureway -> m.cure_way
disease_easyget -> m.easy_get
disease_desc -> m.desc
```

对应 Cypher 形式：

```cypher
MATCH (m:Disease)
where m.name = '高血压'
return m.name, m.cause
```

这类查询不涉及其他节点，只读取疾病节点自身的属性。

### 6.2 关系查询

关系查询会沿着图谱中的边查另一个节点。

例如疾病查症状：

```python
elif question_type == 'disease_symptom':
    sql = [
        "MATCH (m:Disease)-[r:has_symptom]->(n:Symptom) where m.name = '{0}' return m.name, r.name, n.name".format(i)
        for i in entities
    ]
```

对应图谱结构：

```text
Disease - has_symptom -> Symptom
```

再比如疾病查药品：

```python
elif question_type == 'disease_drug':
    sql1 = ["MATCH (m:Disease)-[r:common_drug]->(n:Drug) where m.name = '{0}' return m.name, r.name, n.name".format(i) for i in entities]
    sql2 = ["MATCH (m:Disease)-[r:recommand_drug]->(n:Drug) where m.name = '{0}' return m.name, r.name, n.name".format(i) for i in entities]
    sql = sql1 + sql2
```

这里一个问题类型对应两类关系：

```text
Disease - common_drug -> Drug
Disease - recommand_drug -> Drug
```

## 7. 正向查询和反向查询

有些问题是从疾病出发查其他实体，这是正向查询。

例如：

```text
感冒要吃什么药？
```

生成：

```cypher
MATCH (m:Disease)-[r:common_drug]->(n:Drug)
where m.name = '感冒'
return m.name, r.name, n.name
```

有些问题是从药品、食物、检查项目反查疾病，这是反向查询。

例如：

```text
板蓝根颗粒能治什么病？
```

生成：

```cypher
MATCH (m:Disease)-[r:common_drug]->(n:Drug)
where n.name = '板蓝根颗粒'
return m.name, r.name, n.name
```

注意关系方向没有变，仍然是：

```text
Disease -> Drug
```

只是查询条件从 `m.name` 换成了 `n.name`。

## 8. question_type 到 Cypher 的映射

常见映射如下：

| question_type | 使用实体 | 查询内容 |
| --- | --- | --- |
| `disease_symptom` | `disease` | `Disease - has_symptom -> Symptom` |
| `symptom_disease` | `symptom` | 从 `Symptom` 反查 `Disease` |
| `disease_cause` | `disease` | `Disease.cause` |
| `disease_acompany` | `disease` | `Disease - acompany_with -> Disease`，正反两个方向都查 |
| `disease_not_food` | `disease` | `Disease - no_eat -> Food` |
| `disease_do_food` | `disease` | `Disease - do_eat/recommand_eat -> Food` |
| `food_not_disease` | `food` | 从 `Food` 反查忌食疾病 |
| `food_do_disease` | `food` | 从 `Food` 反查宜食疾病 |
| `disease_drug` | `disease` | `Disease - common_drug/recommand_drug -> Drug` |
| `drug_disease` | `drug` | 从 `Drug` 反查疾病 |
| `disease_check` | `disease` | `Disease - need_check -> Check` |
| `check_disease` | `check` | 从 `Check` 反查疾病 |
| `disease_prevent` | `disease` | `Disease.prevent` |
| `disease_lasttime` | `disease` | `Disease.cure_lasttime` |
| `disease_cureway` | `disease` | `Disease.cure_way` |
| `disease_cureprob` | `disease` | `Disease.cured_prob` |
| `disease_easyget` | `disease` | `Disease.easy_get` |
| `disease_desc` | `disease` | `Disease.desc` |

## 9. 一个完整例子

分类器输入：

```python
{
    "args": {
        "感冒": ["disease"]
    },
    "question_types": ["disease_drug"]
}
```

第一步，重组实体：

```python
entity_dict = {
    "disease": ["感冒"]
}
```

第二步，识别问题类型：

```python
question_type = "disease_drug"
```

第三步，调用：

```python
self.sql_transfer(question_type, entity_dict.get('disease'))
```

第四步，生成两条 Cypher：

```cypher
MATCH (m:Disease)-[r:common_drug]->(n:Drug)
where m.name = '感冒'
return m.name, r.name, n.name
```

```cypher
MATCH (m:Disease)-[r:recommand_drug]->(n:Drug)
where m.name = '感冒'
return m.name, r.name, n.name
```

第五步，最终返回：

```python
[
    {
        "question_type": "disease_drug",
        "sql": [
            "...common_drug...",
            "...recommand_drug..."
        ]
    }
]
```

## 10. 这个模块的特点

优点：

```text
逻辑直观
查询模板固定
方便 debug
生成结果可控
和图谱 schema 对应清楚
```

缺点：

```text
每个 question_type 都要手写模板
Cypher 使用字符串拼接，可维护性一般
扩展新问题类型时需要同时改分类器和解析器
对复杂组合查询支持有限
```

## 11. 和 LLM 分支的关系

`QuestionPaser` 是规则版链路的一部分。

规则版链路是：

```text
QuestionClassifier -> QuestionPaser -> AnswerSearcher
```

LLM 分支不复用这个模块。LLM 分支使用的是：

```text
IntentPlanner -> CypherBuilder -> GraphClient
```

两者都查询同一个 Neo4j 图谱，但查询生成方式不同：

```text
rule_based：question_type 固定映射 Cypher
llm_based：LLM 查询计划动态生成 Cypher
```

## 12. 总结

`QuestionPaser` 的作用可以概括为：

```text
把分类器输出的 question_type 和实体，转换成 Neo4j Cypher 查询语句
```

它不负责理解自然语言，也不直接组织最终答案。它是规则版问答系统中连接“问题理解”和“图谱查询”的中间层。
