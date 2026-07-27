"""
profile - 体质适配分析

分析患者体型、用药史、基础病等特征，评估候选方的适配性差异。
"""

from .config import Config


class ProfileAnalyzer:
    """体质适配分析器"""

    def check_patient_profile(self, all_text: str, args, formulas: list) -> dict:
        """患者体质适配分析"""
        result = {"physique_assessment": [], "dose_notes": [], "formula_adjustments": []}

        # === 1. 体型评估 ===
        is_emaciated = any(kw in all_text for kw in ["消瘦", "瘦弱", "羸瘦", "BMI"])
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

        # === 5. 候选方微调建议 ===
        for item in formulas[:3]:
            f = item["formula"]
            f_name = f.get("name", "")
            f_composition = f.get("composition", [])
            adjustments = []

            # 5a. 小便不利 → 加茯苓
            has_urine_issue = any(kw in all_text for kw in ["小便不利", "小便少", "小便不通", "水排不出", "尿少"])
            has_fuling = any(c.get("herb") == "茯苓" for c in f_composition)
            if has_urine_issue and not has_fuling and f_name != "五苓散":
                adjustments.append({
                    "type": "加味", "herb": "茯苓",
                    "reason": "患者有小便不利/水入不化之证，加茯苓利水渗湿、健脾宁心",
                    "jingfang_basis": "SHL-096「心下悸、小便不利者，去黄芩加茯苓」；SHL-067茯苓桂枝白术甘草汤治水气"
                })

            # 5b. 心烦/易怒 → 加黄芩
            has_irritability = any(kw in all_text for kw in ["心烦", "易怒", "脾气不好", "烦躁", "不安"])
            has_huangqin = any(c.get("herb") == "黄芩" for c in f_composition)
            if has_irritability and not has_huangqin:
                adjustments.append({
                    "type": "加味", "herb": "黄芩/栀子",
                    "reason": "患者有心烦易怒表现，可加黄芩清上焦热或栀子除烦",
                    "jingfang_basis": "SHL-096小柴胡汤证「心烦喜呕」用黄芩；SHL-076栀子豉汤治「虚烦不得眠」"
                })

            # 5c. 纳差/脾虚 → 加人参
            has_spleen_deficiency = any(kw in all_text for kw in ["不消化", "食后", "消瘦", "脾虚", "纳差"])
            has_renshen = any(c.get("herb") == "人参" or c.get("herb") == "党参" for c in f_composition)
            if has_spleen_deficiency and not has_renshen:
                adjustments.append({
                    "type": "加味", "herb": "人参（或党参）",
                    "reason": "患者脾虚明显（食不化、形瘦），加人参补中益气",
                    "jingfang_basis": "SHL-386理中丸治「寒多不用水」用人参；李东垣参考，但原典中人参即用于中虚"
                })

            # 5d. 消瘦剂量调整
            if is_emaciated:
                adjustments.append({
                    "type": "剂量调整", "herb": "全方",
                    "reason": "患者极度消瘦，须以调理量（×0.6）起始，不可峻猛",
                    "jingfang_basis": "SHL-273太阴病禁下；虚人宜缓图"
                })

            if adjustments:
                result["formula_adjustments"].append({
                    "formula_name": f_name, "adjustments": adjustments
                })

        return result
