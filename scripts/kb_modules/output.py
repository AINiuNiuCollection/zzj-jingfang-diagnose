"""
output - 输出组装

组装最终 JSON 输出，保持与原 retrieve_kb.py 完全一致的字段名和结构。
"""

from .config import Config


def assemble_output(
    status: str,
    rule_version: str,
    emergency,
    cold_heat,
    contra,
    relative_warnings: list,
    population_adjustments: list,
    hypotheses: list,
    retrieved_clauses: list,
    candidate_formulas: list,
    verification: dict,
    completeness: dict,
    pulse_fallback,
    profile,
    keywords: list,
    negations: list,
    normalized_query: str,
    data: dict,
    args=None,
    required_fields_check=None,
    chapter_context: list = None,
) -> dict:
    """组装最终 JSON 输出

    保持与原 retrieve_kb.py 输出字段完全一致。
    """
    output = {
        "status": status,
        "rule_version": rule_version,
        "disclaimer": Config.DISCLAIMER,
        "emergency": emergency,
        "cold_heat": cold_heat,
        "contraindications": contra,
        "relative_warnings": relative_warnings,
        "population_adjustments": population_adjustments,
        "six_channel_hypotheses": hypotheses,
        "retrieved_clauses": retrieved_clauses,
        "candidate_formulas": candidate_formulas,
        "verification_inquiry": verification,
        "info_completeness": completeness,
        "pulse_fallback": pulse_fallback,
        "patient_profile": profile,
        "keywords": keywords,
        "negations": negations,
        "normalized_query": normalized_query,
        "data_stats": {
            "clauses_count": len(data.get("clauses", [])),
            "formulas_count": len(data.get("formulas", [])),
            "rules_count": len(data.get("rules", [])),
        },
        "chapter_context": chapter_context or [],
    }

    # 必填项缺失时的额外字段
    if required_fields_check is not None:
        output["required_fields_check"] = required_fields_check
        output["message"] = f"必填信息缺失：{', '.join(r['field_display'] for r in required_fields_check['missing'])}。请补充后再进行辨证分析。"

    return output
