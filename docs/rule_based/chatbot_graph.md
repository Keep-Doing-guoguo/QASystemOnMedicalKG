# chatbot_graph.py 讲解

当前代码位置：

```text
rule_based/chatbot_graph.py
```

`chatbot_graph.py` 是规则版医疗问答系统的入口文件。它负责把问题分类、问题解析、图谱查询和答案生成串联起来。

它的核心作用是：

```text
输入用户问题
  -> 调用 QuestionClassifier 识别问题类型
  -> 调用 QuestionPaser 生成 Cypher
  -> 调用 AnswerSearcher 查询 Neo4j
  -> 返回最终答案
```

## 1. 整体定位

规则版问答链路是：

```text
用户问题
  -> QuestionClassifier
  -> QuestionPaser
  -> AnswerSearcher
  -> 最终答案
```

`chatbot_graph.py` 是这条链路的主控层。

它本身不直接做实体识别，也不直接写 Cypher，更不直接处理 Neo4j 查询结果。它只负责：

```text
组织调用顺序
处理兜底返回
提供运行入口
```

## 2. 导入模块

当前代码：

```python
try:
    from rule_based.question_classifier import *
    from rule_based.question_parser import *
    from rule_based.answer_search import *
except ModuleNotFoundError:
    from question_classifier import *
    from question_parser import *
    from answer_search import *
```

这里写成 `try/except` 是为了兼容两种运行方式。

推荐方式：

```bash
python -m rule_based.chatbot_graph
```

也兼容直接运行：

```bash
python rule_based/chatbot_graph.py
```

直接运行文件时，Python 的模块搜索路径可能找不到 `rule_based` 包，所以代码会退回到相对当前目录导入。

## 3. ChatBotGraph 类

核心类：

```python
class ChatBotGraph:
```

它代表一个规则版问答机器人。

初始化代码：

```python
def __init__(self):
    self.classifier = QuestionClassifier()
    self.parser = QuestionPaser()
    self.searcher = AnswerSearcher()
```

这里创建了三个核心组件：

| 成员 | 类型 | 作用 |
| --- | --- | --- |
| `self.classifier` | `QuestionClassifier` | 识别实体和问题类型 |
| `self.parser` | `QuestionPaser` | 把问题类型转换成 Cypher |
| `self.searcher` | `AnswerSearcher` | 查询 Neo4j 并生成答案 |

所以 `ChatBotGraph` 本身是一个组合器。

## 4. chat_main 的主流程

核心方法：

```python
def chat_main(self, sent):
```

它接收一句用户输入，然后返回回答。

完整代码逻辑：

```python
answer = '您好，我是小勇医药智能助理，希望可以帮到您。如果没答上来，可联系https://liuhuanyong.github.io/。祝您身体棒棒！'
res_classify = self.classifier.classify(sent)
if not res_classify:
    return answer
res_sql = self.parser.parser_main(res_classify)
final_answers = self.searcher.search_main(res_sql)
if not final_answers:
    return answer
else:
    return '\n'.join(final_answers)
```

可以拆成四步。

### 4.1 设置默认回答

```python
answer = '您好，我是小勇医药智能助理...'
```

这是兜底答案。

当分类失败、查询失败或没有图谱结果时，都会返回这句话。

### 4.2 调用分类器

```python
res_classify = self.classifier.classify(sent)
if not res_classify:
    return answer
```

如果用户问题无法识别实体，`QuestionClassifier` 会返回 `{}`。

例如：

```text
我最近不太舒服怎么办？
```

如果没有命中词典实体，就会直接返回默认回答。

### 4.3 调用解析器

```python
res_sql = self.parser.parser_main(res_classify)
```

例如分类结果是：

```python
{
    "args": {
        "高血压": ["disease"]
    },
    "question_types": ["disease_not_food"]
}
```

解析器会生成：

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

### 4.4 调用查询器

```python
final_answers = self.searcher.search_main(res_sql)
```

`AnswerSearcher` 会执行 Cypher，并把查询结果格式化为自然语言。

如果没有答案：

```python
if not final_answers:
    return answer
```

如果有多个答案：

```python
return '\n'.join(final_answers)
```

这里用换行拼接，是为了支持多意图问题。

例如：

```text
高血压有什么症状，怎么治疗？
```

可能同时返回：

```text
高血压的症状包括：...
高血压可以尝试如下治疗：...
```

## 5. DEBUG_QUESTIONS 的作用

代码里定义了：

```python
DEBUG_QUESTIONS = [
    "乳腺癌的症状有哪些？",
    "最近老是流鼻涕，可能是什么病？",
    "为什么会得高血压？",
    ...
]
```

这些问题用于调试不同的 `question_type` 分支。

例如：

| 问题 | 目标分支 |
| --- | --- |
| `乳腺癌的症状有哪些？` | `disease_symptom` |
| `最近老是流鼻涕，可能是什么病？` | `symptom_disease` |
| `为什么会得高血压？` | `disease_cause` |
| `高血压不能吃什么？` | `disease_not_food` |
| `板蓝根颗粒能治什么病？` | `drug_disease` |
| `血常规能查出什么病？` | `check_disease` |

这些问题适合用来打断点观察完整流程。

## 6. 多意图调试问题

代码里还有：

```python
DEBUG_MULTI_INTENT_QUESTIONS = [
    "高血压有什么症状，怎么治疗？",
    "糖尿病吃什么药，不能吃什么？",
    "感冒多久能好，怎么预防？",
    "脑膜炎有什么症状，需要做什么检查？",
]
```

这些问题用于调试一个问题命中多个 `question_type` 的情况。

例如：

```text
脑膜炎有什么症状，需要做什么检查？
```

可能同时命中：

```python
["disease_symptom", "disease_check"]
```

然后 `chat_main()` 最终会把多个回答用换行拼起来。

## 7. run_debug_questions 的作用

代码：

```python
def run_debug_questions(handler, questions):
    for question in questions:
        print('用户:', question)
        answer = handler.chat_main(question)
        print('小勇:', answer)
        print('*' * 80)
```

它就是一个批量调试函数。

执行时会：

```text
1. 遍历问题列表
2. 调用 chat_main()
3. 打印用户问题
4. 打印系统回答
5. 打印分隔线
```

这比每次手动改一个 `question` 更适合调试完整分支。

## 8. 程序入口

代码：

```python
if __name__ == '__main__':
    handler = ChatBotGraph()

    run_debug_questions(handler, DEBUG_QUESTIONS)

    print('多意图问题调试:')
    print('*' * 80)
    run_debug_questions(handler, DEBUG_MULTI_INTENT_QUESTIONS)
```

当你直接运行这个文件时，会自动批量执行调试问题。

启动方式：

```bash
python -m rule_based.chatbot_graph
```

或者：

```bash
python rule_based/chatbot_graph.py
```

注意：运行前需要 Neo4j 已启动，并且图谱数据已经导入。

## 9. 一个完整例子

输入问题：

```text
感冒要吃什么药？
```

第一步，`chat_main()` 调用分类器：

```python
res_classify = self.classifier.classify(sent)
```

得到：

```python
{
    "args": {
        "感冒": ["disease"]
    },
    "question_types": ["disease_drug"]
}
```

第二步，调用解析器：

```python
res_sql = self.parser.parser_main(res_classify)
```

得到：

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

第三步，调用查询器：

```python
final_answers = self.searcher.search_main(res_sql)
```

得到：

```python
[
    "感冒通常的使用的药品包括：板蓝根颗粒；感冒灵颗粒"
]
```

第四步，返回给用户：

```python
return '\n'.join(final_answers)
```

## 10. 适合打断点的位置

调试这个入口文件时，建议看以下变量：

| 位置 | 变量 | 作用 |
| --- | --- | --- |
| `chat_main()` | `sent` | 用户原始问题 |
| `chat_main()` | `res_classify` | 分类器输出 |
| `chat_main()` | `res_sql` | 解析器生成的 Cypher |
| `chat_main()` | `final_answers` | 查询器生成的最终答案 |

进一步深入时，可以跳进：

```text
QuestionClassifier.classify()
QuestionPaser.parser_main()
AnswerSearcher.search_main()
AnswerSearcher.answer_prettify()
```

## 11. 这个模块的特点

优点：

```text
流程清楚
适合端到端 debug
把三个核心组件串联得很直观
支持批量测试多种 question_type
```

缺点：

```text
默认回答写死在代码里
运行时强依赖 Neo4j 连接
当前入口默认批量运行 debug 问题，不是交互式聊天
```

## 12. 和 LLM 分支的关系

`rule_based/chatbot_graph.py` 是规则版入口。

LLM 分支有自己的入口：

```text
llm_based/chatbot_graph.py
```

两者的职责类似，都是串联完整问答流程。

区别是：

```text
rule_based/chatbot_graph.py：串联规则分类、规则解析、模板答案
llm_based/chatbot_graph.py：串联实体对齐、LLM 查询计划、Cypher 构造、LLM 答案生成
```

## 13. 总结

`chatbot_graph.py` 的作用可以概括为：

```text
规则版问答系统的总入口和流程调度器
```

它负责把用户问题依次交给分类器、解析器和查询器，并最终把答案返回给用户。
