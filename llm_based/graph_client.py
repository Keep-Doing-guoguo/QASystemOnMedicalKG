from py2neo import Graph

try:
    from llm_based.config import NEO4J_DEBUG, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
    from llm_based.runtime import get_logger
except ModuleNotFoundError:
    from config import NEO4J_DEBUG, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
    from runtime import get_logger


class GraphClient:
    """Neo4j 查询客户端。

    LLM 通道通过 CypherBuilder 生成参数化 Cypher，再由这里执行。
    """

    def __init__(self):
        self.debug = NEO4J_DEBUG
        self.logger = get_logger("graph_client")
        # 和 rule_based 保持同一套 Neo4j 连接配置。
        self.debug_print("connect", "{0} user={1}".format(NEO4J_URI, NEO4J_USER))
        self.g = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

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
            self.logger.info("%s: %s", name, value)
