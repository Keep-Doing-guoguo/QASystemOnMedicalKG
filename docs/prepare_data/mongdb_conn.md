# mongdb_conn.py 讲解

## 1. 这个文件是做什么的

`mongdb_conn.py` 是一个数据库连通性测试脚本。

它的作用很简单：测试本机的 MongoDB 服务是否可以正常连接。如果这个脚本都连不上，后面的爬虫、数据整理、JSON 导入都没法正常运行。

---

## 2. 这个文件里用到的库

### `pymongo`

`pymongo` 是 Python 连接 MongoDB 的官方驱动库。

在这个文件里，它主要负责：

1. 创建 MongoDB 客户端
2. 连接本地数据库
3. 发送 `ping` 命令测试数据库是否在线
4. 关闭数据库连接

---

## 3. 代码中的函数是做什么的

### `test_connection()`

这个函数负责完成整个测试流程：

1. 创建数据库连接
2. 执行测试命令
3. 输出成功或失败信息
4. 关闭连接

---

## 4. 按代码顺序讲解

```python
import pymongo
```

导入 `pymongo`，用于连接 MongoDB。

```python
def test_connection():
```

定义一个函数，名字叫 `test_connection`，表示“测试连接”。

```python
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
```

这一行创建 MongoDB 客户端对象。

- `mongodb://127.0.0.1:27017/` 表示连接本机 MongoDB
- `127.0.0.1` 表示本机地址
- `27017` 是 MongoDB 默认端口
- `serverSelectionTimeoutMS=3000` 表示 3 秒超时

```python
    try:
```

开始异常处理。

```python
        client.admin.command("ping")
```

向 MongoDB 发送一个 `ping` 命令。  
如果数据库能正常响应，说明连接可用。

```python
        print("MongoDB connected")
```

如果连接成功，就打印提示。

```python
    except Exception as exc:
```

如果发生异常，就进入异常处理分支。

```python
        print(f"MongoDB connect failed: {exc}")
```

打印失败信息，方便排查。

```python
    finally:
```

无论前面成功还是失败，最后都会执行这里。

```python
        client.close()
```

关闭数据库连接。

```python
if __name__ == "__main__":
    test_connection()
```

这表示只有当前文件被直接执行时，才会运行测试函数。

---

## 5. 课堂上可以怎么总结

这个文件虽然很短，但很重要。  
它不是业务处理脚本，而是环境检查脚本。

你可以告诉学生：

1. 做数据项目之前，先确保数据库能连通
2. 小脚本通常用来排查环境问题
3. `ping` 是 MongoDB 连通性测试里很常见的写法
