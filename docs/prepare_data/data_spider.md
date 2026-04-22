# data_spider.py 讲解

## 1. 这个文件是做什么的

`data_spider.py` 是 `prepare_data` 目录中负责采集原始医疗数据的核心脚本。

它主要完成这些工作：

1. 根据疾病编号拼接网页地址
2. 请求网页 HTML
3. 解析疾病的多个页面
4. 把结果保存到 MongoDB

简单说，这个文件做的是：**从网页抓原始数据，并存入数据库**。

---

## 2. 这个文件里用到的库

### `urllib.request`

用于发送 HTTP 请求，获取网页源码。

### `urllib.parse`

通常用于 URL 解析和编码。  
这个文件中导入了它，但当前代码没有实际使用。

### `lxml.etree`

用于解析 HTML 页面，并通过 XPath 提取目标内容。

### `pymongo`

用于把抓取到的数据写入 MongoDB。

### `re`

正则表达式库。当前文件里虽然导入了，但并没有真正使用。

---

## 3. 类和函数是做什么的

### 类：`CrimeSpider`

这个类负责整个网页抓取流程。  
虽然类名叫 `CrimeSpider`，但这个项目里实际抓取的是医疗数据，属于旧代码命名遗留。

### 类中的函数

#### `__init__()`

初始化数据库连接。

#### `get_html(url)`

根据网址抓取网页 HTML。

#### `url_parser(content)`

从 HTML 中解析链接。这个函数当前主流程没有使用。

#### `spider_main()`

主抓取流程。遍历疾病编号，分别抓取不同类型的页面。

#### `basicinfo_spider(url)`

抓取疾病基本信息。

#### `treat_spider(url)`

抓取治疗相关信息。

#### `drug_spider(url)`

抓取药品信息。

#### `food_spider(url)`

抓取饮食信息。

#### `symptom_spider(url)`

抓取症状信息。

#### `inspect_spider(url)`

抓取检查项链接。

#### `common_spider(url)`

通用页面解析函数，主要用于病因和预防等结构相似页面。

#### `inspect_crawl()`

抓取检查项详情页 HTML，并保存到 MongoDB。

---

## 4. 按代码顺序讲解

```python
import urllib.request
import urllib.parse
from lxml import etree
import pymongo
import re
```

导入程序所需的库。

```python
class CrimeSpider:
```

定义爬虫类。

```python
    def __init__(self):
        self.conn = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
        self.db = self.conn['medical']
        self.col = self.db['data']
```

初始化时完成数据库连接：

1. 连接本地 MongoDB
2. 选择 `medical` 数据库
3. 选择 `data` 集合

```python
    def get_html(self, url):
```

定义抓网页函数。

```python
        headers = {'User-Agent': 'Mozilla/5.0 ...'}
```

设置请求头，模拟浏览器，减少被网站拦截的概率。

```python
        req = urllib.request.Request(url=url, headers=headers)
```

构造请求对象。

```python
        res = urllib.request.urlopen(req)
```

发送请求，拿到响应。

```python
        html = res.read().decode('gbk')
```

读取响应并用 `gbk` 解码。  
这说明目标网站页面编码是 `gbk`。

```python
        return html
```

返回 HTML 文本。

```python
    def url_parser(self, content):
```

定义 URL 解析函数。

```python
        selector = etree.HTML(content)
        urls = ['http://www.anliguan.com' + i for i in selector.xpath('//h2[@class="item-title"]/a/@href')]
        return urls
```

这个函数本来是从 HTML 中提取链接，但当前医疗项目的主流程里并没有真正使用它，而且域名也不是当前站点，可以视为遗留代码。

```python
    def spider_main(self):
```

主抓取流程开始。

```python
        for page in range(2266, 11000):
```

遍历疾病编号。  
作者通过编号来构造不同疾病的页面地址。

```python
            try:
```

对每个页面做异常保护，避免某一页失败后整个程序中断。

```python
                basic_url = 'http://jib.xywy.com/il_sii/gaishu/%s.htm'%page
                cause_url = 'http://jib.xywy.com/il_sii/cause/%s.htm'%page
                prevent_url = 'http://jib.xywy.com/il_sii/prevent/%s.htm'%page
                symptom_url = 'http://jib.xywy.com/il_sii/symptom/%s.htm'%page
                inspect_url = 'http://jib.xywy.com/il_sii/inspect/%s.htm'%page
                treat_url = 'http://jib.xywy.com/il_sii/treat/%s.htm'%page
                food_url = 'http://jib.xywy.com/il_sii/food/%s.htm'%page
                drug_url = 'http://jib.xywy.com/il_sii/drug/%s.htm'%page
```

同一个疾病编号，会对应多个专题页面：

1. 概述
2. 病因
3. 预防
4. 症状
5. 检查
6. 治疗
7. 饮食
8. 药品

这说明作者是通过多个页面拼装一个完整疾病对象。

```python
                data = {}
                data['url'] = basic_url
```

初始化一个字典保存疾病数据，并记录基础页面地址。

```python
                data['basic_info'] = self.basicinfo_spider(basic_url)
                data['cause_info'] = self.common_spider(cause_url)
                data['prevent_info'] = self.common_spider(prevent_url)
                data['symptom_info'] = self.symptom_spider(symptom_url)
                data['inspect_info'] = self.inspect_spider(inspect_url)
                data['treat_info'] = self.treat_spider(treat_url)
                data['food_info'] = self.food_spider(food_url)
                data['drug_info'] = self.drug_spider(drug_url)
```

调用不同函数解析不同页面内容。

```python
                print(page, basic_url)
```

打印当前抓取进度。

```python
                self.col.insert_one(data)
```

将抓到的这条疾病数据写入 MongoDB。

```python
            except Exception as e:
                print(e, page)
```

如果抓某一页失败，就打印错误和页码。

### `basicinfo_spider(url)`

```python
    def basicinfo_spider(self, url):
```

定义疾病基本信息解析函数。

```python
        html = self.get_html(url)
        selector = etree.HTML(html)
```

先抓网页，再解析 HTML。

```python
        title = selector.xpath('//title/text()')[0]
```

取页面标题。

```python
        category = selector.xpath('//div[@class="wrap mt10 nav-bar"]/a/text()')
```

提取疾病分类。

```python
        desc = selector.xpath('//div[@class="jib-articl-con jib-lh-articl"]/p/text()')
```

提取疾病简介。

```python
        ps = selector.xpath('//div[@class="mt20 articl-know"]/p')
```

取包含属性信息的段落。

```python
        infobox = []
        for p in ps:
            info = p.xpath('string(.)').replace('\r','').replace('\n','').replace('\xa0', '').replace('   ', '').replace('\t','')
            infobox.append(info)
```

逐段清洗文本并保存。

```python
        basic_data = {}
        basic_data['category'] = category
        basic_data['name'] = title.split('的简介')[0]
        basic_data['desc'] = desc
        basic_data['attributes'] = infobox
        return basic_data
```

把疾病基本信息组织成字典返回。

### `treat_spider(url)`

```python
    def treat_spider(self, url):
```

解析治疗页面。

```python
        ps = selector.xpath('//div[starts-with(@class,"mt20 articl-know")]/p')
```

定位治疗信息区域。

```python
        infobox = []
        for p in ps:
            info = p.xpath('string(.)').replace(...)
            infobox.append(info)
        return infobox
```

逐段抽取并清洗文本，最终返回治疗信息列表。

### `drug_spider(url)`

```python
    def drug_spider(self, url):
```

解析药品页面。

```python
        drugs = [i.replace('\n','').replace('\t', '').replace(' ','') for i in selector.xpath('//div[@class="fl drug-pic-rec mr30"]/p/a/text()')]
```

用 XPath 抽取药品名，然后去掉多余空白字符。

### `food_spider(url)`

```python
    def food_spider(self, url):
```

解析饮食页面。

```python
        divs = selector.xpath('//div[@class="diet-img clearfix mt20"]')
```

找到饮食信息区域。

```python
        try:
            food_data = {}
            food_data['good'] = divs[0].xpath('./div/p/text()')
            food_data['bad'] = divs[1].xpath('./div/p/text()')
            food_data['recommand'] = divs[2].xpath('./div/p/text()')
        except:
            return {}
```

分别获取：

1. 宜食
2. 忌食
3. 推荐食谱

如果页面结构不完整，就返回空字典。

### `symptom_spider(url)`

```python
    def symptom_spider(self, url):
```

解析症状页面。

```python
        symptoms = selector.xpath('//a[@class="gre" ]/text()')
```

提取症状词列表。

```python
        ps = selector.xpath('//p')
```

取页面中的所有段落。

```python
        detail = []
        for p in ps:
            info = p.xpath('string(.)').replace(...)
            detail.append(info)
```

提取症状详情文本。

```python
        symptoms_data = {}
        symptoms_data['symptoms'] = symptoms
        symptoms_data['symptoms_detail'] = detail
        return symptoms, detail
```

这里定义了 `symptoms_data`，但并没有返回它，最后返回的是一个元组。  
这是讲课时可以指出的代码一致性问题。

### `inspect_spider(url)`

```python
    def inspect_spider(self, url):
```

解析检查页面。

```python
        inspects = selector.xpath('//li[@class="check-item"]/a/@href')
        return inspects
```

返回检查项 URL 列表。

### `common_spider(url)`

```python
    def common_spider(self, url):
```

通用页面解析函数。

```python
        ps = selector.xpath('//p')
```

提取页面中的所有段落。

```python
        infobox = []
        for p in ps:
            info = p.xpath('string(.)').replace(...)
            if info:
                infobox.append(info)
```

清洗段落内容，并过滤空字符串。

```python
        return '\n'.join(infobox)
```

将多个段落合并为一个字符串返回。

### `inspect_crawl()`

```python
    def inspect_crawl(self):
```

抓检查项详情页。

```python
        for page in range(1, 3685):
```

遍历检查项编号。

```python
                url = 'http://jck.xywy.com/jc_%s.html'%page
                html = self.get_html(url)
```

构造 URL 并抓取 HTML。

```python
                data = {}
                data['url']= url
                data['html'] = html
```

保存页面地址和网页源码。

```python
                self.db['jc'].insert_one(data)
```

写入 MongoDB 的 `jc` 集合。

### 文件结尾

```python
handler = CrimeSpider()
#handler.inspect_crawl()
handler.spider_main()
```

这里表示默认执行 `spider_main()`，也就是抓取疾病页面。  
如果要抓检查项详情页，可以把 `inspect_crawl()` 打开。

---

## 5. 课堂总结

你可以把这个文件总结成一句话：

`data_spider.py` 负责从网页抓取多个维度的疾病信息，然后把它们合并成一条原始记录保存到 MongoDB。

讲课时可以特别强调三点：

1. 一个疾病对应多个网页，不是单页采集
2. `lxml + XPath` 是网页结构化抽取的核心工具
3. 这个脚本抓到的是“原始结构化数据”，还不是最终图谱数据
