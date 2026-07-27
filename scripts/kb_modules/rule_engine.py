"""
rule_engine - 规则引擎

统一规则检查接口：急重症预判、寒热鉴别、绝对/相对禁忌、人群禁忌。
关键改进：急重症阈值从 emergency.json 数据驱动，寒热关键词从 Config 读取，禁汗规则动态推导。
"""

from .config import Config


class RuleEngine:
    """规则引擎：急重症/寒热/禁忌/人群"""

    def check_emergency(self, all_text: str, emergencies: list) -> dict:
        """急重症预判

        关键改进：阈值从 emergency["threshold"] 读取，
        无 threshold 字段时回退到 Config.EMERGENCY_DEFAULT_THRESHOLD。
        """
        for em in emergencies:
            hit_count = sum(1 for ind in em.get("indicators", []) if ind in all_text)
            threshold = em.get("threshold", Config.EMERGENCY_DEFAULT_THRESHOLD)
            if hit_count >= threshold:
                return {
                    "name": em["name"],
                    "treatment": em["treatment"],
                    "main_formula": em["main_formula"],
                    "source_clause": em["source_clause"],
                    "hit_indicators": [ind for ind in em.get("indicators", []) if ind in all_text],
                    "category": em.get("category", ""),
                    "treatment_note": em.get("treatment_note", ""),
                }
        return None

    def check_cold_heat(self, args, all_text: str) -> dict:
        """真假寒热鉴别

        关键改进：关键词从 Config.COLD_HEAT_KEYWORDS 读取，不再硬编码。
        """
        kw = Config.COLD_HEAT_KEYWORDS
        has_extreme_heat = any(k in all_text for k in kw["extreme_heat"])
        has_extreme_cold = any(k in all_text for k in kw["extreme_cold"])
        want_clothing = getattr(args, 'want_clothing', '') or ""
        has_heat = "发热" in (getattr(args, 'chill_fever', '') or "") or "热" in (getattr(args, 'chief', '') or "")
        has_cold = any(k in (getattr(args, 'chill_fever', '') or "") for k in ["恶寒", "怕冷", "恶风"])
        pulse = getattr(args, 'pulse', '') or ""
        thirst = getattr(args, 'thirst', '') or ""

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
                is_true_heat = any(k in pulse for k in kw["true_heat_pulse"]) and thirst == "渴喜冷饮"
                if is_true_heat:
                    return {"conclusion": "真热（脉象与渴饮佐证）", "need_inquiry": False, "inquiry_points": []}
                if not pulse or not thirst:
                    return {"conclusion": "寒热真假未明", "need_inquiry": True,
                            "inquiry_points": ["极端热象需鉴别真假寒热（第11条）", "请补充欲近衣情况、脉象、饮水情况"]}
            if has_extreme_cold:
                is_true_cold = any(k in pulse for k in kw["true_cold_pulse"])
                if is_true_cold:
                    return {"conclusion": "真寒（脉象佐证）", "need_inquiry": False, "inquiry_points": []}
                if not pulse:
                    return {"conclusion": "寒热真假未明", "need_inquiry": True,
                            "inquiry_points": ["极端寒象需鉴别真假寒热（第11条）", "请补充欲近衣情况、脉象"]}

        if has_heat or has_cold:
            return {"conclusion": "寒热表现明确（普通外感），非极端寒热", "need_inquiry": False, "inquiry_points": []}
        return {"conclusion": "未涉及寒热", "need_inquiry": False, "inquiry_points": []}

    def check_contraindications(self, all_text: str, formulas: list, rules: list, population: str) -> dict:
        """绝对禁忌红色拦截 + 后世安全规则橙级处理

        关键改进：禁汗规则从 rules 动态推导，不再硬编码 ID 集合。
        """
        excluded_ids = []
        excluded_categories = []
        triggered = []
        orange_warnings = []

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
                orange_warnings.append({
                    "id": rule["id"],
                    "description": rule.get("description", ""),
                    "classical_precedent": rule.get("classical_precedent"),
                    "contraindicated_pairs": self._extract_contraindicated_pairs(rule),
                })

        # 类别 → 方剂ID
        for formula_cat in excluded_categories:
            for f in formulas:
                if f.get("formula_category") == formula_cat and f["id"] not in excluded_ids:
                    excluded_ids.append(f["id"])

        # 禁汗规则额外排除含麻黄方剂（动态推导）
        diaphoretic_triggered = any(
            self._is_diaphoretic_rule(r)
            for r in rules if r["id"] in triggered
        )
        if diaphoretic_triggered:
            for f in formulas:
                if any(c.get("herb") == "麻黄" for c in f.get("composition", [])):
                    if f["id"] not in excluded_ids:
                        excluded_ids.append(f["id"])

        return {"excluded_ids": excluded_ids, "excluded_categories": excluded_categories,
                "triggered": triggered, "orange_warnings": orange_warnings}

    def _is_diaphoretic_rule(self, rule: dict) -> bool:
        """判断规则是否为禁汗规则（动态推导，替代硬编码 ID 集合）

        推导逻辑：target_formula_category 包含 "发汗" 或 "解表" 的绝对禁忌规则。
        兼容原有 R-CONTRA-001~005 的判断。
        """
        target_cat = rule.get("target_formula_category", "")
        desc = rule.get("description", "")
        if rule.get("category") != "absolute_contraindication":
            return False
        # 方法1：检查 target_formula_category
        if any(kw in target_cat for kw in ["发汗", "解表", "汗法"]):
            return True
        # 方法2：检查描述中是否包含禁汗语义
        if any(kw in desc for kw in ["不可发汗", "禁汗", "不可汗", "慎不可发汗"]):
            return True
        return False

    @staticmethod
    def _extract_contraindicated_pairs(rule: dict) -> list:
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

    def check_relative_warnings(self, all_text: str, rules: list) -> list:
        """相对禁忌黄色警示"""
        warnings = []
        for rule in rules:
            if rule.get("category") != "relative_contraindication":
                continue
            if any(s in all_text for s in rule.get("trigger_symptoms", [])):
                warnings.append({"category": rule["target_formula_category"], "description": rule["description"]})
        return warnings

    def check_population(self, rules: list, population: str) -> list:
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
