# 数据处理部分架构（讲解大纲）

下面是“数据处理部分”的整体架构框架，你可以在每个模块下补充细节与讲解内容。

## 1. 数据来源层

- 目标站点与页面类型
- 数据采集范围（疾病页、检查项页等）
- 输出：原始网页内容或结构化片段

## 2. 爬虫采集层（data_spider.py）

- 入口：爬虫启动与任务调度
- 处理：抓取网页、解析基础字段、入库
- 输出到 MongoDB：
  - `data` 集合：疾病相关原始/半结构化信息
  - `jc` 集合：检查项页面原始 HTML

## 3. 结构化解析层（build_data.py）

### 3.1 检查项解析（modify_jc）
- 输入：`jc` 集合原始 HTML
- 处理：解析检查项名称与描述
- 输出：更新 `jc` 集合结构化字段

### 3.2 疾病数据整理（collect_medical）
- 输入：`data` 集合原始/半结构化数据
- 处理：
  - 字段清洗与统一格式（如去空格、换行）
  - 字段映射（中文字段 → 英文字段）
  - 列表字段整理（症状、检查、食物、药品、科室等）
  - 并发症字段处理（当前为简单分割）
- 输出：写入 `medical` 集合（结构化疾病数据）

#### 字段映射（展开说明）

1) 基础信息与属性类字段  
来源：`basic_info` / `attributes` / `treat_info` / `cause_info` / `prevent_info`

- `basic_info.name` → `name`（疾病名称）  
- `basic_info.desc` → `desc`（疾病简介）  
- `cause_info` → `cause`（病因说明）  
- `prevent_info` → `prevent`（预防措施）  
- `basic_info.category` → `category`（分类标签）

从 `attributes` / `treat_info` 中抽取（中文键 → 英文字段）：

- `医保疾病` → `yibao_status`  
- `患病比例` → `get_prob`  
- `易感人群` → `easy_get`  
- `传播方式` → `get_way`  
- `就诊科室` → `cure_department`  
- `治疗方式` → `cure_way`  
- `治疗周期` → `cure_lasttime`  
- `治愈率` → `cured_prob`  
- `治疗费用` → `cost_money`

处理方式说明：
- `yibao_status / get_prob / easy_get / get_way / cure_lasttime / cured_prob`  
  → 去空格和制表符  
- `cure_department / cure_way / common_drug`  
  → 按空格拆成列表  

2) 症状与并发症  
来源：`symptom_info`

- `symptom_info` → `symptom`（症状列表，去掉停用词）  
- 并发症 `acompany`：  
  由 `attributes` 中的“并发症”字段映射  
  当前版本使用简单分割，不再依赖 `dict/disease.txt` 分词

3) 检查项  
来源：`inspect_info`

- `inspect_info`（URL 列表）  
  → `get_inspect(url)` 查 `jc` 集合  
  → `check`（检查项名称列表）

4) 饮食建议  
来源：`food_info`

- `food_info.good` → `do_eat`（宜吃）  
- `food_info.bad` → `not_eat`（忌吃）  
- `food_info.recommand` → `recommand_eat`（推荐食谱）

5) 药品与厂商  
来源：`drug_info` / `drug_detail`

- `drug_info` → `recommand_drug`（推荐药品名称列表）  
- `drug_detail` → `drug_detail`（药品详情，含厂商信息）  
- `drug_detail` 会在建图阶段拆分厂商/药品：  
  `(Producer)-[:drugs_of]->(Drug)`

注意：  
新版网站中 `drug_info / drug_detail` 可能为空或缺失，  
如果你不需要药品相关关系，这一部分可以在流程中忽略或删除。

## 4. 数据导出层（可选）

- 将 `medical` 集合导出为 `data/medical.json`
- 为后续图谱构建提供统一输入

## 5. 输出与后续消费

- `medical.json` → `build_medicalgraph.py` 建图
- `dict/*.txt` 词典（可选，由 JSON 或 DB 导出）

## 6. 关系列表与对应关系（build_medicalgraph.py）

以下来自 `build_medicalgraph.py` 的 `rels_*` 列表，已展开成“来源字段 → 关系类型 → 方向”，并补充中文含义。

### 6.1 疾病与症状/并发/检查

1) `rels_symptom`  
来源：`symptom`  
关系：`(Disease)-[:has_symptom]->(Symptom)`  
中文：疾病—症状

2) `rels_acompany`  
来源：`acompany`  
关系：`(Disease)-[:acompany_with]->(Disease)`  
中文：疾病—并发症

3) `rels_check`  
来源：`check`  
关系：`(Disease)-[:need_check]->(Check)`  
中文：疾病—检查项目

### 6.2 疾病与药品/厂商

4) `rels_commonddrug`  
来源：`common_drug`  
关系：`(Disease)-[:common_drug]->(Drug)`  
中文：疾病—常用药品

5) `rels_recommanddrug`  
来源：`recommand_drug`  
关系：`(Disease)-[:recommand_drug]->(Drug)`  
中文：疾病—推荐药品

11) `rels_drug_producer`  
来源：`drug_detail`  
关系：`(Producer)-[:drugs_of]->(Drug)`  
中文：厂商—药品

### 6.3 疾病与饮食

6) `rels_noteat`  
来源：`not_eat`  
关系：`(Disease)-[:no_eat]->(Food)`  
中文：疾病—忌吃食物

7) `rels_doeat`  
来源：`do_eat`  
关系：`(Disease)-[:do_eat]->(Food)`  
中文：疾病—宜吃食物

8) `rels_recommandeat`  
来源：`recommand_eat`  
关系：`(Disease)-[:recommand_eat]->(Food)`  
中文：疾病—推荐食谱

### 6.4 疾病与科室

9) `rels_department`  
来源：`cure_department`（两级科室）  
关系：`(Department)-[:belongs_to]->(Department)`  
中文：科室—科室隶属

10) `rels_category`  
来源：`cure_department`  
关系：`(Disease)-[:belongs_to]->(Department)`  
中文：疾病—所属科室

## 7. 节点创建与 medical.json 对应关系

以下说明“medical.json 字段 → 节点/属性”的对应关系（以单条疾病记录为单位）。

### 7.1 Disease 节点（核心）

节点标签：`Disease`  
节点属性来自 `medical.json` 的字段：

- `name` → `Disease.name`
- `desc` → `Disease.desc`
- `prevent` → `Disease.prevent`
- `cause` → `Disease.cause`
- `easy_get` → `Disease.easy_get`
- `cure_department` → `Disease.cure_department`
- `cure_way` → `Disease.cure_way`
- `cure_lasttime` → `Disease.cure_lasttime`
- `cured_prob` → `Disease.cured_prob`
- `get_prob` → `Disease.get_prob`

说明：
- 以上属性是在 `create_diseases_nodes()` 中一次性写入的。

### 7.2 其他实体节点

这些节点都只有 `name` 属性，来源于 `medical.json` 中的列表字段：

- `symptom` → `Symptom` 节点（`Symptom.name`）
- `check` → `Check` 节点（`Check.name`）
- `cure_department` → `Department` 节点（`Department.name`）
- `common_drug / recommand_drug` → `Drug` 节点（`Drug.name`）
- `not_eat / do_eat / recommand_eat` → `Food` 节点（`Food.name`）
- `drug_detail`（解析厂商）→ `Producer` 节点（`Producer.name`）

### 7.3 与图片字段的直接对应

你图里的字段可以直接对应到如下节点/属性：

- `name / desc / prevent / cause / easy_get / cure_way / cure_lasttime / cured_prob / get_prob`  
  → Disease 节点属性
- `symptom` → Symptom 节点
- `check` → Check 节点
- `cure_department` → Department 节点
- `do_eat / not_eat / recommand_eat` → Food 节点
- `recommand_drug / common_drug` → Drug 节点
- `drug_detail` → Producer 节点（由药品详情解析厂商）

## 问答系统流程（改写版）

用户问题进入系统后，依次完成：

1. 实体识别：从问题中匹配疾病/症状/药品等实体  
2. 意图分类：结合触发词判断问题类型  
3. Cypher 查询生成：把意图转换成图查询语句  
4. 答案生成：执行查询并组织为自然语言回复

---

如果你希望，我可以把每个模块补充成“讲解稿版本”，也可以补流程图或字段映射图。
