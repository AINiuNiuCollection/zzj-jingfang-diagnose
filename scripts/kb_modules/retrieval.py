"""
retrieval - BM25 检索 + 方剂排序 + 否定排除

使用 DataLoader 缓存的 BM25 索引，权重从 Config 读取。

v2 重写核心改进：
1. 否定感知匹配：提取否定区间，匹配时跳过被否定词修饰的区域
2. 特异性加权：指示词得分 = 基础权重 × 特异性系数（1字0.3, 2字通用0.6, 3字1.0, 4字+1.2）
3. 复合指示词分拆匹配：整体优先，拆分兜底，部分命中按比例计分
"""

from .config import Config


# ============================================================
# 否定感知匹配工具函数
# ============================================================

# 中文否定前缀（从 negation_mapping 中归纳）
_NEGATION_PREFIXES = ("不", "无", "未", "非", "莫")

# 2字通用指示词集合（特异性系数降为0.6）
_GENERIC_2CHAR = frozenset({
    "汗出", "发热", "下利", "腹满", "小便", "大便",
    "心下", "呕吐", "腹痛", "头痛", "恶寒", "恶风",
    "口渴", "烦躁", "短气", "咳喘", "自汗", "盗汗",
    "心烦", "口苦", "咽干", "目眩", "喘满", "腹胀",
})


def extract_negation_positions(query: str) -> list:
    """从标准化查询中提取否定前缀位置

    只记录每个否定前缀的字符位置，不做区间扩展。
    否定判定改为前缀紧邻检查（见 _is_negated_at），避免区间过宽误杀。

    Returns:
        list of (char_index, prefix_char) 否定前缀位置及其字符
    """
    positions = []
    for prefix in _NEGATION_PREFIXES:
        start = 0
        while True:
            idx = query.find(prefix, start)
            if idx == -1:
                break
            positions.append((idx, prefix))
            start = idx + 1
    return positions


def _is_negated_at(pos: int, indicator: str, query: str, neg_positions: list) -> bool:
    """检查指示词匹配位置是否被否定前缀紧邻修饰

    核心逻辑：只有否定前缀位于指示词**正前方紧邻**位置时才视为被否定。
    如果否定前缀位于指示词匹配范围内部（如"小便不利"中的"不"），
    需要区分两种情况：
    - 否定前缀是指示词自身的组成部分（"不利"中的"不"） → 不算否定
    - 否定前缀修饰的是指示词的前半部分（如"不"+"心下痞"） → 算否定

    判别方法：检查指示词本身是否包含该否定前缀字符。
    如果指示词自身也包含"不"（如"小便不利"、"不欲食"），
    则查询中对应位置的"不"是指示词的组成部分而非外部否定。
    """
    ind_len = len(indicator)
    for neg_idx, neg_char in neg_positions:
        # 否定前缀紧贴在指示词正前方：如 "不"+"渴" → neg_idx == pos-1
        if neg_idx == pos - 1:
            return True
        # 否定前缀位于指示词匹配范围内部
        if pos <= neg_idx < pos + ind_len:
            # 计算否定前缀在指示词内部的偏移
            offset = neg_idx - pos
            # 如果指示词自身在同一偏移处也是同一个否定字，
            # 说明这是指示词的组成部分（如"小便不利"的"不"），不算否定
            if offset < len(indicator) and indicator[offset] == neg_char:
                continue  # 不是外部否定，跳过
            # 否则，查询中该位置出现了指示词中没有的否定字 → 外部否定
            return True
    return False


def match_indicator(indicator: str, query: str, neg_positions: list) -> dict:
    """否定感知的指示词匹配（前缀紧邻方式）

    Returns:
        {"hit": bool, "is_negated": bool, "position": int}
        - hit: 指示词在查询中出现
        - is_negated: 出现位置被否定前缀紧邻修饰（不计数）
        - position: 匹配位置（-1为未命中）
    """
    pos = query.find(indicator)
    if pos == -1:
        return {"hit": False, "is_negated": False, "position": -1}

    if _is_negated_at(pos, indicator, query, neg_positions):
        return {"hit": True, "is_negated": True, "position": pos}

    return {"hit": True, "is_negated": False, "position": pos}


def specificity_weight(indicator: str) -> float:
    """根据指示词长度和特异性计算权重系数

    设计逻辑：
    - 1字（"痞""渴""呕"）：鉴别力极低，大量方剂共享 → 系数0.3
    - 2字通用（"汗出""发热""下利"）：中等鉴别力 → 系数0.6
    - 2字特异性（"恶寒""往来"）：较高鉴别力 → 系数0.8
    - 3字（"心下痞""不得眠"）：高鉴别力 → 系数1.0
    - 4字+（"往来寒热""干噫食臭"）：极高鉴别力 → 系数1.2
    """
    length = len(indicator)
    if length == 1:
        return 0.3
    elif length == 2:
        if indicator in _GENERIC_2CHAR:
            return 0.6
        return 0.8
    elif length == 3:
        return 1.0
    else:  # 4字+
        return 1.2


# ============================================================
# 复合指示词拆分表
# ============================================================

# 从 formulas.json 中提取的复合指示词 → 拆分后的独立指示词列表
# 只收录长度≥3的复合指示词（2字不拆）
_COMPOUND_SPLIT_TABLE = {
    "肠鸣下利": ["肠鸣", "下利"],
    "心下痞硬而满": ["心下痞硬", "满"],
    "心烦不得安": ["心烦", "不得安"],
    "下利日数十行": ["下利频"],
    "腹满而吐": ["腹满", "吐"],
    "喘而汗出": ["喘", "汗出"],
    "心下痞硬": ["心下痞", "硬"],
    "昼日烦躁不得眠": ["昼日烦躁", "不得眠"],
    "咳而微喘": ["咳", "微喘"],
    "下利清谷": ["下利", "清谷"],
    "不能消谷": ["不能", "消谷"],
}


def match_compound(indicator: str, query: str, neg_positions: list) -> dict:
    """复合指示词匹配：整体优先，拆分兜底

    Returns:
        {"hit": bool, "partial": bool, "score_ratio": float}
        - hit: 是否有任意部分命中
        - partial: 是否为部分命中（非整体连续命中）
        - score_ratio: 得分系数（整体1.0, 拆分全命中0.8, 部分命中按比例×0.5）
    """
    # 1. 整体匹配（否定感知）
    result = match_indicator(indicator, query, neg_positions)
    if result["hit"] and not result["is_negated"]:
        return {"hit": True, "partial": False, "score_ratio": 1.0}

    # 2. 查找拆分表
    parts = _COMPOUND_SPLIT_TABLE.get(indicator, [])
    if not parts:
        return {"hit": False, "partial": False, "score_ratio": 0.0}

    # 3. 分别匹配各部分
    hits = 0
    for part in parts:
        r = match_indicator(part, query, neg_positions)
        if r["hit"] and not r["is_negated"]:
            hits += 1

    if hits == len(parts) and hits > 0:
        return {"hit": True, "partial": True, "score_ratio": 0.8}
    elif hits > 0:
        return {"hit": True, "partial": True, "score_ratio": (hits / len(parts)) * 0.5}
    else:
        return {"hit": False, "partial": False, "score_ratio": 0.0}


class Retriever:
    """BM25 检索 + 方剂排序（v2: 否定感知+特异性加权+复合拆分）"""

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
        """层级加权排序 v2（否定感知+特异性加权+复合拆分+后世安全规则降权）

        关键改进：
        1. 否定感知：先提取否定区间，匹配时跳过被否定修饰的区域
        2. 特异性加权：指示词得分 = CORE_INDICATOR_WEIGHT × specificity_weight(ind)
        3. 复合拆分：对复合指示词，整体优先匹配，拆分兜底部分命中按比例计分
        """
        orange_warnings = orange_warnings or []
        results = []
        cfg = Config

        # 提取否定前缀位置（前缀紧邻方式，不做区间扩展）
        neg_positions = extract_negation_positions(normalized_query)

        for f in self.data["formulas"]:
            if f["id"] in excluded_ids:
                continue
            score = 0.0

            # ---- 一级：特异性核心指征（否定感知+特异性加权+复合拆分） ----
            core_hits = 0
            for ind in f.get("core_indicators", []):
                # 判断是否为复合指示词（在拆分表中的）
                is_compound = ind in _COMPOUND_SPLIT_TABLE

                if is_compound:
                    # 复合指示词：整体优先，拆分兜底
                    cm = match_compound(ind, normalized_query, neg_positions)
                    if cm["hit"]:
                        sw = specificity_weight(ind)
                        score += cfg.CORE_INDICATOR_WEIGHT * sw * cm["score_ratio"]
                        if cm["score_ratio"] >= 0.8:
                            core_hits += 1
                else:
                    # 普通指示词：否定感知匹配
                    mr = match_indicator(ind, normalized_query, neg_positions)
                    if mr["hit"] and not mr["is_negated"]:
                        sw = specificity_weight(ind)
                        score += cfg.CORE_INDICATOR_WEIGHT * sw
                        core_hits += 1

            # 排除指征命中 → 重罚（仍用否定感知）
            for ex_ind in f.get("exclusion_indicators", []):
                mr = match_indicator(ex_ind, normalized_query, neg_positions)
                if mr["hit"] and not mr["is_negated"]:
                    score -= cfg.EXCLUSION_PENALTY

            # ---- 二级：主症+脉象（否定感知，不做特异性加权——二级已够低） ----
            main_hits = 0
            for ind in f.get("main_indications", []):
                mr = match_indicator(ind, normalized_query, neg_positions)
                if mr["hit"] and not mr["is_negated"]:
                    main_hits += 1
                    score += cfg.MAIN_INDICATION_WEIGHT

            pulse_hits = 0
            for p in f.get("typical_pulse", []):
                mr = match_indicator(p, normalized_query, neg_positions)
                if mr["hit"] and not mr["is_negated"]:
                    pulse_hits += 1
                    score += cfg.MAIN_INDICATION_WEIGHT

            # ---- 三级：病机 ----
            if f.get("core_pathogenesis") and any(
                kw in normalized_query for kw in f["core_pathogenesis"].split("，")
            ):
                score += cfg.PATHOGENESIS_WEIGHT

            # ---- 相对禁忌降权 ----
            if f.get("formula_category") in warned_categories:
                score *= cfg.RELATIVE_CONTRA_PENALTY

            # ---- 🟠 后世安全规则降权 ----
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
                    "formula": f, "score": round(score, 2),
                    "core_hits": core_hits, "main_hits": main_hits, "pulse_hits": pulse_hits,
                    "orange_warnings": orange_details if orange_hit else []
                })

        return sorted(results, key=lambda x: x["score"], reverse=True)[:cfg.FORMULA_TOP_K]

    def build_chapter_context(self, retrieved_clauses: list, data: dict) -> list:
        """根据检索命中的条文，提取其所属病篇的完整条文列表

        当某个病篇命中≥1条条文时，将该病篇的全部条文id+摘要附加到输出，
        使AI能看到病篇全貌，不再受BM25 Top-K排名视野限制。

        Returns:
            list of {"chapter", "hit_count", "total_clauses", "all_clause_ids", "summary"}
        """
        # 1. 统计命中条文的 chapter 分布
        chapter_hits = {}  # chapter → {"count": int, "clauses": list}
        for item in retrieved_clauses:
            clause = item.get("clause", {})
            chapter = clause.get("chapter", "")
            if not chapter:
                continue
            if chapter not in chapter_hits:
                chapter_hits[chapter] = {"count": 0, "clauses": []}
            chapter_hits[chapter]["count"] += 1
            chapter_hits[chapter]["clauses"].append(clause)

        if not chapter_hits:
            return []

        # 2. 对每个命中病篇，收集全部条文
        all_clauses = data.get("clauses", [])
        chapter_all = {}  # chapter → list of clause ids
        for clause in all_clauses:
            ch = clause.get("chapter", "")
            if ch in chapter_hits:
                if ch not in chapter_all:
                    chapter_all[ch] = []
                chapter_all[ch].append(clause.get("id", ""))

        # 3. 构建输出（只保留命中≥1条的病篇）
        results = []
        for chapter, hit_info in chapter_hits.items():
            all_ids = chapter_all.get(chapter, [])
            # 构建摘要：列出该病篇中涉及的关键方剂名
            formula_names = set()
            for clause in hit_info["clauses"]:
                for fn in clause.get("formulas", []):
                    formula_names.add(fn)
            summary_parts = [f"{chapter}共{len(all_ids)}条"]
            if formula_names:
                summary_parts.append(f"涉及方剂：{'、'.join(sorted(formula_names))}")

            results.append({
                "chapter": chapter,
                "hit_count": hit_info["count"],
                "total_clauses": len(all_ids),
                "all_clause_ids": all_ids,
                "summary": "，".join(summary_parts),
            })

        # 按命中数降序排列
        return sorted(results, key=lambda x: x["hit_count"], reverse=True)
