# QASystemOnMedicalKG

这是一个基于医疗知识图谱的问答系统。项目以疾病为中心构建 Neo4j 图谱，并提供两条问答通道：

```text
rule_based：词典匹配 + 规则分类 + Cypher 查询 + 模板回答
llm_based ：词典实体对齐 + LLM 查询规划 + Cypher 查询 + LLM/模板回答
```

当前代码已经按学习和调试方式重新整理过。推荐先从 `rule_based` 理解传统规则问答链路，再看 `llm_based` 如何在保持图谱内容不变的前提下接入大模型。

## 1. 项目目录

```text
.
├── data/                  # 原始医疗数据，例如 medical.json
├── dict/                  # 实体词典，供规则分类和 LLM 实体对齐使用
├── docs/                  # 项目讲解文档
├── llm_based/             # 大模型版问答通道
├── prepare_data/          # 数据采集、清洗和中间处理脚本
├── rule_based/            # 规则匹配版问答通道和 Neo4j 建图脚本
├── web_app/               # 简单前端问答工作台
├── .vscode/               # VS Code 调试配置
└── README.md
```

核心目录说明：

| 目录 | 作用 |
| --- | --- |
| `rule_based/` | 原始规则版问答主线，适合学习知识图谱问答的基本流程 |
| `llm_based/` | LLM 版问答通道，让大模型负责理解问题和生成回答 |
| `dict/` | 疾病、症状、药品、食物、检查等实体词典 |
| `data/` | 建图使用的数据文件 |
| `docs/` | 按模块整理后的讲解文档 |
| `web_app/` | 可视化调试页面，不参与项目讲解主线 |

## 2. 图谱规模

原始项目构建的是一个疾病中心的医疗知识图谱，包含约 4.4 万个实体和约 30 万条关系。

### 2.1 节点类型

| Neo4j Label | 中文含义 | 示例 |
| --- | --- | --- |
| `Disease` | 疾病 | 高血压、糖尿病、乳腺癌 |
| `Symptom` | 症状 | 流鼻涕、胸痛、乳房肿块 |
| `Drug` | 药品 | 板蓝根颗粒、布林佐胺滴眼液 |
| `Food` | 食物 | 蜂蜜、鹅肉、番茄冲菜牛肉丸汤 |
| `Check` | 检查项目 | 血常规、支气管造影 |
| `Department` | 科室 | 内科、妇产科 |
| `Producer` | 在售药品/生产商药品名 | 通药制药青霉素V钾片 |

### 2.2 关系类型

| 关系类型 | 中文含义 | 示例 |
| --- | --- | --- |
| `has_symptom` | 疾病症状 | 疾病 -> 症状 |
| `acompany_with` | 并发疾病 | 疾病 -> 疾病 |
| `no_eat` | 忌吃食物 | 疾病 -> 食物 |
| `do_eat` | 宜吃食物 | 疾病 -> 食物 |
| `recommand_eat` | 推荐食谱 | 疾病 -> 食物 |
| `common_drug` | 常用药品 | 疾病 -> 药品 |
| `recommand_drug` | 推荐药品 | 疾病 -> 药品 |
| `need_check` | 所需检查 | 疾病 -> 检查项目 |
| `drugs_of` | 在售药品 | 生产商药品名 -> 药品 |
| `belongs_to` | 所属科室 | 疾病/科室 -> 科室 |

### 2.3 疾病属性

`Disease` 节点除了 `name` 外，还包含这些常用属性：

| 属性 | 中文含义 |
| --- | --- |
| `desc` | 疾病简介 |
| `cause` | 疾病病因 |
| `prevent` | 预防措施 |
| `cure_lasttime` | 治疗周期 |
| `cure_way` | 治疗方式 |
| `cured_prob` | 治愈概率 |
| `easy_get` | 易感人群 |

目前 `cause`、`prevent` 这类内容还是大段文本属性。后续可以尝试事件抽取，把原因、预防措施等拆成独立节点和关系。

## 3. 环境准备

### 3.1 Python 虚拟环境

项目根目录已经按 `.venv` 使用方式整理。新环境可以这样创建：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install py2neo==2021.2.4 pyahocorasick==2.1.0 lxml==5.3.0 pymongo==4.10.1
```

注意：

```text
pip 安装包名是 pyahocorasick
代码导入名是 ahocorasick
```

所以不要执行：

```bash
pip install ahocorasick
```

应该执行：

```bash
pip install pyahocorasick
```

### 3.2 Neo4j

项目默认连接配置：

```text
地址：bolt://127.0.0.1:7687
账号：neo4j
密码：12341234
```

相关代码位置：

```text
rule_based/build_medicalgraph.py
rule_based/answer_search.py
llm_based/graph_client.py
```

如果本机 Neo4j 密码不同，需要同步修改这些文件。

Mac 上如果 Neo4j 解压目录是：

```text
/Volumes/PSSD/sources/neo4j-community-5.25.1
```

可以进入目录后启动：

```bash
cd /Volumes/PSSD/sources/neo4j-community-5.25.1
bin/neo4j console
```

Neo4j Browser 默认地址：

```text
http://127.0.0.1:7474
```

Bolt 默认地址：

```text
bolt://127.0.0.1:7687
```

### 3.3 MongoDB

如果只是运行现有知识图谱问答，通常不需要 MongoDB。

如果要重新执行 `prepare_data/` 里的采集、清洗、入库流程，才需要 MongoDB。

## 4. 导入知识图谱

确认 Neo4j 已经启动后，在项目根目录执行：

```bash
.venv/bin/python rule_based/build_medicalgraph.py
```

这个脚本会读取：

```text
data/medical.json
```

并向 Neo4j 写入节点、关系和疾病属性。

数据量较大，首次导入可能需要较长时间。

导入后可以在 Neo4j Browser 中检查：

```cypher
MATCH (n) RETURN labels(n), count(n) LIMIT 20;
```

也可以检查某个疾病：

```cypher
MATCH (d:Disease {name: "乳腺癌"}) RETURN d LIMIT 1;
```

检查疾病症状关系：

```cypher
MATCH (d:Disease {name: "乳腺癌"})-[r:has_symptom]->(s:Symptom)
RETURN d.name, r.name, s.name
LIMIT 10;
```

## 5. 规则版问答：rule_based

启动：

```bash
.venv/bin/python -m rule_based.chatbot_graph
```

核心流程：

```text
用户问题
  -> QuestionClassifier 识别实体和 question_type
  -> QuestionPaser 生成 Cypher
  -> AnswerSearcher 查询 Neo4j
  -> 根据 question_type 套用回答模板
```

主要文件：

| 文件 | 作用 |
| --- | --- |
| `rule_based/question_classifier.py` | 词典匹配 + 规则判断，输出 `question_types` |
| `rule_based/question_parser.py` | 把 `question_type` 转成 Cypher |
| `rule_based/answer_search.py` | 执行 Cypher，并按模板生成答案 |
| `rule_based/chatbot_graph.py` | 规则版主入口 |

调试时会看到类似日志：

```text
[ChatBotGraph] question: 乳腺癌的症状有哪些？
[QuestionClassifier] matched_entities: {'乳腺癌': ['disease']}
[QuestionClassifier] entity_types: ['disease']
[QuestionClassifier] question_types: ['disease_symptom']
[QuestionPaser] sql_for_disease_symptom: [...]
[AnswerSearcher] raw_result: [...]
```

常见判断方式：

| 日志现象 | 可能原因 |
| --- | --- |
| `matched_entities` 为空 | 词典没有识别到实体 |
| `question_types` 不符合预期 | 规则关键词没有命中 |
| `sql` 为空 | parser 没有对应模板 |
| `raw_result` 为空 | Neo4j 没有查到对应节点或关系 |
| `pretty_answer` 为空 | 查询结果和回答模板字段不匹配 |

## 6. 大模型版问答：llm_based

启动：

```bash
.venv/bin/python -m llm_based.chatbot_graph
```

## 7. Web 服务与会话接口

启动调试工作台：

```bash
.venv/bin/python web_app/server.py
```

默认地址：

```text
http://127.0.0.1:8000
```

当前接口：

```text
GET  /api/status
GET  /api/session/status
POST /api/rule/chat
POST /api/llm/chat
POST /api/session/clear
```

`/api/llm/chat` 请求示例：

```json
{
  "question": "高血压不能吃什么？",
  "session_id": "optional-browser-session-id"
}
```

统一响应结构：

```json
{
  "ok": true,
  "code": "OK",
  "request_id": "uuid",
  "data": {},
  "error": null,
  "meta": {
    "duration_ms": 12.34
  }
}
```

## 8. 工程化运行建议

推荐通过环境变量配置运行参数，参考：

```text
.env.example
```

重点配置项：

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
NEO4J_URI
NEO4J_USER
NEO4J_PASSWORD
WEB_HOST
WEB_PORT
APP_LOG_LEVEL
```

## 9. 测试

运行基础单元测试：

```bash
python -m unittest
```

## 10. Docker 部署

构建镜像：

```bash
docker build -t medical-kg-qa:latest .
```

运行容器：

```bash
docker run --rm -p 8000:8000 \
  -e WEB_HOST=0.0.0.0 \
  -e WEB_PORT=8000 \
  -e LLM_API_KEY=your-key \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=12341234 \
  medical-kg-qa:latest
```

## 11. 后续建议

当前项目已经具备比较清晰的模块边界、基础测试、会话记忆和统一响应结构，但如果要继续向完整生产级靠近，下一步最值得做的是：

1. 将 `web_app/server.py` 迁移到 `FastAPI`
2. 增加请求鉴权、限流和中间件
3. 增加更完整的评测集与自动化回归
4. 引入容器编排和监控告警

核心流程：

```text
用户问题
  -> EntityLinker 从 dict/ 中识别图谱实体
  -> IntentPlanner 让 LLM 生成结构化查询计划 plan
  -> CypherBuilder 把 plan 转成参数化 Cypher
  -> GraphClient 查询 Neo4j
  -> AnswerGenerator 根据图谱结果生成自然语言回答
```

主要文件：

| 文件 | 作用 |
| --- | --- |
| `llm_based/config.py` | LLM API 配置 |
| `llm_based/schema.py` | 节点、属性、关系白名单 |
| `llm_based/entity_linker.py` | 基于词典的实体识别和实体校验 |
| `llm_based/intent_planner.py` | 调用 LLM 生成查询计划 |
| `llm_based/cypher_builder.py` | 把查询计划转成 Cypher |
| `llm_based/graph_client.py` | 查询 Neo4j |
| `llm_based/answer_generator.py` | LLM/模板生成最终回答 |
| `llm_based/chatbot_graph.py` | LLM 版主入口 |

LLM 配置写在：

```text
llm_based/config.py
```

示例：

```python
LLM_API_KEY = "你的 API Key"
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen-turbo"
LLM_TIMEOUT = 30
LLM_MAX_RETRIES = 2
```

注意：不要把真实 API Key 提交到公开仓库。

`llm_based` 不是让大模型直接回答医学问题，而是让大模型做两件事：

```text
1. 理解问题，生成受 schema 约束的查询计划
2. 根据 Neo4j 查询结果整理自然语言答案
```

事实数据仍然来自 Neo4j 知识图谱。

调试时会看到类似日志：

```text
[EntityLinker] linked_entities: [...]
[IntentPlanner] raw_plan: {...}
[IntentPlanner] normalized_plan: {...}
[CypherBuilder] cypher: MATCH ...
[GraphClient] result_count: 10
[AnswerGenerator] llm_answer: ...
```

常见判断方式：

| 日志现象 | 可能原因 |
| --- | --- |
| `linked_entities` 为空 | `dict/` 词典没有识别到实体 |
| `raw_plan` 为空 | LLM 调用失败或没有返回 JSON |
| `normalized_plan` 为空 | LLM 输出不符合 schema |
| `cypher` 为空 | plan 的 label、relation、property 不匹配 |
| `result_count` 为 0 | Neo4j 没有对应数据 |
| `llm_answer` 为空 | 回答生成模型调用失败，会走本地模板 |

## 7. 前端调试页面

启动：

```bash
.venv/bin/python web_app/server.py
```

浏览器访问：

```text
http://127.0.0.1:8000
```

前端支持：

```text
规则版 / LLM 版切换
实体识别结果查看
question_type 或 LLM plan 查看
Cypher 查看
Neo4j 原始结果查看
简单图谱子图展示
```

## 8. VS Code 调试

项目包含 `.vscode/launch.json`，可以直接在 VS Code 的 Run and Debug 中选择：

```text
Python: rule_based chatbot
Python: llm_based chatbot
Python: build medical graph
```

`.vscode/settings.json` 已经指向项目虚拟环境：

```text
${workspaceFolder}/.venv/bin/python
```

如果你使用 Code Runner 插件，建议确认它也使用 `.venv/bin/python`，否则可能出现：

```text
ModuleNotFoundError: No module named 'rule_based'
ModuleNotFoundError: No module named 'llm_based'
```

推荐运行方式仍然是：

```bash
.venv/bin/python -m rule_based.chatbot_graph
.venv/bin/python -m llm_based.chatbot_graph
```

## 9. 支持的问答类型

规则版主要支持这些 `question_type`：

| question_type | 中文含义 | 示例 |
| --- | --- | --- |
| `disease_desc` | 疾病简介 | 糖尿病 |
| `disease_symptom` | 疾病查症状 | 乳腺癌的症状有哪些？ |
| `symptom_disease` | 症状反查疾病 | 流鼻涕可能是什么病？ |
| `disease_cause` | 疾病病因 | 为什么会得高血压？ |
| `disease_acompany` | 疾病并发症 | 糖尿病有哪些并发症？ |
| `disease_not_food` | 疾病忌口 | 高血压不能吃什么？ |
| `disease_do_food` | 疾病宜吃/推荐食谱 | 高血压适合吃什么？ |
| `food_not_disease` | 食物反查忌口疾病 | 哪些病人不能吃蜂蜜？ |
| `food_do_disease` | 食物反查适合疾病 | 鹅肉对什么病有好处？ |
| `disease_drug` | 疾病查药品 | 感冒要吃什么药？ |
| `drug_disease` | 药品反查疾病 | 板蓝根颗粒能治什么病？ |
| `disease_check` | 疾病查检查 | 脑膜炎需要做什么检查？ |
| `check_disease` | 检查反查疾病 | 血常规能查出什么病？ |
| `disease_prevent` | 疾病预防 | 怎么预防高血压？ |
| `disease_lasttime` | 治疗周期 | 感冒多久能好？ |
| `disease_cureway` | 治疗方式 | 糖尿病怎么治疗？ |
| `disease_cureprob` | 治愈概率 | 高血压能治好吗？ |
| `disease_easyget` | 易感人群 | 什么人容易得糖尿病？ |

LLM 版没有直接使用这些 `question_type`，而是使用结构化 plan：

```json
{
  "action": "query_relation",
  "subject": {
    "name": "乳腺癌",
    "label": "Disease"
  },
  "relation": "has_symptom",
  "direction": "outgoing"
}
```

或者：

```json
{
  "action": "query_property",
  "subject": {
    "name": "高血压",
    "label": "Disease"
  },
  "property": "cause"
}
```

## 10. 推荐学习顺序

1. 先看 [docs/README.md](docs/README.md)，了解文档目录。
2. 看 [docs/rule_based/question_classifier.md](docs/rule_based/question_classifier.md)，理解规则分类。
3. 看 [docs/rule_based/question_parser.md](docs/rule_based/question_parser.md)，理解 Cypher 是如何生成的。
4. 看 [docs/rule_based/answer_search.md](docs/rule_based/answer_search.md)，理解 Neo4j 查询和模板回答。
5. 运行 `rule_based`，跟着日志一步步 debug。
6. 看 [docs/llm_based/README.md](docs/llm_based/README.md)，理解 LLM 通道。
7. 运行 `llm_based`，重点观察 `linked_entities -> raw_plan -> cypher -> graph_results`。
8. 最后用 `web_app` 做可视化调试。

## 11. 常见问题

### pip install ahocorasick 失败

安装包名不是 `ahocorasick`，而是：

```bash
pip install pyahocorasick
```

代码里仍然这样导入：

```python
import ahocorasick
```

### No module named rule_based / llm_based

不要直接在任意目录运行某个文件。推荐在项目根目录使用模块方式：

```bash
.venv/bin/python -m rule_based.chatbot_graph
.venv/bin/python -m llm_based.chatbot_graph
```

### Cannot open connection to bolt://127.0.0.1:7687

通常是 Neo4j 没启动、端口不通、账号密码不对，或者 Neo4j 启动后还没有完成初始化。

先检查端口：

```bash
nc -vz 127.0.0.1 7687
```

再检查 Neo4j Browser：

```text
http://127.0.0.1:7474
```

### LLM 通道查不到 Neo4j 数据

按日志逐步看：

```text
EntityLinker 是否识别到实体
IntentPlanner 是否生成正确 plan
CypherBuilder 是否生成正确 Cypher
GraphClient 的 result_count 是否为 0
```

如果 `result_count` 是 0，可以把日志里的 Cypher 和 parameters 拿到 Neo4j Browser 里手动验证。

## 12. 项目后续可以扩展的方向

目前这个项目适合作为医疗知识图谱问答学习项目。后续可以继续尝试：

```text
把 cause / prevent 等大段文本属性进一步结构化为节点和关系
增加更多 LLM 查询计划类型
支持多跳关系查询
支持实体消歧
支持更完整的前端图谱可视化
用事件抽取把病因、预防措施、治疗方式结构化
```
