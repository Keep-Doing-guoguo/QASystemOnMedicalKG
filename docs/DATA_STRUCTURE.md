# 数据结构示意图

下面是 README 中的数据结构总结，包含实体、关系、属性，并附结构图。

## 实体类型（全部）

- Disease（疾病）
- Symptom（症状）
- Drug（药品）
- Food（食物）
- Check（检查）
- Department（科室）
- Producer（厂商）

## 关系类型（全部）

- `belongs_to`：Department → Department（科室从属）
- `belongs_to`：Disease → Department（疾病所属科室）
- `has_symptom`：Disease → Symptom
- `common_drug`：Disease → Drug
- `recommand_drug`：Disease → Drug
- `drugs_of`：Producer → Drug
- `need_check`：Disease → Check
- `do_eat`：Disease → Food
- `no_eat`：Disease → Food
- `recommand_eat`：Disease → Food
- `acompany_with`：Disease → Disease

## 节点属性（全部）

所有节点都有：
- `name`

Disease 额外属性：
- `desc`
- `prevent`
- `cause`
- `easy_get`
- `cure_department`
- `cure_way`
- `cure_lasttime`
- `symptom`
- `cured_prob`
- `get_prob`

## 关系属性（全部）

所有关系都有：
- `name`

## 结构图（纯文本）

```
                         (Symptom)
                            ^
                            | has_symptom
                            |
(Food) <-do_eat/no_eat/recommand_eat- (Disease) -common_drug/recommand_drug-> (Drug) <-drugs_of- (Producer)
                            |
                            | need_check
                            v
                         (Check)
                            |
                            | belongs_to
                            v
                        (Department)
                            ^
                            | belongs_to
                        (Department)

(Disease) -acompany_with-> (Disease)
```

## medical.json 字段（单条记录）

```
medical.json 单行记录
├─ name / desc / cause / prevent
├─ symptom                 (症状列表)
├─ check                   (检查列表)
├─ cure_department         (科室列表)
├─ cure_way                (治疗方式)
├─ cure_lasttime           (疗程)
├─ cured_prob              (治愈率)
├─ common_drug             (常用药品)
├─ recommand_drug          (推荐药品)
├─ drug_detail             (药品详情/厂商)
├─ not_eat / do_eat / recommand_eat (饮食建议)
├─ acompany                (并发症)
└─ easy_get / get_prob / get_way / yibao_status / cost_money
```

## 问答类型 → 图谱映射（详细）

以下映射来自 `question_parser.py` 的查询模板，体现了“问答类型”与“关系/属性”的对应：

- `disease_symptom`  
  关系：`(Disease)-[:has_symptom]->(Symptom)`  
  返回：`Symptom.name`

- `symptom_disease`  
  关系：`(Disease)-[:has_symptom]->(Symptom)`  
  返回：`Disease.name`

- `disease_acompany`  
  关系：`(Disease)-[:acompany_with]->(Disease)`（双向查询）  
  返回：`Disease.name`

- `disease_not_food`  
  关系：`(Disease)-[:no_eat]->(Food)`  
  返回：`Food.name`

- `disease_do_food`  
  关系：`(Disease)-[:do_eat]->(Food)` + `(Disease)-[:recommand_eat]->(Food)`  
  返回：`Food.name`

- `food_not_disease`  
  关系：`(Disease)-[:no_eat]->(Food)`  
  返回：`Disease.name`

- `food_do_disease`  
  关系：`(Disease)-[:do_eat]->(Food)` + `(Disease)-[:recommand_eat]->(Food)`  
  返回：`Disease.name`

- `disease_drug`  
  关系：`(Disease)-[:common_drug]->(Drug)` + `(Disease)-[:recommand_drug]->(Drug)`  
  返回：`Drug.name`

- `drug_disease`  
  关系：`(Disease)-[:common_drug]->(Drug)` + `(Disease)-[:recommand_drug]->(Drug)`  
  返回：`Disease.name`

- `disease_check`  
  关系：`(Disease)-[:need_check]->(Check)`  
  返回：`Check.name`

- `check_disease`  
  关系：`(Disease)-[:need_check]->(Check)`  
  返回：`Disease.name`

- `disease_cause`  
  属性：`Disease.cause`

- `disease_prevent`  
  属性：`Disease.prevent`

- `disease_lasttime`  
  属性：`Disease.cure_lasttime`

- `disease_cureway`  
  属性：`Disease.cure_way`

- `disease_cureprob`  
  属性：`Disease.cured_prob`

- `disease_easyget`  
  属性：`Disease.easy_get`

- `disease_desc`  
  属性：`Disease.desc`

## KG 映射图（字段 → 节点/关系）

```
medical.json 字段
├─ name/desc/cause/prevent/...
│     └─ Disease 节点属性
├─ symptom
│     └─ (Disease)-[:has_symptom]->(Symptom)
├─ acompany
│     └─ (Disease)-[:acompany_with]->(Disease)
├─ check
│     └─ (Disease)-[:need_check]->(Check)
├─ cure_department
│     ├─ (Disease)-[:belongs_to]->(Department)
│     └─ (Department)-[:belongs_to]->(Department)
├─ common_drug
│     └─ (Disease)-[:common_drug]->(Drug)
├─ recommand_drug
│     └─ (Disease)-[:recommand_drug]->(Drug)
├─ not_eat / do_eat / recommand_eat
│     ├─ (Disease)-[:no_eat]->(Food)
│     ├─ (Disease)-[:do_eat]->(Food)
│     └─ (Disease)-[:recommand_eat]->(Food)
└─ drug_detail
      └─ (Producer)-[:drugs_of]->(Drug)
```

如果你需要“字段 → 节点/关系”的映射图，我可以再补一张 KG 映射图。  
