from py2neo import Graph


class GraphClient:
    """Neo4j 查询客户端。

    LLM 通道通过 CypherBuilder 生成参数化 Cypher，再由这里执行。
    """

    def __init__(self):
        self.debug = True
        # 和 rule_based 保持同一套 Neo4j 连接配置。
        self.debug_print("connect", "bolt://127.0.0.1:7687 user=neo4j")
        self.g = Graph("bolt://127.0.0.1:7687", auth=("neo4j", "12341234"))

    def run(self, cypher, parameters=None):
        # CypherBuilder 如果校验失败会返回空 cypher，这里直接返回空结果。
        if not cypher:
            self.debug_print("skip_reason", "Empty cypher.")
            return []
        self.debug_print("cypher", cypher)
        self.debug_print("parameters", parameters or {})
        result = self.g.run(cypher, parameters or {}).data()
        self.debug_print("result_count", len(result))
        self.debug_print("result", result)
        return result

    def debug_print(self, name, value):
        if self.debug:
            print("[GraphClient] {0}: {1}".format(name, value))
