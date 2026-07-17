#!/usr/bin/env python3
"""
张仲景经方辨证辅助 - 知识库检索脚本

自包含脚本，AI 调用此脚本获取知识库检索结果，然后按七步流程进行综合分析。

依赖：rank_bm25, jieba
用法：
  python retrieve_kb.py --symptoms "发热,汗出,恶风" --pulse "脉浮缓" --chill-fever "发热" --sweat "有汗"
  python retrieve_kb.py --chief "发热三天恶风汗出" --pulse "脉浮缓"

输出：JSON 格式的检索结果（规则过滤+六经候选+方剂排名+条文召回）
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# 确保依赖可用
try:
    from rank_bm25 import BM25Okapi
    import jieba
except ImportError:
    print(json.dumps({"error": "缺少依赖，请运行: pip install rank_bm25 jieba"}, ensure_ascii=False))
    sys.exit(1)

# 静默 jieba
jieba.setLogLevel(20)

# assets 目录路径
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"

# 规则版本
RULE_VERSION = "1.0.0"
# 免责声明
DISCLAIMER = "本结果仅为经方学术参考，不构成诊疗建议，具体处方请由执业医师辨证开具。"

# ========== 脉象缺失兜底映射 ==========
# 数据来源：formulas.json + 六经脉象纲领（原典条文）
# 用途：当追问脉象后用户仍无法提供时，列出不同脉象对应的方剂方向

PULSE_FALLBACK_MAP = {
    "太阳": {
        "纲领": "太阳之为病，脉浮（SHL-001）",
        "脉象方向": [
            {"脉象": "脉浮缓", "方剂": "桂枝汤", "条文": "SHL-012", "提示": "太阳中风表虚证"},
            {"脉象": "脉浮紧", "方剂": "麻黄汤", "条文": "SHL-035", "提示": "太阳伤寒表实证"},
            {"脉象": "脉浮", "方剂": "五苓散", "条文": "SHL-071", "提示": "太阳蓄水证"},
            {"脉象": "脉浮弱", "方剂": "桂枝汤", "条文": "SHL-042", "提示": "表虚营卫不和"},
            {"脉象": "脉浮滑", "方剂": "小陷胸汤", "条文": "SHL-138", "提示": "痰热结胸轻证"},
            {"脉象": "脉浮数", "方剂": "厚朴七物汤", "条文": "JGL-腹满", "提示": "表里双解"},
        ],
    },
    "阳明": {
        "纲领": "阳明脉洪大（SHL-186）",
        "脉象方向": [
            {"脉象": "脉洪大", "方剂": "白虎汤/白虎加人参汤", "条文": "SHL-176/SHL-026", "提示": "阳明经热证"},
            {"脉象": "脉沉实", "方剂": "大承气汤", "条文": "SHL-208", "提示": "阳明腑实证"},
            {"脉象": "脉滑而疾", "方剂": "小承气汤", "条文": "SHL-208", "提示": "阳明腑实轻证"},
            {"脉象": "脉浮发热", "方剂": "猪苓汤", "条文": "SHL-223", "提示": "阳明水热互结"},
        ],
    },
    "少阳": {
        "纲领": "少阳脉弦（SHL-096）",
        "脉象方向": [
            {"脉象": "脉弦", "方剂": "小柴胡汤", "条文": "SHL-096", "提示": "少阳枢机不利"},
            {"脉象": "脉弦细", "方剂": "小柴胡汤", "条文": "SHL-096", "提示": "少阳气血偏弱"},
        ],
    },
    "太阴": {
        "纲领": "太阴脉缓弱（SHL-278/SHL-386）",
        "脉象方向": [
            {"脉象": "脉缓弱", "方剂": "理中丸/理中汤", "条文": "SHL-386", "提示": "太阴脾虚寒湿"},
            {"脉象": "脉沉迟", "方剂": "理中汤辈", "条文": "SHL-386", "提示": "中焦虚寒"},
        ],
    },
    "少阴": {
        "纲领": "少阴脉微细（SHL-281）",
        "脉象方向": [
            {"脉象": "脉微", "方剂": "白通汤", "条文": "SHL-314", "提示": "少阴阳虚戴阳"},
            {"脉象": "脉微欲绝", "方剂": "四逆汤/通脉四逆汤", "条文": "SHL-388/SHL-317", "提示": "少阴亡阳欲脱"},
            {"脉象": "脉沉", "方剂": "附子汤/麻黄细辛附子汤", "条文": "SHL-304/SHL-301", "提示": "少阴阳虚寒湿/太少两感"},
            {"脉象": "脉沉微", "方剂": "干姜附子汤", "条文": "SHL-061", "提示": "少阴暴脱急温"},
        ],
    },
    "厥阴": {
        "纲领": "厥阴无专脉，多脉微/脉细（SHL-338/SHL-351）",
        "脉象方向": [
            {"脉象": "脉微", "方剂": "乌梅丸", "条文": "SHL-338", "提示": "厥阴蛔厥寒热错杂"},
            {"脉象": "脉细欲绝", "方剂": "当归四逆汤/当归四逆加吴茱萸生姜汤", "条文": "SHL-351/SHL-352", "提示": "厥阴血虚寒厥/兼内有久寒"},
        ],
    },
}

# 脉象关键词→六经归类映射（用于根据已有症状快速定位最可能的脉象方向）
PULSE_KEYWORD_TO_CHANNEL = {
    "恶寒": ["太阳"],
    "恶风": ["太阳"],
    "发热": ["太阳", "阳明"],
    "往来寒热": ["少阳"],
    "但欲寐": ["少阴"],
    "下利清谷": ["少阴", "太阴"],
    "腹满而吐": ["太阴"],
    "自利不渴": ["太阴"],
    "消渴": ["厥阴", "阳明"],
    "气上撞心": ["厥阴"],
    "心下痞": ["太阳"],
    "大便不通": ["阳明"],
    "谵语": ["阳明"],
    "汗出不止": ["少阴", "太阳"],
    "四肢厥冷": ["少阴", "厥阴"],
}


def load_json(filename):
    """从 assets 加载 JSON"""
    path = ASSETS_DIR / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ========== 脉象缺失兜底逻辑 ==========

def generate_pulse_fallback(args, six_channel_hypotheses):
    """脉象缺失兜底方案：当追问脉象后用户仍无法提供时，根据六经脉象纲领列出不同脉象对应的方剂方向

    逻辑：
    1. 若已有六经候选（从症状推断），优先展示最可能的1-2经的脉象方向
    2. 同时列出全部六经的脉象纲领与对应方剂，供执业医师参考
    3. 所有映射均标注原典条文依据

    Args:
        args: 命令行参数（用于从已有症状推断最可能的六经）
        six_channel_hypotheses: 六经候选列表（从症状推断的结果）

    Returns:
        dict: {"pulse_missing": True, "likely_channels": [...], "full_map": {...}, "summary": str}
    """
    # 从已有症状推断最可能的六经方向
    symptom_text = f"{getattr(args, 'chief', '') or ''} {getattr(args, 'symptoms', '') or ''} {getattr(args, 'chill_fever', '') or ''} {getattr(args, 'sweat', '') or ''}"
    likely_channels = set()

    # 方法1：从 six_channel_hypotheses 获取
    for hyp in six_channel_hypotheses[:2]:
        ch = hyp.get("channel", "")
        if ch:
            likely_channels.add(ch)

    # 方法2：从症状关键词补充推断
    for keyword, channels in PULSE_KEYWORD_TO_CHANNEL.items():
        if keyword in symptom_text:
            for ch in channels:
                likely_channels.add(ch)

    # 构建优先展示的脉象方向
    priority_channels = [ch for ch in ["太阳", "阳明", "少阳", "太阴", "少阴", "厥阴"] if ch in likely_channels]

    # 构建完整的兜底映射输出
    full_map = {}
    for channel, data in PULSE_FALLBACK_MAP.items():
        full_map[channel] = {
            "纲领": data["纲领"],
            "脉象方向": data["脉象方向"],
            "is_priority": channel in priority_channels,
        }

    # 生成可读的摘要文本
    summary_parts = ["【脉象缺失兜底参考】脉象为仲景辨证一级依据，以下为不同脉象对应的方剂方向，供执业医师参考："]
    if priority_channels:
        summary_parts.append(f"\n▶ 最可能方向（基于已有症状推断）：")
        for ch in priority_channels:
            ch_data = PULSE_FALLBACK_MAP.get(ch, {})
            summary_parts.append(f"  {ch}（{ch_data.get('纲领', '')}）：")
            for item in ch_data.get("脉象方向", []):
                summary_parts.append(f"    {item['脉象']} → {item['方剂']}（{item['条文']}，{item['提示']}）")

    summary_parts.append(f"\n▶ 全部六经脉象参考：")
    for ch in ["太阳", "阳明", "少阳", "太阴", "少阴", "厥阴"]:
        ch_data = PULSE_FALLBACK_MAP.get(ch, {})
        summary_parts.append(f"  {ch}（{ch_data.get('纲领', '')}）：")
        for item in ch_data.get("脉象方向", []):
            marker = "★" if ch in priority_channels else " "
            summary_parts.append(f"  {marker} {item['脉象']} → {item['方剂']}（{item['条文']}，{item['提示']}）")

    summary_parts.append("\n⚠️ 以上为脉象缺失时的辅助参考方向，不替代脉诊。最终辨证须以实际脉象为准。")

    return {
        "pulse_missing": True,
        "likely_channels": priority_channels,
        "full_map": full_map,
        "summary": "\n".join(summary_parts),
    }


# ========== 数据加载 ==========

def load_data():
    """加载全部知识库数据"""
    return {
        "clauses": load_json("clauses.json") or [],
        "formulas": load_json("formulas.json") or [],
        "rules": load_json("rules.json") or [],
        "dictionary": load_json("dictionary.json") or {},
        "emergency": load_json("emergency.json") or [],
        "hebian": load_json("hebian.json") or [],
        "mistreatment": load_json("mistreatment.json") or {},
    }


# ========== 术语映射 ==========

def normalize(text, dictionary):
    """白话 → 文言标准术语映射"""
    symptom_map = dictionary.get("symptom_mapping", {})
    result = text
    for colloquial in sorted(symptom_map.keys(), key=len, reverse=True):
        classical = symptom_map[colloquial]
        if colloquial in result:
            result = result.replace(colloquial, classical)
    return result


def extract_negations(text, dictionary):
    """否定提取 → 排除清单"""
    negation_map = dictionary.get("negation_mapping", {})
    negations = []
    for neg_term, excluded in negation_map.items():
        if neg_term in text:
            negations.append(excluded)
    return list(dict.fromkeys(negations))


def extract_keywords(text, dictionary):
    """jieba 分词 + 术语映射"""
    normalized = normalize(text, dictionary)
    words = jieba.lcut(normalized)
    stop_words = {"的", "了", "是", "在", "有", "和", "与", "或", "及", "等"}
    return [w for w in words if len(w) >= 2 and w not in stop_words]


def detect_six_channel(text, dictionary):
    """六经候选检测"""
    normalized = normalize(text, dictionary)
    six_channel_kw = dictionary.get("six_channel_keywords", {})
    scores = {}
    for channel, keywords in six_channel_kw.items():
        score = sum(1 for kw in keywords if kw in normalized)
        if score > 0:
            scores[channel] = score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ========== 规则引擎 ==========

def collect_text(args):
    """收集患者输入文本"""
    parts = [
        args.chief, " ".join(args.symptoms.split(",")),
        args.pulse, args.tongue, args.sweat, args.chill_fever,
        args.stool_urine, args.thirst, args.extra,
    ]
    if args.population and args.population != "普通成人":
        parts.append(args.population)
    if args.treatment_history and args.treatment_history != "未经治疗":
        parts.append(args.treatment_history)
    return " ".join(p for p in parts if p)


def check_emergency(all_text, emergencies):
    """急重症预判"""
    for em in emergencies:
        hit_count = sum(1 for ind in em.get("indicators", []) if ind in all_text)
        if hit_count >= 2:
            return {
                "name": em["name"],
                "treatment": em["treatment"],
                "main_formula": em["main_formula"],
                "source_clause": em["source_clause"],
                "hit_indicators": [ind for ind in em.get("indicators", []) if ind in all_text],
            }
    return None


def check_cold_heat(args, all_text):
    """真假寒热鉴别"""
    has_extreme_heat = any(kw in all_text for kw in ["大热", "高热", "高烧", "身大热"])
    has_extreme_cold = any(kw in all_text for kw in ["大寒", "身大寒", "四肢厥冷", "手足冰凉"])
    want_clothing = args.want_clothing or ""
    has_heat = "发热" in args.chill_fever or "热" in args.chief
    has_cold = any(kw in args.chill_fever for kw in ["恶寒", "怕冷", "恶风"])
    pulse = args.pulse or ""
    thirst = args.thirst or ""

    if has_extreme_heat and want_clothing == "欲近衣":
        if not pulse or not thirst:
            return {"conclusion": "真寒假热（热在皮肤，寒在骨髓）", "need_inquiry": True,
                    "inquiry_points": ["请补充脉象：脉沉微/脉沉迟？", "请补充饮水情况：渴不欲饮/渴欲饮热？"]}
        return {"conclusion": "真寒假热（热在皮肤，寒在骨髓）", "need_inquiry": False, "inquiry_points": []}

    if has_extreme_cold and want_clothing == "不欲近衣":
        if not pulse or not thirst:
            return {"conclusion": "真热假寒（寒在皮肤，热在骨髓）", "need_inquiry": True,
                    "inquiry_points": ["请补充脉象：脉滑数有力？", "请补充饮水情况：渴喜冷饮？"]}
        return {"conclusion": "真热假寒（寒在皮肤，热在骨髓）", "need_inquiry": False, "inquiry_points": []}

    if (has_extreme_heat or has_extreme_cold) and (not want_clothing or want_clothing == "未知"):
        if has_extreme_heat:
            is_true_heat = any(kw in pulse for kw in ["洪", "数", "滑", "大"]) and thirst == "渴喜冷饮"
            if is_true_heat:
                return {"conclusion": "真热（脉象与渴饮佐证）", "need_inquiry": False, "inquiry_points": []}
            if not pulse or not thirst:
                return {"conclusion": "寒热真假未明", "need_inquiry": True,
                        "inquiry_points": ["极端热象需鉴别真假寒热（第11条）", "请补充欲近衣情况、脉象、饮水情况"]}
        if has_extreme_cold:
            is_true_cold = any(kw in pulse for kw in ["微", "细", "沉", "迟"])
            if is_true_cold:
                return {"conclusion": "真寒（脉象佐证）", "need_inquiry": False, "inquiry_points": []}
            if not pulse:
                return {"conclusion": "寒热真假未明", "need_inquiry": True,
                        "inquiry_points": ["极端寒象需鉴别真假寒热（第11条）", "请补充欲近衣情况、脉象"]}

    if has_heat or has_cold:
        return {"conclusion": "寒热表现明确（普通外感），非极端寒热", "need_inquiry": False, "inquiry_points": []}
    return {"conclusion": "未涉及寒热", "need_inquiry": False, "inquiry_points": []}


def check_contraindications(all_text, formulas, rules, population):
    """绝对禁忌红色拦截 + 后世安全规则橙级处理"""
    excluded_ids = []
    excluded_categories = []
    triggered = []
    orange_warnings = []  # 🟠 后世安全规则（非原典）

    for rule in rules:
        cat = rule.get("category", "")

        # 🔴 原典绝对禁忌（一票否决）
        if cat == "absolute_contraindication":
            hit = any(s in all_text for s in rule.get("trigger_symptoms", []))
            if rule.get("trigger_conditions", {}).get("population") == population:
                hit = True
            if hit:
                formula_cat = rule.get("target_formula_category", "")
                if formula_cat and formula_cat not in excluded_categories:
                    excluded_categories.append(formula_cat)
                triggered.append(rule["id"])

        # 🟠 后世安全规则（十八反/十九畏，非原典）
        elif cat == "postclassical_safety_rule":
            # 检查方剂组成中是否同时含有互忌药对
            # 此处在检索阶段先记录命中的规则，具体方剂级检查在 rank_formulas 中进行
            orange_warnings.append({
                "id": rule["id"],
                "description": rule.get("description", ""),
                "classical_precedent": rule.get("classical_precedent"),
                "contraindicated_pairs": _extract_contraindicated_pairs(rule),
            })

    # 类别 → 方剂ID
    for formula_cat in excluded_categories:
        for f in formulas:
            if f.get("formula_category") == formula_cat and f["id"] not in excluded_ids:
                excluded_ids.append(f["id"])

    # 禁汗规则额外排除含麻黄方剂
    diaphoretic_ids = {"R-CONTRA-001", "R-CONTRA-002", "R-CONTRA-003", "R-CONTRA-004", "R-CONTRA-005"}
    if any(rid in triggered for rid in diaphoretic_ids):
        for f in formulas:
            if any(c.get("herb") == "麻黄" for c in f.get("composition", [])):
                if f["id"] not in excluded_ids:
                    excluded_ids.append(f["id"])

    return {"excluded_ids": excluded_ids, "excluded_categories": excluded_categories, "triggered": triggered,
            "orange_warnings": orange_warnings}


def _extract_contraindicated_pairs(rule):
    """从后世安全规则中提取互忌药对"""
    pairs = []
    tc = rule.get("trigger_conditions", {})
    group_a = tc.get("contains_herb", [])
    group_b = tc.get("contraindicated_with", [])
    if isinstance(group_a, list) and isinstance(group_b, list):
        for a in group_a:
            for b in group_b:
                pairs.append((a, b))
    return pairs


def check_relative_warnings(all_text, rules):
    """相对禁忌黄色警示"""
    warnings = []
    for rule in rules:
        if rule.get("category") != "relative_contraindication":
            continue
        if any(s in all_text for s in rule.get("trigger_symptoms", [])):
            warnings.append({"category": rule["target_formula_category"], "description": rule["description"]})
    return warnings


def check_population(rules, population):
    """人群禁忌"""
    adjustments = []
    for rule in rules:
        if rule.get("category") != "population":
            continue
        if rule.get("trigger_conditions", {}).get("population") == population:
            adjustments.append(rule["description"])
    if population == "儿童":
        adjustments.append("儿童：剂量自动下调至成人1/3-1/2")
    return adjustments


# ========== BM25 检索 ==========

def bm25_search(corpus_docs, query_keywords, top_k=10):
    """BM25 检索"""
    if not corpus_docs or not query_keywords:
        return []
    bm25 = BM25Okapi(corpus_docs)
    scores = bm25.get_scores(query_keywords)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [(idx, float(score)) for idx, score in ranked[:top_k] if score > 0]


def rank_formulas(formulas, query, excluded_ids, warned_categories, orange_warnings=None):
    """层级加权排序（含🟠后世安全规则降权）"""
    orange_warnings = orange_warnings or []
    results = []
    for f in formulas:
        if f["id"] in excluded_ids:
            continue
        score = 0.0
        # 一级：特异性核心指征 ×10
        core_hits = sum(1 for ind in f.get("core_indicators", []) if ind in query)
        score += core_hits * 10.0
        # 排除指征命中 → 重罚
        for ex_ind in f.get("exclusion_indicators", []):
            if ex_ind in query:
                score -= 20.0
        # 二级：主症+脉象 ×3
        main_hits = sum(1 for ind in f.get("main_indications", []) if ind in query)
        pulse_hits = sum(1 for p in f.get("typical_pulse", []) if p in query)
        score += (main_hits + pulse_hits) * 3.0
        # 三级：病机 ×1
        if f.get("core_pathogenesis") and any(kw in query for kw in f["core_pathogenesis"].split("，")):
            score += 1.0
        # 相对禁忌降权
        if f.get("formula_category") in warned_categories:
            score *= 0.7
        # 🟠 后世安全规则降权：检查方剂组成中是否有互忌药对
        orange_hit = False
        orange_details = []
        herbs_in_formula = [c.get("herb", "") for c in f.get("composition", [])]
        for ow in orange_warnings:
            for herb_a, herb_b in ow.get("contraindicated_pairs", []):
                if herb_a in herbs_in_formula and herb_b in herbs_in_formula:
                    orange_hit = True
                    # 有原典先例者降权30%，无先例者降权50%
                    has_precedent = bool(ow.get("classical_precedent"))
                    penalty = 0.7 if has_precedent else 0.5
                    score *= penalty
                    orange_details.append({
                        "rule_id": ow["id"],
                        "pair": f"{herb_a}+{herb_b}",
                        "has_classical_precedent": has_precedent,
                        "precedent": ow.get("classical_precedent", ""),
                        "penalty": penalty,
                    })
        if score > 0:
            results.append({"formula": f, "score": score, "core_hits": core_hits,
                            "main_hits": main_hits, "pulse_hits": pulse_hits,
                            "orange_warnings": orange_details if orange_hit else []})
    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]


# ========== 主流程 ==========

def check_verification_inquiry(filtered_formulas, args, all_text):
    """验证性追问（v3通用版）：基于方剂core_indicators/exclusion_indicators自动检测关键鉴别信息缺失

    通用机制：检查Top1方剂的核心指征和排除指征中，哪些关键词对应的用户输入字段为空，
    自动生成追问。同时保留原有的6类特殊场景作为兜底增强。

    与六经追问互补：六经追问在病位不确定时触发，验证性追问在方剂已匹配但关键鉴别信息缺失时触发。

    Args:
        filtered_formulas: 排序后的候选方剂列表
        args: 命令行参数（含用户输入的四诊信息）
        all_text: 患者全部输入文本

    Returns:
        dict: {"need_verification": bool, "inquiry_point": str, "target_formula": str}
    """
    if not filtered_formulas:
        return {"need_verification": False, "inquiry_point": "", "target_formula": ""}

    top1 = filtered_formulas[0]["formula"]
    top1_name = top1.get("name", "")
    top1_cat = top1.get("formula_category", "")
    top1_core = top1.get("core_indicators", [])
    top1_exclusion = top1.get("exclusion_indicators", [])

    # ---- 通用机制：基于core_indicators/exclusion_indicators自动检测 ----
    # 建立关键词→输入字段→追问模板的映射
    keyword_field_map = {
        "汗出": {"field": "sweat", "question": "请确认：□有汗 □无汗 □汗出不止", "reason": "汗出情况是桂枝汤与麻黄汤的分水岭"},
        "无汗": {"field": "sweat", "question": "请确认：□有汗 □无汗 □汗出不止", "reason": "无汗是麻黄汤类核心指征"},
        "汗漏不止": {"field": "sweat", "question": "请确认：□有汗 □无汗 □汗出不止", "reason": "汗漏不止是桂枝加附子汤证核心"},
        "恶寒": {"field": "chill_fever", "question": "请确认寒热情况：□恶寒 □恶风 □发热 □往来寒热 □无明显寒热", "reason": "寒热是治则判定的核心依据"},
        "恶风": {"field": "chill_fever", "question": "请确认寒热情况：□恶寒 □恶风 □发热 □往来寒热 □无明显寒热", "reason": "恶风为桂枝汤证特征"},
        "发热": {"field": "chill_fever", "question": "请确认寒热情况：□恶寒 □恶风 □发热 □往来寒热 □无明显寒热", "reason": "发热为太阳/阳明核心指征"},
        "往来寒热": {"field": "chill_fever", "question": "请确认寒热情况：□恶寒 □恶风 □发热 □往来寒热 □无明显寒热", "reason": "往来寒热为少阳独有指征"},
        "小便不利": {"field": "stool_urine", "question": "请补充小便情况：□小便不利 □小便自利 □小便清长 □小便黄少", "reason": "小便不利为五苓散等利水方核心指征"},
        "口渴": {"field": "thirst", "question": "请确认渴饮情况：□口渴喜冷饮 □口渴不欲饮 □口渴欲饮热 □不口渴", "reason": "渴饮是真假寒热鉴别与五苓散证判定关键"},
        "渴欲饮水": {"field": "thirst", "question": "请确认渴饮情况：□口渴喜冷饮 □口渴不欲饮 □口渴欲饮热 □不口渴", "reason": "渴欲饮水为五苓散证核心"},
        "不渴": {"field": "thirst", "question": "请确认渴饮情况：□口渴喜冷饮 □口渴不欲饮 □口渴欲饮热 □不口渴", "reason": "不渴为茯苓甘草汤证与五苓散证的鉴别点（SHL-073）"},
        "脉浮": {"field": "pulse", "question": "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）", "reason": "脉浮为太阳病核心脉象（SHL-001）"},
        "脉沉": {"field": "pulse", "question": "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）", "reason": "脉沉为少阴/太阴病核心脉象"},
        "脉弦": {"field": "pulse", "question": "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）", "reason": "脉弦为少阳病核心脉象"},
        "脉浮紧": {"field": "pulse", "question": "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）", "reason": "脉浮紧为麻黄汤证核心脉象"},
        "脉浮缓": {"field": "pulse", "question": "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）", "reason": "脉浮缓为桂枝汤证核心脉象"},
        "但欲寐": {"field": None, "question": "请确认精神状态：□但欲寐（精神萎靡只想睡） □烦躁不安 □精神尚可", "reason": "但欲寐为少阴病核心指征（SHL-281）"},
    }

    # 检查core_indicators和exclusion_indicators中的关键词对应的输入是否缺失
    all_indicators = list(top1_core) + list(top1_exclusion)
    for indicator in all_indicators:
        if indicator in keyword_field_map:
            mapping = keyword_field_map[indicator]
            field = mapping["field"]
            # 如果该关键词对应的输入字段为空，触发追问
            if field is not None:
                field_value = getattr(args, field, "") or ""
                if not field_value.strip():
                    return {"need_verification": True,
                            "inquiry_point": f"Top1候选方为{top1_name}，其核心指征含「{indicator}」，但{mapping['reason']}。{mapping['question']}",
                            "target_formula": top1_name}
            elif indicator == "但欲寐" and "但欲寐" not in all_text and "嗜卧" not in all_text and "萎靡" not in all_text:
                return {"need_verification": True,
                        "inquiry_point": f"Top1候选方为{top1_name}，{mapping['reason']}。{mapping['question']}",
                        "target_formula": top1_name}

    # ---- 保留原有6类特殊场景作为兜底增强 ----
    # 这些场景涉及更复杂的鉴别逻辑，不能仅靠关键词映射覆盖

    # 兜底1：泻心汤类—需确认痞证性质（心下痛否）
    if top1_name in ("半夏泻心汤", "生姜泻心汤", "甘草泻心汤", "大黄黄连泻心汤", "旋覆代赭汤"):
        if "按之" not in all_text and "压痛" not in all_text and "硬痛" not in all_text and "喜按" not in all_text and "拒按" not in all_text and "痞" not in all_text:
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（泻心汤类/痞证方），需确认心下痞性质。请确认：患者心下（胃脘部）是 □但满不痛（痞） □硬痛拒按（须排除结胸）",
                    "target_formula": top1_name}

    # 兜底2：攻下方需确认表证已解
    if top1_name in ("大承气汤", "小承气汤", "调胃承气汤"):
        if not args.chill_fever:
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（攻下方），需确认表证是否已解。请补充：当前是否仍有恶寒/发热等表证？",
                    "target_formula": top1_name}

    # 兜底3：温阳方需排除真热假寒
    if top1_name in ("四逆汤", "真武汤", "附子汤", "干姜附子汤"):
        if not args.want_clothing and ("四肢厥冷" in all_text or "大寒" in all_text):
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（温阳方），患者有寒象但欲近衣情况未知，需排除真热假寒。请确认：患者虽怕冷，是否反而不想多穿衣服？",
                    "target_formula": top1_name}

    return {"need_verification": False, "inquiry_point": "", "target_formula": ""}


def check_info_completeness(args, filtered_formulas):
    """信息完整性检查（v3增强版）：在报告生成前系统检查信息缺口

    检查范围（3类）：
    1. 必填项系统性校验（与阻断点1一致）
    2. 强烈推荐项按需校验（基于Top1方核心指征）
    3. 体质关键项校验（影响剂量安全）

    Returns:
        dict: {"has_gaps": bool, "gaps": [{"field": str, "importance": str, "question": str, "reason": str}]}
    """
    gaps = []

    # === 1. 必填项系统性校验 ===
    required_fields = [
        ("chief", "主诉", "主诉是核心辨证起点，决定检索方向"),
        ("symptoms", "症状列表", "症状列表是方证匹配的主要依据"),
        ("pulse", "脉象", "仲景脉证合参，脉象为一级辨证依据。如SHL-001:太阳之为病，脉浮；无脉象则六经定性与方证匹配均会降权"),
        ("chill_fever", "寒热情况", "第11条真假寒热鉴别必查项；寒热未明则禁止定治则"),
        ("sweat", "汗出情况", "桂枝汤与麻黄汤的分水岭；亡阳证判定依据"),
        ("stool_urine", "二便情况", "阳明腑实/太阴脾虚/水饮内停鉴别；五苓散证vs猪苓汤证鉴别"),
    ]
    for field_name, display_name, reason in required_fields:
        field_value = getattr(args, field_name, "") or ""
        if not field_value.strip():
            importance = "high"
            # 脉象缺失时提供可能方剂方向
            extra_hint = ""
            if field_name == "pulse":
                extra_hint = "（若无法提供脉象，系统将自动生成脉象缺失兜底参考：按六经脉象纲领列出不同脉象对应的方剂方向，如脉浮缓→桂枝汤、脉沉迟→理中汤辈、脉弦→小柴胡汤等，详见输出pulse_fallback字段）"
            gaps.append({
                "field": field_name,
                "importance": importance,
                "question": f"{display_name}未记录。{reason}。请补充{display_name}{extra_hint}",
                "reason": reason
            })

    # === 2. 强烈推荐项按需校验（基于Top1方核心指征） ===
    if filtered_formulas:
        top1 = filtered_formulas[0]["formula"]
        top1_core = top1.get("core_indicators", [])
        top1_exclusion = top1.get("exclusion_indicators", [])
        top1_name = top1.get("name", "")

        all_indicators = list(top1_core) + list(top1_exclusion)

        # 2a. 渴饮：若Top1方核心指征涉及渴/饮/水
        thirst_keywords = ["口渴", "渴欲饮水", "不渴", "渴不欲饮", "渴饮", "消渴"]
        if any(kw in all_indicators for kw in thirst_keywords):
            thirst_value = getattr(args, "thirst", "") or ""
            if not thirst_value.strip():
                gaps.append({
                    "field": "thirst",
                    "importance": "high",
                    "question": f"Top1候选为{top1_name}，其核心指征涉及渴饮，但渴饮情况未填写。请确认：□口渴喜冷饮 □口渴不欲饮 □口渴欲饮热 □不口渴",
                    "reason": "渴饮是真假寒热鉴别关键与五苓散证判定关键（SHL-073）"
                })

        # 2b. 欲近衣：若Top1方涉及寒热鉴别（温阳方/清热方）
        cold_heat_formulas = ("四逆汤", "真武汤", "附子汤", "干姜附子汤", "白虎汤", "白虎加人参汤",
                              "黄芩汤", "葛根芩连汤", "黄连阿胶汤")
        if top1_name in cold_heat_formulas:
            want_clothing_value = getattr(args, "want_clothing", "") or ""
            if not want_clothing_value.strip():
                gaps.append({
                    "field": "want_clothing",
                    "importance": "high",
                    "question": f"Top1候选为{top1_name}，需排除寒热真假（第11条）。请确认：□欲近衣（怕冷想加衣） □不欲近衣（怕热想减衣） □正常",
                    "reason": "真寒假热/真热假寒鉴别核心（第11条），寒热颠倒则治则方向完全相反"
                })

        # 2c. 腹诊：泻心汤类/结胸方/承气汤类
        abdominal_formulas = ("半夏泻心汤", "生姜泻心汤", "甘草泻心汤", "大黄黄连泻心汤",
                              "旋覆代赭汤", "大陷胸汤", "小陷胸汤",
                              "大承气汤", "小承气汤", "调胃承气汤")
        if top1_name in abdominal_formulas:
            extra_value = getattr(args, "extra", "") or ""
            if not extra_value.strip() or not any(kw in extra_value for kw in ["按", "压痛", "硬痛", "喜按", "拒按", "痞", "腹"]):
                gaps.append({
                    "field": "abdominal_palpation",
                    "importance": "high",
                    "question": f"Top1候选为{top1_name}，腹部触诊对鉴别至关重要。请补充：脘腹部按压感觉如何？□但满不痛（痞证） □硬痛拒按（结胸） □腹满按之痛 □柔软无压痛",
                    "reason": "SHL-149：'但满而不痛，此为痞' vs '心下满而硬痛者，此为结胸'"
                })

    # === 3. 体质关键项校验（影响剂量安全） ===
    # 3a. 年龄/体重缺失→剂量倍率无法精确计算
    extra_value = getattr(args, "extra", "") or ""
    has_bmi_info = "BMI" in extra_value or "消瘦" in extra_value or "体重" in extra_value
    if not has_bmi_info:
        # 检查是否缺少年龄或体重信息（在extra中通常包含这些）
        chief_value = getattr(args, "chief", "") or ""
        symptoms_value = getattr(args, "symptoms", "") or ""
        all_input = f"{chief_value} {symptoms_value} {extra_value}"
        has_age = any(kw in all_input for kw in ["岁", "年龄"])
        has_weight = any(kw in all_input for kw in ["kg", "公斤", "体重"])
        if not has_age or not has_weight:
            missing_items = []
            if not has_age:
                missing_items.append("年龄")
            if not has_weight:
                missing_items.append("体重（kg）")
            gaps.append({
                "field": "physique_info",
                "importance": "medium",
                "question": f"缺少{'/'.join(missing_items)}，影响剂量倍率计算。请补充：{'/'.join(missing_items)}",
                "reason": "年龄/体重是剂量倍率核心依据：老年→调理量×0.6，极度消瘦(BMI<17)→调理量×0.6，急证重证→急证量×2.0"
            })

    # 3b. 激素/免疫抑制用药史
    if args.population == "素有宿疾" or "激素" in str(args.extra).lower() or "泼尼松" in str(args.extra):
        if not args.treatment_history or args.treatment_history == "未经治疗":
            gaps.append({
                "field": "medication_detail",
                "importance": "medium",
                "question": "患者有长期用药史（激素/免疫抑制剂等），对体质有重要影响。请补充具体用药情况（药名、剂量、疗程）",
                "reason": "长期使用激素相当于'壮火食气'，影响病机判断，但属辅助参考信息"
            })

    # 3c. 极低BMI需体重变化史
    if "消瘦" in str(args.extra) or "BMI" in str(args.extra):
        try:
            bmi_text = str(args.extra)
            import re as _re
            bmi_match = _re.search(r'BMI[：: ]*([0-9.]+)', bmi_text)
            if bmi_match and float(bmi_match.group(1)) < 17.0:
                gaps.append({
                    "field": "weight_history",
                    "importance": "medium",
                    "question": "患者BMI低于17.0（重度消瘦），请补充：消瘦是长期如此还是近期加重？有无明显体重下降？",
                    "reason": "极度消瘦影响方剂选择与剂量调整，太阴脾虚/胃阴虚等判断需要此信息"
                })
        except Exception:
            pass

    return {"has_gaps": len(gaps) > 0, "gaps": gaps}


def check_required_fields(args):
    """必填项预检（方案B）：在检索前校验6项必填信息

    Returns:
        dict: {"has_missing": bool, "missing": [{"field": str, "field_display": str, "question": str, "reason": str}]}
    """
    required = [
        ("chief", "主诉", "请描述患者最主要的症状及持续时间"),
        ("symptoms", "症状列表", "请列出所有症状，用逗号分隔"),
        ("pulse", "脉象", "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）。若无法提供，请回复'无法提供脉象'，系统将输出脉象缺失兜底参考（按六经脉象纲领列出不同脉象对应的方剂方向）"),
        ("chill_fever", "寒热情况", "请确认寒热：□恶寒 □恶风 □发热 □往来寒热 □无明显寒热"),
        ("sweat", "汗出情况", "请确认汗出：□有汗 □无汗 □汗出不止 □自汗 □正常"),
        ("stool_urine", "二便情况", "请描述大便和小便情况"),
    ]
    missing = []
    for field_name, display_name, question in required:
        field_value = getattr(args, field_name, "") or ""
        if not field_value.strip():
            missing.append({
                "field": field_name,
                "field_display": display_name,
                "question": question,
                "reason": f"{display_name}为必填项，缺失将严重影响辨证准确性"
            })
    return {"has_missing": len(missing) > 0, "missing": missing}


def check_patient_profile(all_text, args, formulas):
    """患者体质适配分析（v2新增）：基于患者特征对候选方剂的适配性评估

    分析患者体型、用药史、基础病等特征，评估候选方的适配性差异，
    提出基于原典的合理微调方向。

    Returns:
        dict: 体质分析结果，含整体评估和候选方微调建议
    """
    result = {"physique_assessment": [], "dose_notes": [], "formula_adjustments": []}

    # === 1. 体型评估 ===
    is_emaciated = any(kw in all_text for kw in ["消瘦", "瘦弱", "羸瘦", "BMI"])
    is_obese = any(kw in all_text for kw in ["肥胖", "丰腴", "BMI"])
    if is_emaciated:
        result["physique_assessment"].append({
            "type": "极度消瘦",
            "impact": "脾胃运化能力弱，气血生化不足",
            "dose_advice": "建议采用常规调理量（原量×0.6）或更轻，峻猛药物（大黄、芒硝、麻黄等）减量或去之",
            "jingfang_basis": "SHL-397「虚羸少气，气逆欲吐」— 竹叶石膏汤证，虚人治以补养为先",
            "reference": "辅助参考"
        })

    # === 2. 激素/免疫抑制用药史 ===
    if any(kw in all_text for kw in ["激素", "泼尼松", "强的松", "免疫抑制剂", "prednisone"]):
        result["physique_assessment"].append({
            "type": "长期激素使用史",
            "impact": "激素为纯阳壮火之品，长期使用耗伤真阴、灼伤胃阴，同时可致水钠潴留",
            "dose_advice": "注意顾护胃阴（可酌加麦冬、沙参等，参照SHL-397竹叶石膏汤法）；利水药用量可适当增加",
            "jingfang_basis": "SHL-397「伤寒解后，虚羸少气」 — 痿后调理以养阴益气为主",
            "reference": "辅助参考"
        })

    # === 3. 慢性肾脏病史 ===
    if any(kw in all_text for kw in ["肾炎", "肾", "IgA", "尿蛋白", "泡沫"]):
        result["physique_assessment"].append({
            "type": "慢性肾脏病史",
            "impact": "肾主水液代谢，肾脏疾病可致水气不化、精微下注",
            "dose_advice": "避免肾毒性药物（木通、马兜铃等）；利水药（茯苓、猪苓、泽泻）在合理范围内使用",
            "jingfang_basis": "金匮「水气病脉证并治」 — 腰以下肿当利小便",
            "reference": "辅助参考"
        })

    # === 4. 剂量建议 ===
    if is_emaciated:
        result["dose_notes"].append({
            "level": "建议",
            "note": "患者BMI偏低、形体消瘦，建议以推荐剂量的下限起始。半夏（原方半升≈40g）在常规调理量下约24g，仍超药典常规量（3-9g），须注意",
            "basis": "虚人宜缓攻徐补，不可峻猛伤正（SHL-273太阴病禁下）"
        })

    # === 5. 候选方微调建议（仅对Top3候选方）===
    for item in formulas[:3]:
        f = item["formula"]
        f_name = f.get("name", "")
        f_composition = f.get("composition", [])
        adjustments = []

        # 5a. 患者有小便不利 → 若方中无茯苓，建议加茯苓
        has_urine_issue = any(kw in all_text for kw in ["小便不利", "小便少", "小便不通", "水排不出", "尿少"])
        has_fuling = any(c.get("herb") == "茯苓" for c in f_composition)
        if has_urine_issue and not has_fuling and f_name != "五苓散":
            adjustments.append({
                "type": "加味",
                "herb": "茯苓",
                "reason": "患者有小便不利/水入不化之证，加茯苓利水渗湿、健脾宁心",
                "jingfang_basis": "SHL-096「心下悸、小便不利者，去黄芩加茯苓」；SHL-067茯苓桂枝白术甘草汤治水气"
            })

        # 5b. 患者有心烦/易怒 → 可考虑黄芩或相关配伍
        has_irritability = any(kw in all_text for kw in ["心烦", "易怒", "脾气不好", "烦躁", "不安"])
        has_huangqin = any(c.get("herb") == "黄芩" for c in f_composition)
        if has_irritability and not has_huangqin:
            adjustments.append({
                "type": "加味",
                "herb": "黄芩/栀子",
                "reason": "患者有心烦易怒表现，可加黄芩清上焦热或栀子除烦",
                "jingfang_basis": "SHL-096小柴胡汤证「心烦喜呕」用黄芩；SHL-076栀子豉汤治「虚烦不得眠」"
            })

        # 5c. 患者有纳差/食后不化/脾虚 → 若方中无参,建议加人参/党参
        has_spleen_deficiency = any(kw in all_text for kw in ["不消化", "食后", "消瘦", "脾虚", "纳差"])
        has_renshen = any(c.get("herb") == "人参" or c.get("herb") == "党参" for c in f_composition)
        if has_spleen_deficiency and not has_renshen:
            adjustments.append({
                "type": "加味",
                "herb": "人参（或党参）",
                "reason": "患者脾虚明显（食不化、形瘦），加人参补中益气",
                "jingfang_basis": "SHL-386理中丸治「寒多不用水」用人参；李东垣参考，但原典中人参即用于中虚"
            })

        # 5d. 患者有舌苔黄厚 → 热象明显
        if is_emaciated:
            adjustments.append({
                "type": "剂量调整",
                "herb": "全方",
                "reason": "患者极度消瘦，须以调理量（×0.6）起始，不可峻猛",
                "jingfang_basis": "SHL-273太阴病禁下；虚人宜缓图"
            })

        if adjustments:
            result["formula_adjustments"].append({
                "formula_name": f_name,
                "adjustments": adjustments
            })

    return result


def main():
    parser = argparse.ArgumentParser(description="张仲景经方辨证辅助 - 知识库检索")
    parser.add_argument("--chief", default="", help="主诉")
    parser.add_argument("--symptoms", default="", help="症状列表（逗号分隔）")
    parser.add_argument("--pulse", default="", help="脉象")
    parser.add_argument("--tongue", default="", help="舌象")
    parser.add_argument("--sweat", default="", help="汗出情况")
    parser.add_argument("--chill-fever", default="", help="寒热")
    parser.add_argument("--stool-urine", default="", help="二便")
    parser.add_argument("--want-clothing", default="", help="欲近衣情况")
    parser.add_argument("--thirst", default="", help="渴饮")
    parser.add_argument("--population", default="普通成人", help="人群属性")
    parser.add_argument("--treatment-history", default="未经治疗", help="治疗史")
    parser.add_argument("--history", default="", help="既往病史/素有宿疾（辅助参考）")
    parser.add_argument("--extra", default="", help="其他补充")
    args = parser.parse_args()

    data = load_data()
    all_text = collect_text(args)

    # 0. 必填项预检（方案B：入口校验，缺失时直接返回need_inquiry）
    required_check = check_required_fields(args)
    if required_check["has_missing"]:
        output = {
            "status": "need_inquiry",
            "rule_version": RULE_VERSION,
            "disclaimer": DISCLAIMER,
            "required_fields_check": required_check,
            "message": f"必填信息缺失：{', '.join(r['field_display'] for r in required_check['missing'])}。请补充后再进行辨证分析。",
            "emergency": None,
            "cold_heat": None,
            "contraindications": None,
            "relative_warnings": [],
            "population_adjustments": [],
            "six_channel_hypotheses": [],
            "retrieved_clauses": [],
            "candidate_formulas": [],
            "verification_inquiry": {"need_verification": False, "inquiry_point": "", "target_formula": ""},
            "info_completeness": {"has_gaps": True, "gaps": [{"field": r["field"], "importance": "high", "question": r["question"], "reason": r["reason"]} for r in required_check["missing"]]},
            "patient_profile": None,
            "pulse_fallback": generate_pulse_fallback(args, []) if not getattr(args, "pulse", "").strip() else None,
            "keywords": [],
            "negations": [],
            "normalized_query": "",
            "data_stats": {
                "clauses_count": len(data["clauses"]),
                "formulas_count": len(data["formulas"]),
                "rules_count": len(data["rules"]),
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 1. 术语映射 + 否定提取
    normalized = normalize(all_text, data["dictionary"])
    keywords = extract_keywords(all_text, data["dictionary"])
    negations = extract_negations(all_text, data["dictionary"])

    # 2. 规则引擎
    emergency = check_emergency(all_text, data["emergency"])
    cold_heat = check_cold_heat(args, all_text)
    contra = check_contraindications(all_text, data["formulas"], data["rules"], args.population)
    warnings = check_relative_warnings(all_text, data["rules"])
    pop_adjusts = check_population(data["rules"], args.population)

    # 3. 六经候选
    six_channel_candidates = detect_six_channel(all_text, data["dictionary"])
    total_score = sum(s for _, s in six_channel_candidates)
    hypotheses = []
    for channel, score in six_channel_candidates[:3]:
        conf = score / total_score if total_score > 0 else 0
        hypotheses.append({"channel": channel, "confidence": round(conf, 3)})

    # 4. BM25 条文检索
    clause_docs = [extract_keywords(c["original_text"] + " " + " ".join(c.get("main_symptoms", [])) + " " + " ".join(c.get("pulse", [])), data["dictionary"]) for c in data["clauses"]]
    clause_results = bm25_search(clause_docs, keywords, top_k=10)
    retrieved_clauses = [{"clause": data["clauses"][idx], "score": score} for idx, score in clause_results]

    # 5. 方剂匹配（层级加权）
    warned_cats = {w["category"] for w in warnings}
    formula_results = rank_formulas(data["formulas"], normalized, contra["excluded_ids"], warned_cats, contra.get("orange_warnings", []))

    # 否定排除
    filtered_formulas = []
    for item in formula_results:
        f = item["formula"]
        excluded = any(neg in f.get("core_indicators", []) for neg in negations)
        if not excluded:
            filtered_formulas.append(item)

    # 6. 验证性追问（v2：覆盖6类方证场景）
    verification = check_verification_inquiry(filtered_formulas, args, all_text)

    # 7. 信息完整性检查（v2新增）
    completeness = check_info_completeness(args, filtered_formulas)

    # 8. 患者体质适配分析（v2新增）
    profile = check_patient_profile(all_text, args, filtered_formulas)

    # 9. 脉象缺失兜底方案（脉象为空或用户明确表示无法提供时生成）
    pulse_value = getattr(args, "pulse", "") or ""
    pulse_fallback = None
    if not pulse_value.strip() or pulse_value.strip() in ("无法提供", "无法提供脉象", "不清楚", "不知道", "无"):
        pulse_fallback = generate_pulse_fallback(args, hypotheses)

    # 10. 输出结果
    output = {
        "status": "emergency" if emergency else ("need_inquiry" if cold_heat["need_inquiry"] or verification.get("need_verification", False) or completeness.get("has_gaps", False) else "ready"),
        "rule_version": RULE_VERSION,
        "disclaimer": DISCLAIMER,
        "emergency": emergency,
        "cold_heat": cold_heat,
        "contraindications": contra,
        "relative_warnings": warnings,
        "population_adjustments": pop_adjusts,
        "six_channel_hypotheses": hypotheses,
        "retrieved_clauses": retrieved_clauses,
        "candidate_formulas": filtered_formulas,
        "verification_inquiry": verification,
        "info_completeness": completeness,
        "pulse_fallback": pulse_fallback,
        "patient_profile": profile,
        "keywords": keywords,
        "negations": negations,
        "normalized_query": normalized,
        "data_stats": {
            "clauses_count": len(data["clauses"]),
            "formulas_count": len(data["formulas"]),
            "rules_count": len(data["rules"]),
        },
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
