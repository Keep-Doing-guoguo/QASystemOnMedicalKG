# 项目文档目录

这个目录按当前代码结构整理项目讲解文档。

## 目录结构

```text
docs/
├── README.md
├── rule_based/
├── llm_based/
├── prepare_data/
├── DATA_STRUCTURE.md
├── DATA_PROCESS_ARCH.md
└── ALGORITHMS.md
```

## 推荐阅读顺序

1. [DATA_STRUCTURE.md](./DATA_STRUCTURE.md)：先理解图谱实体、关系和属性结构。
2. [DATA_PROCESS_ARCH.md](./DATA_PROCESS_ARCH.md)：理解数据从采集、清洗到建图的流程。
3. [prepare_data/README.md](./prepare_data/README.md)：查看数据准备脚本说明。
4. [rule_based/README.md](./rule_based/README.md)：查看规则匹配版问答链路。
5. [llm_based/README.md](./llm_based/README.md)：查看 LLM 版问答通道设计。
6. [ALGORITHMS.md](./ALGORITHMS.md)：查看项目中用到的关键算法和规则。

## 目录说明

### rule_based

`docs/rule_based/` 对应代码目录 `rule_based/`，主要讲解传统规则版问答系统：

```text
词典匹配 -> 规则分类 -> Cypher 生成 -> Neo4j 查询 -> 模板回答
```

### llm_based

`docs/llm_based/` 对应代码目录 `llm_based/`，主要讲解大模型版问答通道：

```text
实体对齐 -> LLM 查询计划 -> Cypher 构造 -> Neo4j 查询 -> LLM 答案生成
```

### prepare_data

`docs/prepare_data/` 对应代码目录 `prepare_data/`，主要讲解数据采集、清洗、导入前处理等脚本。
