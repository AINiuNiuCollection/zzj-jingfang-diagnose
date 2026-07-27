"""
terminology - 术语映射模块

纯函数模块，无状态。提供白话→文言映射、关键词提取、否定提取、六经检测、患者文本收集。

六经检测 detect_six_channel() 六层机制：
1. six_channel_keywords 精确匹配（含权重体系支持）
2. 脉象→六经映射（从 pulse_channel_map.json）
3. 语义关联→六经映射（从 dictionary.json → semantic_channel_map）
3.5. 矛盾组合辨证（从 contradictory_combos.json）
4. 否定确认层（从 dictionary.six_channel_negative_indicators）
5. 脉证组合协同（从 diagnostic_combos.json）

返回格式：[{"channel", "score", "exclusive_score", "shared_score", "layers_hit"}, ...]
"""


def normalize(text: str, dictionary: dict) -> str:
    """白话 → 文言标准术语映射"""
    symptom_map = dictionary.get("symptom_mapping", {})
    result = text
    for colloquial in sorted(symptom_map.keys(), key=len, reverse=True):
        classical = symptom_map[colloquial]
        if colloquial in result:
            result = result.replace(colloquial, classical)
    return result


def extract_keywords(text: str, dictionary: dict) -> list:
    """jieba 分词 + 术语映射"""
    normalized = normalize(text, dictionary)
    import jieba
    words = jieba.lcut(normalized)
    stop_words = {"的", "了", "是", "在", "有", "和", "与", "或", "及", "等",
                  "患者", "请问", "如何", "什么", "怎么", "是否", "目前",
                  "比较", "稍微", "明显", "持续", "反复", "已经", "最近"}
    return [w for w in words if len(w) >= 2 and w not in stop_words]


def extract_negations(text: str, dictionary: dict) -> list:
    """否定提取 → 排除清单"""
    negation_map = dictionary.get("negation_mapping", {})
    negations = []
    for neg_term, excluded in negation_map.items():
        if neg_term in text:
            negations.append(excluded)
    return list(dict.fromkeys(negations))


def _build_keyword_channel_map(dictionary: dict, pulse_map: dict, semantic_map: dict) -> dict:
    """构建全局 keyword→set(channels) 映射，用于判断关键词排他性

    返回 {keyword_string: set_of_channels}，包含三层所有关键词。
    """
    kw_ch_map = {}

    # Layer 1: six_channel_keywords
    six_channel_kw = dictionary.get("six_channel_keywords", {})
    for channel, keywords in six_channel_kw.items():
        for kw_entry in keywords:
            if isinstance(kw_entry, dict):
                kw = kw_entry.get("keyword", "")
            else:
                kw = kw_entry
            if kw:
                kw_ch_map.setdefault(kw, set()).add(channel)

    # Layer 2: pulse map
    for pulse_term, channels in pulse_map.items():
        kw_ch_map.setdefault(pulse_term, set()).update(channels)

    # Layer 3: semantic map
    for symptom, channels in semantic_map.items():
        kw_ch_map.setdefault(symptom, set()).update(channels)

    return kw_ch_map


def detect_six_channel(text: str, data: dict) -> list:
    """六经候选检测（增强版：六层检测 + 排他/共享分离）

    参数 data 为完整知识库数据（含 dictionary、pulse_channel_map、diagnostic_combos、contradictory_combos）。

    六层检测机制：
    1. six_channel_keywords 精确匹配（含权重体系支持）
    2. 脉象→六经映射（从 data["pulse_channel_map"]["mappings"]）
    3. 语义关联→六经映射（从 data["dictionary"]["semantic_channel_map"]）
    3.5. 矛盾组合辨证（从 data["contradictory_combos"]["combos"]）
    4. 否定确认层（从 dictionary.six_channel_negative_indicators）
    5. 脉证组合协同（从 data["diagnostic_combos"]["combos"]）

    返回 [{"channel", "score", "exclusive_score", "shared_score", "layers_hit"}, ...]
    按score降序排列。
    - exclusive_score: 仅属于1个经的关键词/映射的得分
    - shared_score: 属于2+个经的关键词/映射的得分
    - layers_hit: 哪些层贡献了得分 (keyword/pulse/semantic/contradictory/negation/combo)
    """
    dictionary = data.get("dictionary", {})

    normalized = normalize(text, dictionary)

    # 从 data 读取配置（替代原 Config 硬编码）
    pulse_channel_mappings = data.get("pulse_channel_map", {}).get("mappings", {})
    semantic_channel_map = dictionary.get("semantic_channel_map", {})
    diagnostic_combos = data.get("diagnostic_combos", {}).get("combos", [])
    contradictory_combos = data.get("contradictory_combos", {}).get("combos", [])

    # 预构建关键词→经映射
    kw_ch_map = _build_keyword_channel_map(
        dictionary, pulse_channel_mappings, semantic_channel_map
    )

    # 初始化每经的计分结构
    channels_data = {}  # channel -> {"score", "exclusive_score", "shared_score", "layers_hit"}

    def _add_score(channel: str, weight: float, keyword: str, layer: str):
        """向channel添加得分，自动区分exclusive/shared"""
        if channel not in channels_data:
            channels_data[channel] = {
                "score": 0.0, "exclusive_score": 0.0,
                "shared_score": 0.0, "layers_hit": set()
            }
        channels_data[channel]["score"] += weight
        channels_data[channel]["layers_hit"].add(layer)

        # 判断排他性：关键词出现在几个经中
        num_channels = len(kw_ch_map.get(keyword, {channel}))
        if num_channels <= 1:
            channels_data[channel]["exclusive_score"] += weight
        else:
            channels_data[channel]["shared_score"] += weight

    # ---- 第1层：six_channel_keywords 精确匹配（含权重体系支持） ----
    six_channel_kw = dictionary.get("six_channel_keywords", {})
    for channel, keywords in six_channel_kw.items():
        for kw_entry in keywords:
            if isinstance(kw_entry, dict):
                kw = kw_entry.get("keyword", "")
                weight = kw_entry.get("weight", 1.0)
            else:
                kw = kw_entry
                weight = 1.0
            if kw and kw in normalized:
                _add_score(channel, weight, kw, "keyword")

    # ---- 第2层：脉象→六经映射 ----
    for pulse_term, channels in pulse_channel_mappings.items():
        if pulse_term in normalized:
            for ch in channels:
                _add_score(ch, 1.5, pulse_term, "pulse")

    # ---- 第3层：语义关联→六经映射 ----
    for symptom, channels in semantic_channel_map.items():
        if symptom in normalized:
            for ch in channels:
                _add_score(ch, 1.0, symptom, "semantic")

    # ---- 第3.5层：矛盾组合辨证 ----
    for combo in contradictory_combos:
        sym_a = combo.get("symptom_a", "")
        sym_b = combo.get("symptom_b", "")
        if sym_a in normalized and sym_b in normalized:
            channel = combo.get("channel", "")
            bonus = combo.get("bonus", 3.0)
            # 矛盾组合天然排他，加到exclusive
            if channel not in channels_data:
                channels_data[channel] = {
                    "score": 0.0, "exclusive_score": 0.0,
                    "shared_score": 0.0, "layers_hit": set()
                }
            channels_data[channel]["score"] += bonus
            channels_data[channel]["exclusive_score"] += bonus
            channels_data[channel]["layers_hit"].add("contradictory")

    # ---- 第4层：否定确认层 ----
    neg_indicators = dictionary.get("six_channel_negative_indicators", {})
    for channel, indicators in neg_indicators.items():
        for ind in indicators:
            neg_term = ind.get("negation", "")
            weight = ind.get("weight", 1.0)
            if neg_term and neg_term in text:
                # 否定证据天然排他（只确认1个经），加到exclusive
                if channel not in channels_data:
                    channels_data[channel] = {
                        "score": 0.0, "exclusive_score": 0.0,
                        "shared_score": 0.0, "layers_hit": set()
                    }
                channels_data[channel]["score"] += weight
                channels_data[channel]["exclusive_score"] += weight
                channels_data[channel]["layers_hit"].add("negation")

    # ---- 第5层：脉证组合协同 ----
    for combo in diagnostic_combos:
        pulse_term = combo.get("pulse", "")
        symptom = combo.get("symptom", "")
        channel = combo.get("channel", "")
        bonus = combo.get("bonus", 3.0)
        # 检查脉象和症状同时存在
        if pulse_term in normalized and symptom in normalized:
            # 脉证组合天然排他，加到exclusive
            if channel not in channels_data:
                channels_data[channel] = {
                    "score": 0.0, "exclusive_score": 0.0,
                    "shared_score": 0.0, "layers_hit": set()
                }
            channels_data[channel]["score"] += bonus
            channels_data[channel]["exclusive_score"] += bonus
            channels_data[channel]["layers_hit"].add("combo")

    if not channels_data:
        return []

    # 组装结果
    results = []
    for channel, data_item in channels_data.items():
        results.append({
            "channel": channel,
            "score": data_item["score"],
            "exclusive_score": data_item["exclusive_score"],
            "shared_score": data_item["shared_score"],
            "layers_hit": data_item["layers_hit"],
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


def collect_patient_text(args) -> str:
    """收集患者输入文本（支持 argparse Namespace 和 dict）"""
    if isinstance(args, dict):
        parts = [
            args.get("chief", ""),
            " ".join(args.get("symptoms", "").split(",")),
            args.get("pulse", ""),
            args.get("tongue", ""),
            args.get("sweat", ""),
            args.get("chill_fever", ""),
            args.get("stool_urine", ""),
            args.get("thirst", ""),
            args.get("extra", ""),
        ]
        pop = args.get("population", "")
        if pop and pop != "普通成人":
            parts.append(pop)
        th = args.get("treatment_history", "")
        if th and th != "未经治疗":
            parts.append(th)
    else:
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
