import os

import ahocorasick

try:
    from llm_based.schema import ENTITY_LABELS
except ModuleNotFoundError:
    from schema import ENTITY_LABELS


class EntityLinker:
    """基于 dict/ 词典做实体识别和实体校验。

    这里没有使用 LLM 抽实体，而是沿用项目已有词典，目的是保证
    进入图谱查询的实体一定来自当前知识图谱的可识别范围。
    """

    def __init__(self):
        self.debug = True
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # ENTITY_LABELS 的 key 和 dict/ 下的文件名保持一致。
        self.entity_files = {
            entity_type: os.path.join(root_dir, "dict", entity_type + ".txt")
            for entity_type in ENTITY_LABELS
        }
        self.entities_by_type = self._load_entities()
        self.word_types = self._build_word_types()
        # Aho-Corasick 自动机用于高效匹配大量医学实体词。
        self.region_tree = self._build_actree(self.word_types.keys())
        self.debug_print("loaded_entity_counts", {
            entity_type: len(words)
            for entity_type, words in self.entities_by_type.items()
        })

    def link(self, question):
        """识别问题中出现的实体，并返回实体类型和 Neo4j label。"""
        self.debug_print("question", question)
        matched_words = []
        for item in self.region_tree.iter(question):
            matched_words.append(item[1][1])
        self.debug_print("matched_words", matched_words)

        # 如果同时匹配短词和长词，删除被包含的短词，保留更具体的实体。
        stop_words = []
        for word1 in matched_words:
            for word2 in matched_words:
                if word1 in word2 and word1 != word2:
                    stop_words.append(word1)

        final_words = [word for word in matched_words if word not in stop_words]
        self.debug_print("stop_words", stop_words)
        self.debug_print("final_words", final_words)
        linked_entities = [
            {
                "name": word,
                "types": self.word_types[word],
                "labels": [ENTITY_LABELS[type_] for type_ in self.word_types[word]],
            }
            for word in final_words
        ]
        self.debug_print("linked_entities", linked_entities)
        return linked_entities

    def validate_entity(self, name, label):
        """校验 LLM 查询计划中的实体是否真的存在于对应词典。"""
        entity_type = self._type_for_label(label)
        if not entity_type:
            self.debug_print("validate_entity", {
                "name": name,
                "label": label,
                "result": False,
                "reason": "Unknown label",
            })
            return False
        result = name in self.entities_by_type.get(entity_type, set())
        self.debug_print("validate_entity", {
            "name": name,
            "label": label,
            "type": entity_type,
            "result": result,
        })
        return result

    def _load_entities(self):
        """读取 dict/ 下的实体词典。"""
        entities = {}
        for entity_type, file_path in self.entity_files.items():
            with open(file_path, encoding="utf-8") as file:
                entities[entity_type] = {line.strip() for line in file if line.strip()}
        return entities

    def _build_word_types(self):
        """构建 实体词 -> 类型列表 的映射。"""
        word_types = {}
        for entity_type, words in self.entities_by_type.items():
            for word in words:
                word_types.setdefault(word, []).append(entity_type)
        return word_types

    def _build_actree(self, words):
        """构建 Aho-Corasick 自动机。"""
        actree = ahocorasick.Automaton()
        for index, word in enumerate(words):
            actree.add_word(word, (index, word))
        actree.make_automaton()
        return actree

    def _type_for_label(self, label):
        """把 Neo4j label 反查为词典类型名。"""
        for entity_type, entity_label in ENTITY_LABELS.items():
            if entity_label == label:
                return entity_type
        return ""

    def debug_print(self, name, value):
        if self.debug:
            print("[EntityLinker] {0}: {1}".format(name, value))
