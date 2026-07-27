"""
data_loader - 数据加载 + 缓存 + BM25 索引构建
"""

import json
from pathlib import Path

from .terminology import extract_keywords


class DataLoader:
    """知识库数据加载器，延迟加载 + 缓存 + BM25 索引缓存"""

    def __init__(self, assets_dir: Path):
        self.assets_dir = assets_dir
        self._data = None
        self._bm25_cache = None  # (bm25_obj, clause_docs)

    def load(self) -> dict:
        """加载全部知识库数据（带缓存）"""
        if self._data is not None:
            return self._data
        self._data = {
            "clauses": self._load_json("clauses.json") or [],
            "formulas": self._load_json("formulas.json") or [],
            "rules": self._load_json("rules.json") or [],
            "dictionary": self._load_json("dictionary.json") or {},
            "emergency": self._load_json("emergency.json") or [],
            "hebian": self._load_json("hebian.json") or [],
            "mistreatment": self._load_json("mistreatment.json") or {},
            "pulse_channel_map": self._load_json("pulse_channel_map.json") or {},
            "diagnostic_combos": self._load_json("diagnostic_combos.json") or {},
            "contradictory_combos": self._load_json("contradictory_combos.json") or {},
        }
        return self._data

    def _load_json(self, filename: str):
        """从 assets 目录加载 JSON"""
        path = self.assets_dir / filename
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_bm25_index(self, data: dict):
        """获取 BM25 索引（带缓存），返回 (bm25, clause_docs)

        仅首次调用时构建，后续直接返回缓存。
        """
        if self._bm25_cache is not None:
            return self._bm25_cache

        from rank_bm25 import BM25Okapi

        dictionary = data.get("dictionary", {})
        clauses = data.get("clauses", [])

        clause_docs = []
        for c in clauses:
            text = c.get("original_text", "") + " " + " ".join(c.get("main_symptoms", [])) + " " + " ".join(c.get("pulse", []))
            keywords = extract_keywords(text, dictionary)
            # BM25 要求每个文档至少有一个 token，空文档用 [""] 填充
            clause_docs.append(keywords if keywords else [""])

        bm25 = BM25Okapi(clause_docs) if clause_docs else None
        self._bm25_cache = (bm25, clause_docs)
        return self._bm25_cache
