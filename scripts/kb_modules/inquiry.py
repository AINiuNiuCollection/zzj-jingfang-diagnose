"""
inquiry - 追问逻辑模块

包含：验证性追问、信息完整性检查、必填项预检、脉象缺失兜底方案。
关键改进：验证性追问关键词映射从 Config 读取。
"""

from .config import Config


class InquiryEngine:
    """追问引擎：验证性追问 + 信息完整性 + 必填项预检 + 脉象兜底"""

    def check_verification_inquiry(self, filtered_formulas: list, args, all_text: str) -> dict:
        """验证性追问（v3通用版）

        关键改进：关键词映射从 Config.VERIFICATION_KEYWORD_MAP 读取。
        """
        if not filtered_formulas:
            return {"need_verification": False, "inquiry_point": "", "target_formula": ""}

        top1 = filtered_formulas[0]["formula"]
        top1_name = top1.get("name", "")
        top1_core = top1.get("core_indicators", [])
        top1_exclusion = top1.get("exclusion_indicators", [])
        cfg = Config

        # ---- 通用机制：基于 Config.VERIFICATION_KEYWORD_MAP 自动检测 ----
        all_indicators = list(top1_core) + list(top1_exclusion)
        for indicator in all_indicators:
            if indicator in cfg.VERIFICATION_KEYWORD_MAP:
                mapping = cfg.VERIFICATION_KEYWORD_MAP[indicator]
                field = mapping["field"]
                if field is not None:
                    field_value = getattr(args, field, "") or ""
                    if not field_value.strip():
                        return {
                            "need_verification": True,
                            "inquiry_point": f"Top1候选方为{top1_name}，其核心指征含「{indicator}」，但{mapping['reason']}。{mapping['question']}",
                            "target_formula": top1_name
                        }
                elif indicator == "但欲寐" and "但欲寐" not in all_text and "嗜卧" not in all_text and "萎靡" not in all_text:
                    return {
                        "need_verification": True,
                        "inquiry_point": f"Top1候选方为{top1_name}，{mapping['reason']}。{mapping['question']}",
                        "target_formula": top1_name
                    }

        # ---- 兜底场景 ----
        # 兜底1：泻心汤类
        if top1_name in cfg.XIE_XIN_FORMULAS:
            if "按之" not in all_text and "压痛" not in all_text and "硬痛" not in all_text and "喜按" not in all_text and "拒按" not in all_text and "痞" not in all_text:
                return {"need_verification": True,
                        "inquiry_point": f"Top1候选方为{top1_name}（泻心汤类/痞证方），需确认心下痞性质。请确认：患者心下（胃脘部）是 □但满不痛（痞） □硬痛拒按（须排除结胸）",
                        "target_formula": top1_name}

        # 兜底2：攻下方需确认表证已解
        if top1_name in cfg.GONG_XIA_FORMULAS:
            if not getattr(args, 'chill_fever', ''):
                return {"need_verification": True,
                        "inquiry_point": f"Top1候选方为{top1_name}（攻下方），需确认表证是否已解。请补充：当前是否仍有恶寒/发热等表证？",
                        "target_formula": top1_name}

        # 兜底3：温阳方需排除真热假寒
        if top1_name in cfg.WEN_YANG_FORMULAS:
            if not getattr(args, 'want_clothing', '') and ("四肢厥冷" in all_text or "大寒" in all_text):
                return {"need_verification": True,
                        "inquiry_point": f"Top1候选方为{top1_name}（温阳方），患者有寒象但欲近衣情况未知，需排除真热假寒。请确认：患者虽怕冷，是否反而不想多穿衣服？",
                        "target_formula": top1_name}

        return {"need_verification": False, "inquiry_point": "", "target_formula": ""}

    def check_info_completeness(self, args, filtered_formulas: list) -> dict:
        """信息完整性检查（v3增强版）"""
        gaps = []
        cfg = Config

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
                extra_hint = ""
                if field_name == "pulse":
                    extra_hint = "（若无法提供脉象，系统将自动生成脉象缺失兜底参考：按六经脉象纲领列出不同脉象对应的方剂方向，如脉浮缓→桂枝汤、脉沉迟→理中汤辈、脉弦→小柴胡汤等，详见输出pulse_fallback字段）"
                gaps.append({
                    "field": field_name, "importance": importance,
                    "question": f"{display_name}未记录。{reason}。请补充{display_name}{extra_hint}",
                    "reason": reason
                })

        # === 2. 强烈推荐项按需校验 ===
        if filtered_formulas:
            top1 = filtered_formulas[0]["formula"]
            top1_core = top1.get("core_indicators", [])
            top1_exclusion = top1.get("exclusion_indicators", [])
            top1_name = top1.get("name", "")
            all_indicators = list(top1_core) + list(top1_exclusion)

            # 2a. 渴饮
            thirst_keywords = ["口渴", "渴欲饮水", "不渴", "渴不欲饮", "渴饮", "消渴"]
            if any(kw in all_indicators for kw in thirst_keywords):
                thirst_value = getattr(args, 'thirst', '') or ""
                if not thirst_value.strip():
                    gaps.append({
                        "field": "thirst", "importance": "high",
                        "question": f"Top1候选为{top1_name}，其核心指征涉及渴饮，但渴饮情况未填写。请确认：□口渴喜冷饮 □口渴不欲饮 □口渴欲饮热 □不口渴",
                        "reason": "渴饮是真假寒热鉴别关键与五苓散证判定关键（SHL-073）"
                    })

            # 2b. 欲近衣
            if top1_name in cfg.COLD_HEAT_FORMULAS:
                want_clothing_value = getattr(args, 'want_clothing', '') or ""
                if not want_clothing_value.strip():
                    gaps.append({
                        "field": "want_clothing", "importance": "high",
                        "question": f"Top1候选为{top1_name}，需排除寒热真假（第11条）。请确认：□欲近衣（怕冷想加衣） □不欲近衣（怕热想减衣） □正常",
                        "reason": "真寒假热/真热假寒鉴别核心（第11条），寒热颠倒则治则方向完全相反"
                    })

            # 2c. 腹诊
            if top1_name in cfg.ABDOMINAL_FORMULAS:
                extra_value = getattr(args, 'extra', '') or ""
                if not extra_value.strip() or not any(kw in extra_value for kw in ["按", "压痛", "硬痛", "喜按", "拒按", "痞", "腹"]):
                    gaps.append({
                        "field": "abdominal_palpation", "importance": "high",
                        "question": f"Top1候选为{top1_name}，腹部触诊对鉴别至关重要。请补充：脘腹部按压感觉如何？□但满不痛（痞证） □硬痛拒按（结胸） □腹满按之痛 □柔软无压痛",
                        "reason": "SHL-149：'但满而不痛，此为痞' vs '心下满而硬痛者，此为结胸'"
                    })

        # === 3. 体质关键项校验 ===
        extra_value = getattr(args, 'extra', '') or ""
        has_bmi_info = "BMI" in extra_value or "消瘦" in extra_value or "体重" in extra_value
        if not has_bmi_info:
            chief_value = getattr(args, 'chief', '') or ""
            symptoms_value = getattr(args, 'symptoms', '') or ""
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
                    "field": "physique_info", "importance": "medium",
                    "question": f"缺少{'/'.join(missing_items)}，影响剂量倍率计算。请补充：{'/'.join(missing_items)}",
                    "reason": "年龄/体重是剂量倍率核心依据：老年→调理量×0.6，极度消瘦(BMI<17)→调理量×0.6，急证重证→急证量×2.0"
                })

        # 3b. 激素/免疫抑制用药史
        if getattr(args, 'population', '') == "素有宿疾" or "激素" in str(extra_value).lower() or "泼尼松" in str(extra_value):
            if not getattr(args, 'treatment_history', '') or getattr(args, 'treatment_history', '') == "未经治疗":
                gaps.append({
                    "field": "medication_detail", "importance": "medium",
                    "question": "患者有长期用药史（激素/免疫抑制剂等），对体质有重要影响。请补充具体用药情况（药名、剂量、疗程）",
                    "reason": "长期使用激素相当于'壮火食气'，影响病机判断，但属辅助参考信息"
                })

        # 3c. 极低BMI
        if "消瘦" in str(extra_value) or "BMI" in str(extra_value):
            try:
                import re as _re
                bmi_match = _re.search(r'BMI[：: ]*([0-9.]+)', str(extra_value))
                if bmi_match and float(bmi_match.group(1)) < 17.0:
                    gaps.append({
                        "field": "weight_history", "importance": "medium",
                        "question": "患者BMI低于17.0（重度消瘦），请补充：消瘦是长期如此还是近期加重？有无明显体重下降？",
                        "reason": "极度消瘦影响方剂选择与剂量调整，太阴脾虚/胃阴虚等判断需要此信息"
                    })
            except Exception:
                pass

        return {"has_gaps": len(gaps) > 0, "gaps": gaps}

    def check_required_fields(self, args) -> dict:
        """必填项预检"""
        required = [
            ("chief", "主诉", "请描述患者最主要的症状及持续时间"),
            ("symptoms", "症状列表", "请列出所有症状，用逗号分隔"),
            ("pulse", "脉象", "请补充脉象（如：浮/沉/弦/数/缓/紧/弱/细等）。若无法提供，请回复'无法提供脉象'，系统将输出脉象缺失兜底参考"),
            ("chill_fever", "寒热情况", "请确认寒热：□恶寒 □恶风 □发热 □往来寒热 □无明显寒热"),
            ("sweat", "汗出情况", "请确认汗出：□有汗 □无汗 □汗出不止 □自汗 □正常"),
            ("stool_urine", "二便情况", "请描述大便和小便情况"),
        ]
        missing = []
        for field_name, display_name, question in required:
            field_value = getattr(args, field_name, "") or ""
            if not field_value.strip():
                missing.append({
                    "field": field_name, "field_display": display_name,
                    "question": question,
                    "reason": f"{display_name}为必填项，缺失将严重影响辨证准确性"
                })
        return {"has_missing": len(missing) > 0, "missing": missing}

    def generate_pulse_fallback(self, args, six_channel_hypotheses: list) -> dict:
        """脉象缺失兜底方案"""
        cfg = Config

        # 从已有症状推断最可能的六经方向
        from .terminology import collect_patient_text
        symptom_text = collect_patient_text(args)
        likely_channels = set()

        for hyp in six_channel_hypotheses[:2]:
            ch = hyp.get("channel", "")
            if ch:
                likely_channels.add(ch)

        for keyword, channels in cfg.PULSE_KEYWORD_TO_CHANNEL.items():
            if keyword in symptom_text:
                for ch in channels:
                    likely_channels.add(ch)

        priority_channels = [ch for ch in ["太阳", "阳明", "少阳", "太阴", "少阴", "厥阴"] if ch in likely_channels]

        full_map = {}
        for channel, data in cfg.PULSE_FALLBACK_MAP.items():
            full_map[channel] = {
                "纲领": data["纲领"],
                "脉象方向": data["脉象方向"],
                "is_priority": channel in priority_channels,
            }

        summary_parts = ["【脉象缺失兜底参考】脉象为仲景辨证一级依据，以下为不同脉象对应的方剂方向，供执业医师参考："]
        if priority_channels:
            summary_parts.append(f"\n▶ 最可能方向（基于已有症状推断）：")
            for ch in priority_channels:
                ch_data = cfg.PULSE_FALLBACK_MAP.get(ch, {})
                summary_parts.append(f"  {ch}（{ch_data.get('纲领', '')}）：")
                for item in ch_data.get("脉象方向", []):
                    summary_parts.append(f"    {item['脉象']} → {item['方剂']}（{item['条文']}，{item['提示']}）")

        summary_parts.append(f"\n▶ 全部六经脉象参考：")
        for ch in ["太阳", "阳明", "少阳", "太阴", "少阴", "厥阴"]:
            ch_data = cfg.PULSE_FALLBACK_MAP.get(ch, {})
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
