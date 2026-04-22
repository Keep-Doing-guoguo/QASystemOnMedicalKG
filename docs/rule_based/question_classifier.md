# question_classifier.py 讲解

当前代码位置：

```text
rule_based/question_classifier.py
```

`QuestionClassifier` 不是机器学习模型，也不是训练出来的分类器。它是一个基于词典匹配和规则判断的问句分类器。

它的核心作用是：

```text
输入一句用户问题
  -> 识别问题里出现了哪些医疗实体
  -> 判断这些实体属于疾病、症状、药品、食物、检查项目等哪一类
  -> 根据疑问词和实体类型判断问题意图
  -> 输出 question_type
```

例如：

```python
question = "高血压不能吃什么？"
```

会被分类成：

```python
{
    "args": {
        "高血压": ["disease"]
    },
    "question_types": ["disease_not_food"]
}
```

然后这个结果会交给 `QuestionPaser`，由 `QuestionPaser` 生成 Neo4j 的 Cypher 查询语句。

## 1. 整体定位

在规则版问答系统中，完整链路是：

```text
用户问题
  -> QuestionClassifier 识别实体和问题类型
  -> QuestionPaser 生成 Cypher 查询
  -> AnswerSearcher 查询 Neo4j 并生成回答
```

所以 `QuestionClassifier` 是问答系统的第一层，也可以理解为“问题理解层”。

它本身不存储医学知识。医学知识来自：

```text
dict/ 词典
data/medical.json
Neo4j 图谱
```

`QuestionClassifier` 只负责判断：

```text
这个问题应该走哪一种查询路线
```

## 2. 初始化时加载词典

`QuestionClassifier.__init__()` 里首先定位项目根目录，然后加载 `dict/` 下的词典文件：

```python
cur_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

self.disease_path = os.path.join(cur_dir, 'dict/disease.txt')
self.department_path = os.path.join(cur_dir, 'dict/department.txt')
self.check_path = os.path.join(cur_dir, 'dict/check.txt')
self.drug_path = os.path.join(cur_dir, 'dict/drug.txt')
self.food_path = os.path.join(cur_dir, 'dict/food.txt')
self.producer_path = os.path.join(cur_dir, 'dict/producer.txt')
self.symptom_path = os.path.join(cur_dir, 'dict/symptom.txt')
self.deny_path = os.path.join(cur_dir, 'dict/deny.txt')
```

这些词典分别对应：

| 词典文件 | 实体类型 | 作用 |
| --- | --- | --- |
| `dict/disease.txt` | `disease` | 疾病词典 |
| `dict/department.txt` | `department` | 科室词典 |
| `dict/check.txt` | `check` | 检查项目词典 |
| `dict/drug.txt` | `drug` | 药品词典 |
| `dict/food.txt` | `food` | 食物词典 |
| `dict/producer.txt` | `producer` | 药品生产商 / 在售药品词典 |
| `dict/symptom.txt` | `symptom` | 症状词典 |
| `dict/deny.txt` | 否定词 | 用来判断“不能吃”“不要吃”等否定语义 |

然后它把每个词典文件逐行读取成列表：

```python
self.disease_wds = [i.strip() for i in open(self.disease_path, encoding='utf-8') if i.strip()]
self.department_wds = [i.strip() for i in open(self.department_path, encoding='utf-8') if i.strip()]
self.check_wds = [i.strip() for i in open(self.check_path, encoding='utf-8') if i.strip()]
self.drug_wds = [i.strip() for i in open(self.drug_path, encoding='utf-8') if i.strip()]
self.food_wds = [i.strip() for i in open(self.food_path, encoding='utf-8') if i.strip()]
self.producer_wds = [i.strip() for i in open(self.producer_path, encoding='utf-8') if i.strip()]
self.symptom_wds = [i.strip() for i in open(self.symptom_path, encoding='utf-8') if i.strip()]
```

所以，分类器的基础不是训练数据，而是这些人工整理或数据处理生成的领域词典。

## 3. 合并所有实体词

加载完各类词典后，代码会把所有实体词合并成一个总词表：

```python
self.region_words = set(
    self.department_wds
    + self.disease_wds
    + self.check_wds
    + self.drug_wds
    + self.food_wds
    + self.producer_wds
    + self.symptom_wds
)
```

`region_words` 就是系统可以识别的全部医疗实体集合。

比如里面可能有：

```text
高血压
糖尿病
乳腺癌
流鼻涕
板蓝根颗粒
蜂蜜
血常规
```

用户问题中如果不包含这些词，分类器大概率无法识别实体，也就无法继续分类。

例如：

```text
我最近不舒服怎么办？
```

如果“不舒服”不在症状词典中，`QuestionClassifier` 可能直接返回：

```python
{}
```

## 4. 构建 Aho-Corasick 自动机

项目使用 `ahocorasick` 来做高效多词匹配。

对应代码：

```python
def build_actree(self, wordlist):
    actree = ahocorasick.Automaton()
    for index, word in enumerate(wordlist):
        actree.add_word(word, (index, word))
    actree.make_automaton()
    return actree
```

初始化时调用：

```python
self.region_tree = self.build_actree(list(self.region_words))
```

它的作用是：

```text
把所有疾病、症状、药品、食物、检查项目等词做成一个快速匹配结构
```

这样用户输入一句话时，不需要一个词一个词遍历所有词典，而是可以快速找出问题中出现了哪些领域词。

例如：

```python
question = "高血压不能吃什么？"
```

自动机会匹配出：

```python
["高血压"]
```

再比如：

```python
question = "板蓝根颗粒能治什么病？"
```

自动机会匹配出：

```python
["板蓝根颗粒"]
```

## 5. 建立实体词到实体类型的映射

分类器还会建立一个字典，用来记录每个实体词属于什么类型。

对应函数是：

```python
def build_wdtype_dict(self):
    wd_dict = dict()
    for wd in self.region_words:
        wd_dict[wd] = []
        if wd in self.disease_wds:
            wd_dict[wd].append('disease')
        if wd in self.department_wds:
            wd_dict[wd].append('department')
        if wd in self.check_wds:
            wd_dict[wd].append('check')
        if wd in self.drug_wds:
            wd_dict[wd].append('drug')
        if wd in self.food_wds:
            wd_dict[wd].append('food')
        if wd in self.symptom_wds:
            wd_dict[wd].append('symptom')
        if wd in self.producer_wds:
            wd_dict[wd].append('producer')
    return wd_dict
```

这个函数会生成类似结构：

```python
{
    "高血压": ["disease"],
    "流鼻涕": ["symptom"],
    "板蓝根颗粒": ["drug"],
    "蜂蜜": ["food"],
    "血常规": ["check"]
}
```

注意，一个词可能属于多个类型。

例如某些词既可能是疾病，也可能是症状，最终可能变成：

```python
{
    "头痛": ["disease", "symptom"]
}
```

这就是为什么代码里每个词对应的是一个类型列表，而不是单个类型字符串。

## 6. 定义疑问词规则

除了实体词典，分类器还定义了很多疑问词列表。

例如症状类触发词：

```python
self.symptom_qwds = ['症状', '表征', '现象', '症候', '表现']
```

病因类触发词：

```python
self.cause_qwds = ['原因', '成因', '为什么', '怎么会', '为何']
```

饮食类触发词：

```python
self.food_qwds = ['饮食', '吃', '食', '喝', '忌口', '食谱', '食物']
```

药品类触发词：

```python
self.drug_qwds = ['药', '药品', '用药', '胶囊', '口服液', '炎片']
```

检查类触发词：

```python
self.check_qwds = ['检查', '检查项目', '查出', '测出', '试出']
```

这些疑问词就是分类规则的重要组成部分。

所以这个分类器依赖两类词：

```text
实体词：高血压、糖尿病、蜂蜜、板蓝根颗粒、血常规
疑问词：症状、为什么、吃、药、检查、多久、怎么治疗
```

## 7. classify 的分类流程

核心方法是：

```python
def classify(self, question):
```

整体流程是：

```text
1. 从问题中识别医疗实体
2. 收集实体类型
3. 根据“实体类型 + 疑问词”判断 question_type
4. 如果没有命中具体意图，使用兜底分类
5. 返回分类结果
```

### 7.1 先识别医疗实体

在 `classify()` 里，第一步是：

```python
medical_dict = self.check_medical(question)
```

`check_medical()` 会用 Aho-Corasick 自动机匹配实体。

例如：

```python
question = "高血压不能吃什么？"
```

得到：

```python
medical_dict = {
    "高血压": ["disease"]
}
```

如果没有识别出任何实体：

```python
if not medical_dict:
    return {}
```

也就是说，问题里没有命中词典实体，分类器就直接失败。

### 7.2 实体长短词去重

`check_medical()` 里有一个重要细节：

```python
stop_wds = []
for wd1 in region_wds:
    for wd2 in region_wds:
        if wd1 in wd2 and wd1 != wd2:
            stop_wds.append(wd1)

final_wds = [i for i in region_wds if i not in stop_wds]
```

它的作用是：

```text
如果同时匹配到短词和长词，保留更具体的长词
```

例如一句话中同时匹配到：

```python
["血压", "高血压"]
```

因为：

```python
"血压" in "高血压"
```

所以会删除 `"血压"`，保留：

```python
["高血压"]
```

这能减少短词带来的误匹配。

### 7.3 收集实体类型

识别完实体后，代码会收集所有实体类型：

```python
types = []
for type_ in medical_dict.values():
    types += type_
```

例如：

```python
medical_dict = {
    "高血压": ["disease"]
}
```

会得到：

```python
types = ["disease"]
```

如果问题是：

```text
板蓝根颗粒能治感冒吗？
```

可能得到：

```python
medical_dict = {
    "板蓝根颗粒": ["drug"],
    "感冒": ["disease"]
}

types = ["drug", "disease"]
```

后面的规则判断就是围绕 `types` 展开的。

## 8. 通过规则判断 question_type

分类规则本质上是很多 `if` 判断。

它的核心公式可以理解为：

```text
实体类型 + 疑问词 = 问题类型
```

### 8.1 疾病查症状

代码：

```python
if self.check_words(self.symptom_qwds, question) and ('disease' in types):
    question_type = 'disease_symptom'
    question_types.append(question_type)
```

含义是：

```text
如果问题中有“症状/表现/现象”等词
并且问题中识别到了 disease 类型实体
那么分类为 disease_symptom
```

例如：

```text
乳腺癌的症状有哪些？
```

结果：

```python
question_types = ["disease_symptom"]
```

### 8.2 症状反查疾病

代码：

```python
if self.check_words(self.symptom_qwds, question) and ('symptom' in types):
    question_type = 'symptom_disease'
    question_types.append(question_type)
```

例如：

```text
流鼻涕是什么病的症状？
```

因为 `"流鼻涕"` 是 `symptom`，所以会分类为：

```python
["symptom_disease"]
```

这里和 `disease_symptom` 的区别在于实体类型不同：

```text
Disease + 症状词 -> 查这个疾病有哪些症状
Symptom + 症状词 -> 反查这个症状可能属于哪些疾病
```

### 8.3 疾病原因

代码：

```python
if self.check_words(self.cause_qwds, question) and ('disease' in types):
    question_type = 'disease_cause'
    question_types.append(question_type)
```

例如：

```text
为什么会得高血压？
```

结果：

```python
["disease_cause"]
```

### 8.4 疾病忌口和推荐饮食

代码：

```python
if self.check_words(self.food_qwds, question) and 'disease' in types:
    deny_status = self.check_words(self.deny_words, question)
    if deny_status:
        question_type = 'disease_not_food'
    else:
        question_type = 'disease_do_food'
    question_types.append(question_type)
```

这里多了一步否定词判断。

例如：

```text
高血压不能吃什么？
```

因为：

```text
高血压 -> disease
吃 -> food_qwds
不能 -> deny_words
```

所以分类为：

```python
["disease_not_food"]
```

而：

```text
高血压适合吃什么？
```

没有否定词，所以分类为：

```python
["disease_do_food"]
```

### 8.5 药品相关问题

疾病查药品：

```python
if self.check_words(self.drug_qwds, question) and 'disease' in types:
    question_type = 'disease_drug'
```

例如：

```text
感冒要吃什么药？
```

结果：

```python
["disease_drug"]
```

药品反查疾病：

```python
if self.check_words(self.cure_qwds, question) and 'drug' in types:
    question_type = 'drug_disease'
```

例如：

```text
板蓝根颗粒能治什么病？
```

结果：

```python
["drug_disease"]
```

### 8.6 检查相关问题

疾病查检查项目：

```python
if self.check_words(self.check_qwds, question) and 'disease' in types:
    question_type = 'disease_check'
```

例如：

```text
脑膜炎需要做什么检查？
```

结果：

```python
["disease_check"]
```

检查项目反查疾病：

```python
if self.check_words(self.check_qwds+self.cure_qwds, question) and 'check' in types:
    question_type = 'check_disease'
```

例如：

```text
血常规能查出什么病？
```

结果：

```python
["check_disease"]
```

## 9. 规则和图谱查询的对应关系

这些规则不是从 Neo4j 节点自动生成的，而是作者根据图谱 schema 和问答需求手工设计出来的。

更准确地说，它们来自：

```text
1. 图谱里有哪些节点类型
2. 图谱里有哪些关系和属性
3. 系统想支持哪些用户问法
```

所以它不是：

```text
扫描 Neo4j 节点 -> 自动生成 if 规则
```

而是：

```text
先设计医疗问答场景
再根据图谱 schema 写规则
再用词典识别用户问题里的实体类型
最后映射成 question_type
```

常见映射关系如下：

| 判断公式 | question_type | 后续查询内容 |
| --- | --- | --- |
| 疾病 + 症状词 | `disease_symptom` | `Disease - has_symptom -> Symptom` |
| 症状 + 症状词 | `symptom_disease` | 从 `Symptom` 反查 `Disease` |
| 疾病 + 原因词 | `disease_cause` | `Disease.cause` |
| 疾病 + 并发词 | `disease_acompany` | `Disease - acompany_with -> Disease` |
| 疾病 + 饮食词 + 否定词 | `disease_not_food` | `Disease - no_eat -> Food` |
| 疾病 + 饮食词 + 无否定词 | `disease_do_food` | `Disease - do_eat/recommand_eat -> Food` |
| 食物 + 饮食词/用途词 + 否定词 | `food_not_disease` | 从 `Food` 反查不适合的 `Disease` |
| 食物 + 饮食词/用途词 + 无否定词 | `food_do_disease` | 从 `Food` 反查适合的 `Disease` |
| 疾病 + 药品词 | `disease_drug` | `Disease - common_drug/recommand_drug -> Drug` |
| 药品 + 治疗词 | `drug_disease` | 从 `Drug` 反查 `Disease` |
| 疾病 + 检查词 | `disease_check` | `Disease - need_check -> Check` |
| 检查项目 + 检查词/用途词 | `check_disease` | 从 `Check` 反查 `Disease` |
| 疾病 + 预防词 | `disease_prevent` | `Disease.prevent` |
| 疾病 + 多久/周期词 | `disease_lasttime` | `Disease.cure_lasttime` |
| 疾病 + 治疗方式词 | `disease_cureway` | `Disease.cure_way` |
| 疾病 + 治愈概率词 | `disease_cureprob` | `Disease.cured_prob` |
| 疾病 + 易感人群词 | `disease_easyget` | `Disease.easy_get` |
| 疾病 + 没命中具体疑问词 | `disease_desc` | `Disease.desc` |

## 10. 支持多个分类结果

`question_types` 是列表，所以一个问题可以命中多个分类。

例如：

```text
高血压有什么症状，怎么治疗？
```

可能同时命中：

```python
[
    "disease_symptom",
    "disease_cureway"
]
```

因为它既有：

```text
症状
```

也有：

```text
怎么治疗
```

后面的 `QuestionPaser` 会对每个 `question_type` 生成一组 Cypher。

## 11. 兜底规则

如果没有命中具体问法，但识别到了疾病：

```python
if question_types == [] and 'disease' in types:
    question_types = ['disease_desc']
```

例如：

```text
糖尿病
```

没有“症状”“药”“检查”等疑问词，但识别到疾病 `"糖尿病"`，所以分类为：

```python
["disease_desc"]
```

意思是返回疾病简介。

如果没有命中具体问法，但识别到了症状：

```python
if question_types == [] and 'symptom' in types:
    question_types = ['symptom_disease']
```

例如：

```text
流鼻涕
```

会分类为：

```python
["symptom_disease"]
```

意思是根据症状查可能疾病。

## 12. 最终输出格式

最终返回：

```python
data['args'] = medical_dict
data['question_types'] = question_types
return data
```

例如问题：

```text
感冒要吃什么药？
```

可能返回：

```python
{
    "args": {
        "感冒": ["disease"]
    },
    "question_types": ["disease_drug"]
}
```

这个格式会被 `rule_based/question_parser.py` 中的 `QuestionPaser` 使用。

## 13. 一个完整例子

问题：

```text
高血压不能吃什么？
```

第一步，实体识别：

```python
medical_dict = {
    "高血压": ["disease"]
}
```

第二步，收集类型：

```python
types = ["disease"]
```

第三步，判断饮食触发词：

```python
self.check_words(self.food_qwds, question)
```

因为问题里有：

```text
吃
```

所以为 `True`。

第四步，判断否定词：

```python
deny_status = self.check_words(self.deny_words, question)
```

因为问题里有：

```text
不能
```

所以为 `True`。

第五步，得到分类：

```python
question_type = "disease_not_food"
```

第六步，后面由 `QuestionPaser` 生成 Cypher：

```cypher
MATCH (m:Disease)-[r:no_eat]->(n:Food)
where m.name = '高血压'
return m.name, r.name, n.name
```

所以这条规则的设计依据是：

```text
图谱里有 Disease 节点
图谱里有 Food 节点
图谱里有 no_eat 关系
用户可能会问“某病不能吃什么”
所以写了 disease + 饮食词 + 否定词 -> disease_not_food
```

## 14. 优点和缺点

优点：

```text
简单
可控
容易 debug
输出稳定
不需要训练数据
不依赖大模型
```

缺点：

```text
依赖词典
依赖关键词
泛化能力弱
同义表达覆盖有限
不能真正理解复杂语义
新增问法需要手写规则
```

例如：

```text
我最近总觉得胸口闷，是不是哪里有问题？
```

如果“胸口闷”不在症状词典里，或者问题中没有命中合适的触发词，规则分类器就可能无法正确处理。

## 15. 和 LLM 分支的关系

这个规则分类器代表的是传统规则问答路线：

```text
词典匹配 -> 规则分类 -> 固定 Cypher -> 模板回答
```

项目现在也有独立的 LLM 分支：

```text
llm_based/
```

LLM 分支不再复用这个 `QuestionClassifier`，而是使用新的链路：

```text
实体对齐 -> LLM 查询计划 -> Cypher 构造 -> 图谱查询 -> LLM 答案生成
```

但是两条路线共享同一套图谱内容：

```text
dict/
data/medical.json
Neo4j
```

因此可以把它们理解成：

```text
rule_based/：稳定、可控、便于教学和 debug
llm_based/：更灵活，更适合处理复杂自然语言表达
```

## 16. 总结

`QuestionClassifier` 的分类建立方式是：

```text
1. 准备医疗实体词典
2. 把疾病、症状、药品、食物、检查等词加载进内存
3. 使用 Aho-Corasick 自动机识别用户问题中的实体
4. 建立“实体 -> 类型”的映射
5. 手写疑问词规则
6. 用“实体类型 + 疑问词 + 否定词”判断问题类型
7. 输出 args 和 question_types
```

它不是训练模型，而是一个规则分类器。

核心判断公式可以理解为：

```text
实体类型 + 疑问词 = 问题类型
```

例如：

```text
疾病 + 症状词 = disease_symptom
疾病 + 原因词 = disease_cause
疾病 + 药品词 = disease_drug
疾病 + 检查词 = disease_check
疾病 + 饮食词 + 否定词 = disease_not_food
疾病 + 饮食词 + 无否定词 = disease_do_food
药品 + 治疗词 = drug_disease
食物 + 饮食词 = food_do_disease / food_not_disease
检查项目 + 检查词 = check_disease
```

所以它本质上是：

```text
从自然语言问题到图谱查询类型的规则路由器
```
