安装neo4j数据库


0.理解数据

这个主要是spider_main的数据内容

数据是从这里面一步一步爬出来的，这个是主页面的信息；
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/1-主页面.png "Magic Gardens")

然后再从主页信息中的每个疾病的链接，爬取每个疾病的详细信息；下面这个是单独的一个疾病信息

![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/2-举例一个.png "Magic Gardens")
这个是举例的一个链接
https://jib.xywy.com/il_sii/gaishu/9748.htm

下面主要是检查想模块数据的主要抓取内容；

举例的链接
http://jck.xywy.com/jc_79.html

这个是第一步的数据展示
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/3-检查项目.png "Magic Gardens")

具体展示
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/4-检查项目举例.png "Magic Gardens")

data['basic_info'] = self.basicinfo_spider(basic_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/basicinfo_spider.png "Magic Gardens")

![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/basciinfo.png "Magic Gardens")

data['cause_info'] =  self.common_spider(cause_url)na拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/cause_info.png "Magic Gardens")

data['prevent_info'] =  self.common_spider(prevent_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/prevent_info.png "Magic Gardens")

data['symptom_info'] =  self.common_spider(symptom_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/symptom_info.png "Magic Gardens")

data['inspect_info'] =  self.common_spider(inspect_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/inspect_info.png "Magic Gardens")
data['treat_info'] =  self.common_spider(treat_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/treat_info.png "Magic Gardens")
data['food_info'] =  self.check_spider(food_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/food_info.png "Magic Gardens")
data['drug_info'] = self.drug_spider(drug_url)拿到的信息是：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/drug_info.png "Magic Gardens")

代码解析的数据为：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/解析数据为.png "Magic Gardens")


schema信息为：
![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/attributes.png "Magic Gardens")

![这是图片](/Volumes/PSSD/未命名文件夹/QASystemOnMedicalKG-master/images_md_zgw/schema.png "Magic Gardens")

最后basic会作为diease的schema的信息存放；cause、prevent、symptom、inspect、traet、food、drug、producers都将会作为节点存放。在数据处理的时候，会将其进行去重存放；
其中疾病的schema的信息都有：


疾病和检查
疾病和部门
疾病和药品（推荐药品、不推荐药品）
疾病和食物（不吃食物、吃食物、推荐食物）
疾病和症状

药品和生产商
科室和科室
比如：
| 科室A   | 关系   | 科室B       |
|--------|--------|------------|
| 妇产科 | 包含   | 妇科       |
| 妇产科 | 包含   | 产科       |
| 外科   | 包含   | 心胸外科   |
| 外科   | 包含   | 普外科     |

diease会和food建立边关系，名称为：rels_noteat、rels_doeat、rels_recommandeat
diease会和drug建立边关系，名称为：rels_commonddrug、rels_recommanddrug
diease会和insepect建立边关系，名称为：rels_check
diease会和symptom建立边关系，名称为：rels_symptom
diease会和category（科室）建立边关系，名称为：rels_category
diease会和acompany（并发证）建立边关系，名称为：rels_acompany


drugs会和producers建立边关系，名称为：rels_drug_producer
department和department建立边关系，名称为：rels_department


1.这个 build_data.py 代码，其实是把你前面爬虫采集到的原始数据（MongoDB 里 medical.data 集合）进行结构化清洗，重新组织成知识图谱需要的标准格式，然后再存回 MongoDB。

#https://github.com/Keep-Doing-guoguo/QASystemOnMedicalKG.git

作用总结

整个 build_data.py 脚本的作用是：

	1.	输入：前面爬虫 (data_spider.py) 存在 medical.data 里的原始 HTML 解析结果
	2.	处理：字段提取 → 清洗 → 标准化 key → 去停用词 → 分词 → 关联检查信息
	3.	输出：清洗好的、结构化的疾病数据，存到 medical.medical 集合
	4.	这些数据就能直接作为 知识图谱构建 或 问答系统 的知识库来源


2.data_spider.py代码，先单独跑一次 inspect_crawl()，把每个检查页面的 HTML 缓存到 medical.jc；→ 再跑 spider_main()。

if __name__ == '__main__':
    handler = MedicalGraph()
    handler.modify_jc()        # 先解析检查项名称/描述
    handler.collect_medical()  # 再清洗疾病数据入库 medical

3.max_cut.py 前后、双向分词；

4.answer_search.py 

5.build_medicalgraph.py 将数据信息导入到知识图谱 Neo4j 中。

6.chatbot_graph.py 将问题分类，然后对问题进行解析；最后再回答问题；

7.question_classifier.py 问题分类；

8.question_parser.py 问题解析；



