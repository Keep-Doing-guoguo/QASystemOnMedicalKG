# build_medicalgraph.py 讲解

当前代码位置：

```text
rule_based/build_medicalgraph.py
```

`build_medicalgraph.py` 负责把 `data/medical.json` 中的结构化医疗数据导入 Neo4j，构建医疗知识图谱。

它的核心作用是：

```text
读取 data/medical.json
  -> 提取疾病、症状、药品、食物、检查、科室、生产商等实体
  -> 提取实体之间的关系
  -> 在 Neo4j 中创建节点
  -> 在 Neo4j 中创建关系
  -> 形成医疗知识图谱
```

## 1. 整体定位

在整个项目中，`build_medicalgraph.py` 属于图谱构建层。

规则版问答系统要能回答问题，前提是 Neo4j 里已经有图谱数据。

整体流程是：

```text
data/medical.json
  -> build_medicalgraph.py
  -> Neo4j 医疗知识图谱
  -> chatbot_graph.py 问答查询
```

所以这个文件通常在问答系统启动前执行。

## 2. 输入和输出

输入数据：

```text
data/medical.json
```

输出结果：

```text
Neo4j 中的节点和关系
```

主要节点类型：

```text
Disease
Symptom
Drug
Food
Check
Department
Producer
```

主要关系类型：

```text
has_symptom
acompany_with
no_eat
do_eat
recommand_eat
common_drug
recommand_drug
need_check
drugs_of
belongs_to
```

## 3. 初始化 Neo4j 连接

核心类是：

```python
class MedicalGraph:
```

初始化代码：

```python
def __init__(self):
    cur_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    self.data_path = os.path.join(cur_dir, 'data/medical.json')
    self.g = Graph("bolt://127.0.0.1:7687", auth=("neo4j", "12341234"))
```

这里做了两件事：

```text
1. 定位 data/medical.json
2. 连接 Neo4j
```

当前 Neo4j 配置是：

```text
地址：bolt://127.0.0.1:7687
用户名：neo4j
密码：12341234
```

如果你的 Neo4j 密码不是 `12341234`，需要修改这里。

## 4. read_nodes 的作用

`read_nodes()` 是这个文件里最核心的函数。

它的作用是：

```text
读取 medical.json
  -> 提取所有节点集合
  -> 提取所有关系列表
  -> 提取 Disease 节点属性
```

函数开头先准备节点集合：

```python
drugs = []
foods = []
checks = []
departments = []
producers = []
diseases = []
symptoms = []

disease_infos = []
```

这些列表分别保存不同类型的节点。

然后准备关系列表：

```python
rels_department = []
rels_noteat = []
rels_doeat = []
rels_recommandeat = []
rels_commonddrug = []
rels_recommanddrug = []
rels_check = []
rels_drug_producer = []
rels_symptom = []
rels_acompany = []
rels_category = []
```

这些列表保存实体之间的边。

## 5. 读取 medical.json

核心循环：

```python
for data in open(self.data_path, encoding='utf-8'):
    disease_dict = {}
    data_json = json.loads(data)
    disease = data_json['name']
```

`medical.json` 是一行一个 JSON 对象。

每一行大致表示一种疾病的信息，例如：

```python
{
    "name": "感冒",
    "desc": "...",
    "cause": "...",
    "symptom": ["流鼻涕", "咳嗽"],
    "common_drug": ["板蓝根颗粒"],
    "check": ["血常规"]
}
```

代码会逐行解析，先取出疾病名称：

```python
disease = data_json['name']
diseases.append(disease)
```

然后创建疾病属性字典：

```python
disease_dict['name'] = disease
disease_dict['desc'] = ''
disease_dict['prevent'] = ''
disease_dict['cause'] = ''
disease_dict['easy_get'] = ''
disease_dict['cure_department'] = ''
disease_dict['cure_way'] = ''
disease_dict['cure_lasttime'] = ''
disease_dict['symptom'] = ''
disease_dict['cured_prob'] = ''
```

这些字段后面会作为 `Disease` 节点的属性。

## 6. 提取疾病属性

如果 JSON 中存在某个字段，就写入 `disease_dict`。

例如疾病描述：

```python
if 'desc' in data_json:
    disease_dict['desc'] = data_json['desc']
```

疾病预防：

```python
if 'prevent' in data_json:
    disease_dict['prevent'] = data_json['prevent']
```

疾病原因：

```python
if 'cause' in data_json:
    disease_dict['cause'] = data_json['cause']
```

治疗方式：

```python
if 'cure_way' in data_json:
    disease_dict['cure_way'] = data_json['cure_way']
```

最终这些属性会写入 Neo4j 的 `Disease` 节点。

## 7. 提取实体关系

`read_nodes()` 不只是提取节点，还会提取关系。

### 7.1 疾病和症状

代码：

```python
if 'symptom' in data_json:
    symptoms += data_json['symptom']
    for symptom in data_json['symptom']:
        rels_symptom.append([disease, symptom])
```

含义是：

```text
疾病 -> 症状
```

对应 Neo4j 关系：

```text
(Disease)-[:has_symptom]->(Symptom)
```

### 7.2 疾病和并发症

代码：

```python
if 'acompany' in data_json:
    for acompany in data_json['acompany']:
        rels_acompany.append([disease, acompany])
```

对应关系：

```text
(Disease)-[:acompany_with]->(Disease)
```

### 7.3 疾病和科室

代码会根据 `cure_department` 判断一级或二级科室：

```python
if len(cure_department) == 1:
    rels_category.append([disease, cure_department[0]])
if len(cure_department) == 2:
    big = cure_department[0]
    small = cure_department[1]
    rels_department.append([small, big])
    rels_category.append([disease, small])
```

这里会产生两类关系：

```text
小科室 -> 大科室
疾病 -> 科室
```

关系类型都是：

```text
belongs_to
```

### 7.4 疾病和药品

常用药：

```python
if 'common_drug' in data_json:
    common_drug = data_json['common_drug']
    for drug in common_drug:
        rels_commonddrug.append([disease, drug])
    drugs += common_drug
```

推荐药：

```python
if 'recommand_drug' in data_json:
    recommand_drug = data_json['recommand_drug']
    drugs += recommand_drug
    for drug in recommand_drug:
        rels_recommanddrug.append([disease, drug])
```

对应关系：

```text
Disease - common_drug -> Drug
Disease - recommand_drug -> Drug
```

### 7.5 疾病和饮食

忌吃：

```python
rels_noteat.append([disease, _not])
```

宜吃：

```python
rels_doeat.append([disease, _do])
```

推荐食谱：

```python
rels_recommandeat.append([disease, _recommand])
```

对应关系：

```text
Disease - no_eat -> Food
Disease - do_eat -> Food
Disease - recommand_eat -> Food
```

### 7.6 疾病和检查项目

代码：

```python
if 'check' in data_json:
    check = data_json['check']
    for _check in check:
        rels_check.append([disease, _check])
    checks += check
```

对应关系：

```text
Disease - need_check -> Check
```

### 7.7 生产商和药品

代码：

```python
if 'drug_detail' in data_json:
    drug_detail = data_json['drug_detail']
    producer = [i.split('(')[0] for i in drug_detail]
    rels_drug_producer += [
        [i.split('(')[0], i.split('(')[-1].replace(')', '')]
        for i in drug_detail
    ]
    producers += producer
```

这里会从类似：

```text
通药制药(青霉素V钾片)
```

拆出：

```text
Producer: 通药制药
Drug: 青霉素V钾片
```

对应关系：

```text
Producer - drugs_of -> Drug
```

## 8. read_nodes 的返回结果

最后返回很多集合和关系列表：

```python
return set(drugs), set(foods), set(checks), set(departments), set(producers), set(symptoms), set(diseases), disease_infos, \
       rels_check, rels_recommandeat, rels_noteat, rels_doeat, rels_department, rels_commonddrug, rels_drug_producer, rels_recommanddrug, \
       rels_symptom, rels_acompany, rels_category
```

这里 `set()` 的作用是去重。

可以理解为：

```text
前半部分：节点集合
后半部分：关系列表
```

## 9. 创建普通节点

函数：

```python
def create_node(self, label, nodes):
    count = 0
    for node_name in nodes:
        node = Node(label, name=node_name)
        self.g.create(node)
        count += 1
        print(count, len(nodes))
```

它用于创建普通实体节点。

例如：

```python
self.create_node('Drug', Drugs)
self.create_node('Food', Foods)
self.create_node('Check', Checks)
self.create_node('Department', Departments)
self.create_node('Producer', Producers)
self.create_node('Symptom', Symptoms)
```

这些节点只有一个核心属性：

```text
name
```

## 10. 创建 Disease 节点

疾病节点比较特殊，因为它除了 `name`，还包含很多属性。

函数：

```python
def create_diseases_nodes(self, disease_infos):
```

核心代码：

```python
node = Node(
    "Disease",
    name=disease_dict['name'],
    desc=disease_dict['desc'],
    prevent=disease_dict['prevent'],
    cause=disease_dict['cause'],
    easy_get=disease_dict['easy_get'],
    cure_lasttime=disease_dict['cure_lasttime'],
    cure_department=disease_dict['cure_department'],
    cure_way=disease_dict['cure_way'],
    cured_prob=disease_dict['cured_prob']
)
```

所以 `Disease` 节点会包含：

```text
name
desc
prevent
cause
easy_get
cure_lasttime
cure_department
cure_way
cured_prob
```

这些属性后面会被问答系统查询，例如：

```text
为什么会得高血压？ -> cause
怎么预防高血压？ -> prevent
高血压怎么治疗？ -> cure_way
```

## 11. create_graphnodes 的作用

函数：

```python
def create_graphnodes(self):
```

它负责创建所有节点。

流程是：

```text
1. 调用 read_nodes() 读取数据
2. 创建 Disease 节点
3. 创建 Drug 节点
4. 创建 Food 节点
5. 创建 Check 节点
6. 创建 Department 节点
7. 创建 Producer 节点
8. 创建 Symptom 节点
```

对应代码：

```python
self.create_diseases_nodes(disease_infos)
self.create_node('Drug', Drugs)
self.create_node('Food', Foods)
self.create_node('Check', Checks)
self.create_node('Department', Departments)
self.create_node('Producer', Producers)
self.create_node('Symptom', Symptoms)
```

注意：创建关系之前必须先创建节点，否则关系无法正确挂载到节点上。

## 12. create_graphrels 的作用

函数：

```python
def create_graphrels(self):
```

它负责创建所有关系。

核心代码：

```python
self.create_relationship('Disease', 'Food', rels_recommandeat, 'recommand_eat', '推荐食谱')
self.create_relationship('Disease', 'Food', rels_noteat, 'no_eat', '忌吃')
self.create_relationship('Disease', 'Food', rels_doeat, 'do_eat', '宜吃')
self.create_relationship('Department', 'Department', rels_department, 'belongs_to', '属于')
self.create_relationship('Disease', 'Drug', rels_commonddrug, 'common_drug', '常用药品')
self.create_relationship('Producer', 'Drug', rels_drug_producer, 'drugs_of', '生产药品')
self.create_relationship('Disease', 'Drug', rels_recommanddrug, 'recommand_drug', '好评药品')
self.create_relationship('Disease', 'Check', rels_check, 'need_check', '诊断检查')
self.create_relationship('Disease', 'Symptom', rels_symptom, 'has_symptom', '症状')
self.create_relationship('Disease', 'Disease', rels_acompany, 'acompany_with', '并发症')
self.create_relationship('Disease', 'Department', rels_category, 'belongs_to', '所属科室')
```

这一步会把节点真正连成图。

## 13. create_relationship 的作用

函数：

```python
def create_relationship(self, start_node, end_node, edges, rel_type, rel_name):
```

参数含义：

| 参数 | 含义 |
| --- | --- |
| `start_node` | 起点节点标签 |
| `end_node` | 终点节点标签 |
| `edges` | 关系列表，例如 `[疾病, 症状]` |
| `rel_type` | Neo4j 关系类型 |
| `rel_name` | 关系中文名称，写入关系属性 `name` |

函数先对边去重：

```python
set_edges = []
for edge in edges:
    set_edges.append('###'.join(edge))
all = len(set(set_edges))
```

然后生成 Cypher：

```python
query = "match(p:%s),(q:%s) where p.name='%s'and q.name='%s' create (p)-[rel:%s{name:'%s'}]->(q)" % (
    start_node, end_node, p, q, rel_type, rel_name)
```

例如：

```python
start_node = "Disease"
end_node = "Symptom"
p = "感冒"
q = "流鼻涕"
rel_type = "has_symptom"
rel_name = "症状"
```

生成：

```cypher
match(p:Disease),(q:Symptom)
where p.name='感冒'and q.name='流鼻涕'
create (p)-[rel:has_symptom{name:'症状'}]->(q)
```

## 14. clear_graph 的作用

函数：

```python
def clear_graph(self):
    self.g.run("MATCH (n) DETACH DELETE n")
```

它会清空 Neo4j 中所有节点和关系。

执行：

```cypher
MATCH (n) DETACH DELETE n
```

含义是：

```text
删除所有节点
同时删除这些节点上的所有关系
```

这是一个危险操作。如果数据库里还有其他项目的数据，不要直接执行。

当前入口里默认会执行：

```python
handler.clear_graph()
```

所以运行建图脚本前要确认当前 Neo4j 数据库可以被清空。

## 15. export_data 的作用

函数：

```python
def export_data(self):
```

它会把 `read_nodes()` 提取出的实体词导出为文本文件：

```text
drug.txt
food.txt
check.txt
department.txt
producer.txt
symptoms.txt
disease.txt
```

这些词典可以用于 `QuestionClassifier` 的实体识别。

不过当前项目已经有 `dict/` 目录，所以一般不需要重新执行这个函数。

## 16. 程序入口

代码：

```python
if __name__ == '__main__':
    handler = MedicalGraph()
    handler.clear_graph()
    print("step1:导入图谱节点中")
    handler.create_graphnodes()
    print("step2:导入图谱边中")
    handler.create_graphrels()
```

执行顺序是：

```text
1. 连接 Neo4j
2. 清空已有图谱
3. 创建节点
4. 创建关系
```

启动方式：

```bash
python rule_based/build_medicalgraph.py
```

或者：

```bash
python -m rule_based.build_medicalgraph
```

注意：导入数据量比较大，执行时间可能较长。

## 17. 一个完整例子

假设 `medical.json` 中有一条疾病数据：

```python
{
    "name": "感冒",
    "symptom": ["流鼻涕", "咳嗽"],
    "common_drug": ["板蓝根颗粒"],
    "check": ["血常规"],
    "not_eat": ["辣椒"],
    "do_eat": ["苹果"],
    "recommand_eat": ["姜汤"]
}
```

`read_nodes()` 会提取节点：

```text
Disease: 感冒
Symptom: 流鼻涕、咳嗽
Drug: 板蓝根颗粒
Check: 血常规
Food: 辣椒、苹果、姜汤
```

也会提取关系：

```text
感冒 - has_symptom -> 流鼻涕
感冒 - has_symptom -> 咳嗽
感冒 - common_drug -> 板蓝根颗粒
感冒 - need_check -> 血常规
感冒 - no_eat -> 辣椒
感冒 - do_eat -> 苹果
感冒 - recommand_eat -> 姜汤
```

然后 `create_graphnodes()` 创建节点，`create_graphrels()` 创建关系。

最终 Neo4j 中就有了可以被问答系统查询的图谱。

## 18. 这个模块的特点

优点：

```text
数据处理流程直观
图谱 schema 清晰
节点和关系构建逻辑集中
和后续问答查询模板对应明确
```

缺点：

```text
导入速度较慢
数据库连接参数写死
create_relationship 使用字符串拼接 Cypher
clear_graph 默认清空数据库，需要谨慎
read_nodes 会被 create_graphnodes 和 create_graphrels 各调用一次，重复读取数据
```

## 19. 和问答模块的关系

`build_medicalgraph.py` 构建的是问答系统查询的底层数据。

例如它创建了：

```text
Disease - has_symptom -> Symptom
```

后面 `question_parser.py` 才能生成：

```cypher
MATCH (m:Disease)-[r:has_symptom]->(n:Symptom)
where m.name = '乳腺癌'
return m.name, r.name, n.name
```

也就是说：

```text
build_medicalgraph.py 决定图谱里有什么
question_parser.py 决定问答时怎么查
answer_search.py 决定查完后怎么回答
```

## 20. 和 LLM 分支的关系

LLM 分支也使用同一个 Neo4j 图谱。

也就是说，`build_medicalgraph.py` 构建出的图谱同时服务于：

```text
rule_based/
llm_based/
```

区别是：

```text
rule_based：使用固定 question_type 查询模板
llm_based：使用 LLM 查询计划和 CypherBuilder 生成查询
```

但它们共享同一套图谱 schema。

## 21. 总结

`build_medicalgraph.py` 的作用可以概括为：

```text
把 data/medical.json 中的医疗结构化数据导入 Neo4j，构建疾病中心的医疗知识图谱
```

它是整个项目的基础层。没有这一步，后面的规则版问答和 LLM 版问答都没有可查询的图谱数据。
