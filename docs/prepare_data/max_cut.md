# max_cut.py 讲解

## 1. 这个文件是做什么的

`max_cut.py` 实现了一个基于词典的中文分词模块，采用的是“最大匹配”思想。

它主要提供三种分词方式：

1. 正向最大匹配
2. 逆向最大匹配
3. 双向最大匹配

这个文件的意义在于：当我们已经有一个领域词典时，就可以用词典去切分文本。

---

## 2. 这个文件里用到的库

### `os`

用于定位词典文件路径。

在这个文件里，它的作用是找到：

`dict/disease.txt`

这个疾病词典文件。

---

## 3. 类和函数是做什么的

### 类：`CutWords`

这个类负责加载词典并执行分词。

### 类中的函数

#### `__init__()`

初始化词典。

#### `load_words(dict_path)`

从文件中读取词典，并记录最大词长。

#### `max_forward_cut(sent)`

执行正向最大匹配分词。

#### `max_backward_cut(sent)`

执行逆向最大匹配分词。

#### `max_biward_cut(sent)`

比较正向和逆向结果，选出更优切分结果。

---

## 4. 按代码顺序讲解

```python
import os
```

导入路径处理库。

```python
class CutWords:
```

定义分词类。

```python
    def __init__(self):
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        dict_path = os.path.join(os.path.dirname(cur_dir), 'dict', 'disease.txt')
        self.word_dict, self.max_wordlen = self.load_words(dict_path)
```

初始化时完成三件事：

1. 获取当前脚本所在目录
2. 拼出疾病词典文件路径
3. 调用 `load_words()` 加载词典和最大词长

### `load_words(dict_path)`

```python
    def load_words(self, dict_path):
```

定义读取词典的函数。

```python
        words = list()
        max_len = 0
```

初始化词列表和最大词长。

```python
        for line in open(dict_path, encoding='utf-8'):
```

逐行读取词典文件。

```python
            wd = line.strip()
            if not wd:
                continue
```

去掉空白字符，并跳过空行。

```python
            if len(wd) > max_len:
                max_len = len(wd)
```

记录当前最长词的长度。

```python
            words.append(wd)
```

把词加入词典列表。

```python
        return words, max_len
```

返回：

1. 词典列表
2. 最大词长

### `max_forward_cut(sent)`

```python
    def max_forward_cut(self, sent):
```

定义正向最大匹配函数。

```python
        cutlist = []
        index = 0
```

初始化分词结果和当前位置索引。

```python
        while index < len(sent):
```

从左往右遍历整个句子。

```python
            matched = False
            for i in range(self.max_wordlen, 0, -1):
                cand_word = sent[index: index + i]
                if cand_word in self.word_dict:
                    cutlist.append(cand_word)
                    matched = True
                    break
```

这一段是正向最大匹配的核心逻辑：

1. 从当前位置开始
2. 先取最长可能的词
3. 如果词典里有，就直接切下来
4. 如果没有，再尝试更短的词

```python
            if not matched:
                i = 1
                cutlist.append(sent[index])
```

如果所有候选词都匹配不上，就按单字切分。

```python
            index += i
```

索引向后移动。

```python
        return cutlist
```

返回分词结果。

### `max_backward_cut(sent)`

```python
    def max_backward_cut(self, sent):
```

定义逆向最大匹配函数。

```python
        cutlist = []
        index = len(sent)
        max_wordlen = 5
```

初始化分词结果、右侧索引。  
这里的 `max_wordlen = 5` 在后面并没有真正用到，因为实际循环用的是 `self.max_wordlen`，所以这行可以看作一个无效局部变量。

```python
        while index > 0:
```

从右往左遍历句子。

```python
            matched = False
            for i in range(self.max_wordlen, 0, -1):
                tmp = (i + 1)
                cand_word = sent[index - tmp: index]
```

从右侧开始不断尝试候选词。  
这里的 `tmp = i + 1` 会让切片逻辑稍微难理解，属于可以在课堂上专门指出的代码可读性问题。

```python
                if cand_word in self.word_dict:
                    cutlist.append(cand_word)
                    matched = True
                    break
```

如果匹配成功，就把该词加入结果。

```python
            if not matched:
                tmp = 1
                cutlist.append(sent[index - 1])
```

如果没有匹配成功，就按单字切。

```python
            index -= tmp
```

索引左移。

```python
        return cutlist[::-1]
```

因为结果是从右向左加入的，所以最后要反转。

### `max_biward_cut(sent)`

```python
    def max_biward_cut(self, sent):
```

定义双向最大匹配函数。

```python
        forward_cutlist = self.max_forward_cut(sent)
        backward_cutlist = self.max_backward_cut(sent)
```

分别得到正向和逆向切分结果。

```python
        count_forward = len(forward_cutlist)
        count_backward = len(backward_cutlist)
```

统计两种切分方式得到的词数。

```python
        def compute_single(word_list):
            num = 0
            for word in word_list:
                if len(word) == 1:
                    num += 1
            return num
```

定义一个内部函数，用来统计单字词数量。

```python
        if count_forward == count_backward:
            if compute_single(forward_cutlist) > compute_single(backward_cutlist):
                return backward_cutlist
            else:
                return forward_cutlist
```

如果正向和逆向切出来的词数相同，就比较谁的单字词更少。  
单字词更少的结果通常更优。

```python
        elif count_backward > count_forward:
            return forward_cutlist
        else:
            return backward_cutlist
```

如果词数不同，就优先选择词数更少的结果。

---

## 5. 课堂总结

你可以这样总结这个文件：

`max_cut.py` 提供了一个基于词典的简单中文分词器，它展示了传统规则方法在领域词典切分中的基本思路。

课堂上建议重点讲三点：

1. 什么是最大匹配分词
2. 为什么需要最长词优先
3. 为什么双向最大匹配通常比单向更稳
