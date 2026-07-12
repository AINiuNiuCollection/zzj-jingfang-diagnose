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


def load_json(filename):
    """从 assets 加载 JSON"""
    path = ASSETS_DIR / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    """绝对禁忌红色拦截"""
    excluded_ids = []
    excluded_categories = []
    triggered = []

    for rule in rules:
        if rule.get("category") != "absolute_contraindication":
            continue
        hit = any(s in all_text for s in rule.get("trigger_symptoms", []))
        if rule.get("trigger_conditions", {}).get("population") == population:
            hit = True
        if hit:
            cat = rule.get("target_formula_category", "")
            if cat and cat not in excluded_categories:
                excluded_categories.append(cat)
            triggered.append(rule["id"])

    # 类别 → 方剂ID
    for cat in excluded_categories:
        for f in formulas:
            if f.get("formula_category") == cat and f["id"] not in excluded_ids:
                excluded_ids.append(f["id"])

    # 禁汗规则额外排除含麻黄方剂
    diaphoretic_ids = {"R-CONTRA-001", "R-CONTRA-002", "R-CONTRA-003", "R-CONTRA-004", "R-CONTRA-005"}
    if any(rid in triggered for rid in diaphoretic_ids):
        for f in formulas:
            if any(c.get("herb") == "麻黄" for c in f.get("composition", [])):
                if f["id"] not in excluded_ids:
                    excluded_ids.append(f["id"])

    return {"excluded_ids": excluded_ids, "excluded_categories": excluded_categories, "triggered": triggered}


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


def rank_formulas(formulas, query, excluded_ids, warned_categories):
    """层级加权排序"""
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
        if score > 0:
            results.append({"formula": f, "score": score, "core_hits": core_hits,
                            "main_hits": main_hits, "pulse_hits": pulse_hits})
    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]


# ========== 主流程 ==========

def check_verification_inquiry(filtered_formulas, args, all_text):
    """验证性追问（v2增强版）：方证匹配后系统检查关键鉴别信息完整性

    覆盖6类方证场景，确保匹配Top1方剂所需的关键鉴别信息已收集完整。
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

    # ---- 第1类：有汗/无汗分水岭（桂枝汤类 vs 麻黄汤类） ----
    if top1_name in ("桂枝汤", "桂枝加葛根汤", "桂枝加附子汤", "小建中汤"):
        if not args.sweat or args.sweat == "不确定":
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}，其核心指征含「汗出」，但汗出情况未明确。请确认：□有汗 □无汗",
                    "target_formula": top1_name}
    if top1_name in ("麻黄汤", "大青龙汤", "葛根汤"):
        if not args.sweat or args.sweat == "不确定":
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}，其核心指征含「无汗」，但汗出情况未明确。请确认：□有汗 □无汗",
                    "target_formula": top1_name}

    # ---- 第2类：少阳/阳明分水岭（有无里实） ----
    if top1_name in ("小柴胡汤", "大柴胡汤"):
        if not args.stool_urine:
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}，需确认有无阳明里实。请补充：有无腹胀满/不大便/心下硬？",
                    "target_formula": top1_name}

    # ---- 第3类：攻下方需确认表证已解 ----
    if top1_name in ("大承气汤", "小承气汤", "调胃承气汤"):
        if not args.chill_fever:
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（攻下方），需确认表证是否已解。请补充：当前是否仍有恶寒/发热等表证？",
                    "target_formula": top1_name}

    # ---- 第4类：温阳方需排除真热假寒 ----
    if top1_name in ("四逆汤", "真武汤", "附子汤", "干姜附子汤"):
        if not args.want_clothing and ("四肢厥冷" in all_text or "大寒" in all_text):
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（温阳方），患者有寒象但欲近衣情况未知，需排除真热假寒。请确认：患者虽怕冷，是否反而不想多穿衣服？",
                    "target_formula": top1_name}

    # ---- 第5类（新增）：泻心汤类—需确认痞证性质（心下痛否） ----
    if top1_name in ("半夏泻心汤", "生姜泻心汤", "甘草泻心汤", "大黄黄连泻心汤", "旋覆代赭汤"):
        if "按之" not in all_text and "压痛" not in all_text and "硬痛" not in all_text:
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（泻心汤类/痞证方），需确认心下痞性质。请确认：患者心下（胃脘部）是 □但满不痛（痞） □硬痛拒按（须排除结胸）",
                    "target_formula": top1_name}

    # ---- 第6类（新增）：五苓散/苓桂剂类—需确认小便与渴饮情况 ----
    if top1_name in ("五苓散", "猪苓汤", "茯苓桂枝白术甘草汤"):
        if not args.stool_urine or "小便" not in all_text:
            return {"need_verification": True,
                    "inquiry_point": f"Top1候选方为{top1_name}（利水方），需确认小便与渴饮情况。请补充：□小便不利/小便自利 □口渴/不渴",
                    "target_formula": top1_name}

    return {"need_verification": False, "inquiry_point": "", "target_formula": ""}


def check_info_completeness(args, filtered_formulas):
    """信息完整性检查（v2新增）：在报告生成前系统检查信息缺口

    检查核心四诊信息是否齐全，根据当前Top1候选方的需求，识别
    对辨证有决定性影响但仍缺失的关键信息。

    Returns:
        dict: {"has_gaps": bool, "gaps": [{"field": str, "importance": str, "question": str, "reason": str}]}
    """
    gaps = []

    # 1. 脉象缺失（一级权重）— 仲景核心
    if not args.pulse or args.pulse == "未记录":
        gaps.append({
            "field": "pulse",
            "importance": "high",
            "question": "脉象未记录。脉诊为仲景辨证核心，请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）",
            "reason": "仲景脉证合参，脉象为一级辨证依据。如SHL-001:太阳之为病，脉浮；无脉象则六经定性与方证匹配均会降权"
        })

    # 2. 当前Top1确定后，检查该方所需的关键信息是否齐全
    if filtered_formulas:
        top1 = filtered_formulas[0]["formula"]
        top1_core = top1.get("core_indicators", [])
        top1_exclusion = top1.get("exclusion_indicators", [])
        top1_name = top1.get("name", "")

        # 泻心汤类：没有"按之濡/按之硬"的腹部触诊信息
        if top1_name in ("半夏泻心汤", "生姜泻心汤", "甘草泻心汤", "旋覆代赭汤"):
            if not args.extra or ("按" not in args.extra and "痞" not in args.extra and "腹" not in args.extra):
                gaps.append({
                    "field": "abdominal_palpation",
                    "importance": "high",
                    "question": f"Top1候选为{top1_name}（痞证方）。腹部触诊对鉴别痞证与结胸至关重要。请补充：脘腹部按压感觉如何？□但满不痛（痞证） □硬痛拒按（结胸） □无异常",
                    "reason": "SHL-149：'但满而不痛，此为痞' vs '心下满而硬痛者，此为结胸'"
                })

        # 苓桂剂/利水方：缺少小便细节
        if top1_name in ("五苓散", "猪苓汤", "茯苓桂枝白术甘草汤", "真武汤"):
            if not args.stool_urine or "小便" not in args.stool_urine:
                gaps.append({
                    "field": "urine_detail",
                    "importance": "high",
                    "question": f"Top1候选为{top1_name}（利水方），小便情况是关键鉴别点。请补充：□小便不利/小便自利 □小便清/黄 □有无水肿？",
                    "reason": "五苓散核心指征为'小便不利、渴欲饮水'（SHL-071）"
                })

    # 3. 患者有明显特殊体质但缺少相关描述
    if args.population == "素有宿疾" or "激素" in str(args.extra).lower() or "泼尼松" in str(args.extra):
        if not args.treatment_history or args.treatment_history == "未经治疗":
            gaps.append({
                "field": "medication_detail",
                "importance": "medium",
                "question": "患者有长期用药史（激素/免疫抑制剂等），对体质有重要影响。请补充具体用药情况（药名、剂量、疗程）",
                "reason": "长期使用激素相当于'壮火食气'，影响病机判断，但属辅助参考信息"
            })

    # 4. 消瘦明显（BMI过低）但缺少相关说明
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
    formula_results = rank_formulas(data["formulas"], normalized, contra["excluded_ids"], warned_cats)

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

    # 9. 输出结果
    output = {
        "status": "emergency" if emergency else ("need_inquiry" if cold_heat["need_inquiry"] else "ready"),
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
