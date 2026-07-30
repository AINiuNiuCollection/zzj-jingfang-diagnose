"""
kb_modules - 经方知识库检索核心模块包

模块结构：
- config: 可调配置常量（权重/阈值/关键词映射）
- data_loader: 数据加载 + 缓存 + BM25 索引
- terminology: 术语映射（白话→文言/否定提取/六经检测）
- rule_engine: 规则引擎（急重症/寒热/禁忌/人群）
- retrieval: BM25 检索 + 方剂排序
- inquiry: 追问逻辑（验证性追问/信息完整性/必填项预检/脉象兜底）
- profile: 体质适配分析
- output: 输出组装
"""

from .config import Config
from .data_loader import DataLoader
from .terminology import normalize, extract_keywords, extract_negations, detect_six_channel, collect_patient_text
from .rule_engine import RuleEngine
from .retrieval import Retriever
from .inquiry import InquiryEngine
from .profile import ProfileAnalyzer
from .output import assemble_output


class JingFangKB:
    """经方知识库检索主类，管理数据加载和检索流程"""

    def __init__(self, assets_dir=None):
        from pathlib import Path
        self.assets_dir = assets_dir or Path(__file__).resolve().parent.parent.parent / "assets"
        self._data_loader = DataLoader(self.assets_dir)
        self._rule_engine = RuleEngine()
        self._retriever = None
        self._inquiry_engine = InquiryEngine()
        self._profile_analyzer = ProfileAnalyzer()

    def search(self, patient_input: dict) -> dict:
        """主检索入口：接收结构化患者输入 dict，返回检索结果

        patient_input 字段：
            chief, symptoms, pulse, tongue, sweat, chill_fever,
            stool_urine, want_clothing, thirst, population,
            treatment_history, history, extra
        """
        from argparse import Namespace
        # 确保所有字段都有默认值
        defaults = {"tongue": "", "want_clothing": "", "thirst": "", "population": "普通成人",
                     "treatment_history": "未经治疗", "history": "", "extra": ""}
        merged = {**defaults, **{k: v or "" for k, v in patient_input.items()}}
        args = Namespace(**merged)
        if not getattr(args, 'population', '').strip():
            setattr(args, 'population', '普通成人')
        if not getattr(args, 'treatment_history', '').strip():
            setattr(args, 'treatment_history', '未经治疗')
        return self.search_from_args(args)

    def search_from_args(self, args) -> dict:
        """从 argparse 命名空间检索（兼容现有 CLI 调用方式）"""
        data = self._data_loader.load()

        # 懒初始化 Retriever（需要 BM25 索引）
        if self._retriever is None:
            self._retriever = Retriever(data, self._data_loader)

        all_text = collect_patient_text(args)

        # 0. 必填项预检
        required_check = self._inquiry_engine.check_required_fields(args)
        if required_check["has_missing"]:
            pulse_fallback = self._inquiry_engine.generate_pulse_fallback(args, [], data) if not getattr(args, 'pulse', '').strip() else None
            return assemble_output(
                status="need_inquiry",
                rule_version=Config.RULE_VERSION,
                required_fields_check=required_check,
                emergency=None, cold_heat=None, contra=None,
                relative_warnings=[], population_adjustments=[],
                hypotheses=[], retrieved_clauses=[], candidate_formulas=[],
                verification={"need_verification": False, "inquiry_point": "", "target_formula": ""},
                completeness={"has_gaps": True, "gaps": [
                    {"field": r["field"], "importance": "high", "question": r["question"], "reason": r["reason"]}
                    for r in required_check["missing"]
                ]},
                profile=None, pulse_fallback=pulse_fallback,
                keywords=[], negations=[], normalized_query="",
                data=data, args=args,
                chapter_context=[],
            )

        # 1. 术语映射 + 否定提取
        normalized = normalize(all_text, data["dictionary"])
        keywords = extract_keywords(all_text, data["dictionary"])
        negations = extract_negations(all_text, data["dictionary"])

        # 2. 规则引擎
        emergency = self._rule_engine.check_emergency(all_text, data["emergency"])
        cold_heat = self._rule_engine.check_cold_heat(args, all_text, data)
        contra = self._rule_engine.check_contraindications(all_text, data["formulas"], data["rules"], args.population)
        warnings = self._rule_engine.check_relative_warnings(all_text, data["rules"])
        pop_adjusts = self._rule_engine.check_population(data["rules"], args.population)

        # 3. 六经候选
        six_channel_candidates = detect_six_channel(all_text, data)

        # 4. BM25 条文检索（提前到六经候选之后，以便兜底逻辑使用）
        retrieved_clauses = self._retriever.search_clauses(keywords, top_k=Config.BM25_TOP_K)

        # 4.5 病篇章节上下文：根据命中条文提取病篇全貌
        chapter_context = self._retriever.build_chapter_context(retrieved_clauses, data)

        # 3.5 六经候选兜底：当 detect_six_channel 返回空时，从 BM25 Top 条文的 six_channel 统计推断
        if not six_channel_candidates and retrieved_clauses:
            clause_channel_scores = {}
            for item in retrieved_clauses:
                clause = item.get("clause", {})
                ch = clause.get("six_channel", "")
                if ch and ch != "通用":
                    clause_channel_scores[ch] = clause_channel_scores.get(ch, 0) + 1
            if clause_channel_scores:
                six_channel_candidates = sorted(
                    [{"channel": ch, "score": sc, "exclusive_score": sc, "shared_score": 0, "layers_hit": {"bm25_fallback"}}
                     for ch, sc in clause_channel_scores.items()],
                    key=lambda x: x["score"], reverse=True
                )

        # 统一处理：detect_six_channel 返回 [{channel, score, ...}]，兜底也已统一为同格式
        total_score = sum(item.get("score", 0) for item in six_channel_candidates)
        hypotheses = []
        for item in six_channel_candidates[:3]:
            channel = item["channel"] if isinstance(item, dict) else item[0]
            score = item.get("score", 0) if isinstance(item, dict) else item[1]
            conf = score / total_score if total_score > 0 else 0
            hypotheses.append({"channel": channel, "confidence": round(conf, 3)})

        # 5. 方剂匹配（层级加权）
        warned_cats = {w["category"] for w in warnings}
        formula_results = self._retriever.rank_formulas(
            normalized, contra["excluded_ids"], warned_cats, contra.get("orange_warnings", [])
        )

        # 否定排除
        filtered_formulas = []
        for item in formula_results:
            f = item["formula"]
            excluded = any(neg in f.get("core_indicators", []) for neg in negations)
            if not excluded:
                filtered_formulas.append(item)

        # 6. 验证性追问
        verification = self._inquiry_engine.check_verification_inquiry(filtered_formulas, args, all_text, data)

        # 7. 信息完整性检查
        completeness = self._inquiry_engine.check_info_completeness(args, filtered_formulas, data)

        # 8. 体质适配分析
        profile = self._profile_analyzer.check_patient_profile(all_text, args, filtered_formulas)

        # 9. 脉象缺失兜底方案
        pulse_value = getattr(args, 'pulse', '') or ''
        pulse_fallback = None
        if not pulse_value.strip() or pulse_value.strip() in ("无法提供", "无法提供脉象", "不清楚", "不知道", "无"):
            pulse_fallback = self._inquiry_engine.generate_pulse_fallback(args, hypotheses, data)

        # 10. 判定状态
        if emergency:
            status = "emergency"
        elif cold_heat.get("need_inquiry") or verification.get("need_verification") or completeness.get("has_gaps"):
            status = "need_inquiry"
        else:
            status = "ready"

        return assemble_output(
            status=status,
            rule_version=Config.RULE_VERSION,
            emergency=emergency, cold_heat=cold_heat, contra=contra,
            relative_warnings=warnings, population_adjustments=pop_adjusts,
            hypotheses=hypotheses, retrieved_clauses=retrieved_clauses,
            candidate_formulas=filtered_formulas,
            verification=verification, completeness=completeness,
            pulse_fallback=pulse_fallback, profile=profile,
            keywords=keywords, negations=negations, normalized_query=normalized,
            data=data, args=args,
            chapter_context=chapter_context,
        )
