"""
retrieval - BM25 检索 + 方剂排序 + 否定排除

使用 DataLoader 缓存的 BM25 索引，权重从 Config 读取。
"""

from .config import Config


class Retriever:
    """BM25 检索 + 方剂排序"""

    def __init__(self, data: dict, data_loader):
        self.data = data
        self.data_loader = data_loader

    def search_clauses(self, query_keywords: list, top_k: int = None) -> list:
        """BM25 条文检索（使用缓存索引）"""
        top_k = top_k or Config.BM25_TOP_K
        if not query_keywords:
            return []

        bm25, clause_docs = self.data_loader.get_bm25_index(self.data)
        if bm25 is None:
            return []
        scores = bm25.get_scores(query_keywords)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked[:top_k]:
            if score > 0:
                results.append({"clause": self.data["clauses"][idx], "score": float(score)})
        return results

    def rank_formulas(self, normalized_query: str, excluded_ids: list,
                      warned_categories: set, orange_warnings: list = None) -> list:
        """层级加权排序（含后世安全规则降权）

        关键改进：权重从 Config 读取，不再硬编码。
        """
        orange_warnings = orange_warnings or []
        results = []
        cfg = Config

        for f in self.data["formulas"]:
            if f["id"] in excluded_ids:
                continue
            score = 0.0

            # 一级：特异性核心指征
            core_hits = sum(1 for ind in f.get("core_indicators", []) if ind in normalized_query)
            score += core_hits * cfg.CORE_INDICATOR_WEIGHT

            # 排除指征命中 → 重罚
            for ex_ind in f.get("exclusion_indicators", []):
                if ex_ind in normalized_query:
                    score -= cfg.EXCLUSION_PENALTY

            # 二级：主症+脉象
            main_hits = sum(1 for ind in f.get("main_indications", []) if ind in normalized_query)
            pulse_hits = sum(1 for p in f.get("typical_pulse", []) if p in normalized_query)
            score += (main_hits + pulse_hits) * cfg.MAIN_INDICATION_WEIGHT

            # 三级：病机
            if f.get("core_pathogenesis") and any(kw in normalized_query for kw in f["core_pathogenesis"].split("，")):
                score += cfg.PATHOGENESIS_WEIGHT

            # 相对禁忌降权
            if f.get("formula_category") in warned_categories:
                score *= cfg.RELATIVE_CONTRA_PENALTY

            # 🟠 后世安全规则降权
            orange_hit = False
            orange_details = []
            herbs_in_formula = [c.get("herb", "") for c in f.get("composition", [])]
            for ow in orange_warnings:
                for herb_a, herb_b in ow.get("contraindicated_pairs", []):
                    if herb_a in herbs_in_formula and herb_b in herbs_in_formula:
                        orange_hit = True
                        has_precedent = bool(ow.get("classical_precedent"))
                        penalty = cfg.CLASSICAL_PRECEDENT_PENALTY if has_precedent else cfg.NO_PRECEDENT_PENALTY
                        score *= penalty
                        orange_details.append({
                            "rule_id": ow["id"],
                            "pair": f"{herb_a}+{herb_b}",
                            "has_classical_precedent": has_precedent,
                            "precedent": ow.get("classical_precedent", ""),
                            "penalty": penalty,
                        })

            if score > 0:
                results.append({
                    "formula": f, "score": score,
                    "core_hits": core_hits, "main_hits": main_hits, "pulse_hits": pulse_hits,
                    "orange_warnings": orange_details if orange_hit else []
                })

        return sorted(results, key=lambda x: x["score"], reverse=True)[:cfg.FORMULA_TOP_K]
