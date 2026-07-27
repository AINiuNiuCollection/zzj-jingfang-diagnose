"""
config - 可调算法阈值常量

领域数据（脉象映射、语义映射、脉证组合、追问映射、寒热关键词、矛盾组合等）
已迁出至 assets/ 目录下的 JSON 配置文件，代码只保留算法逻辑阈值。
"""


class Config:
    """可调算法阈值参数（领域数据已迁出至 JSON 配置文件）"""

    # ===== 版本 =====
    RULE_VERSION = "2.1.0"
    DISCLAIMER = "本结果仅为经方学术参考，不构成诊疗建议，具体处方请由执业医师辨证开具。"

    # ===== 方剂排序权重 =====
    CORE_INDICATOR_WEIGHT = 10.0
    EXCLUSION_PENALTY = 20.0
    MAIN_INDICATION_WEIGHT = 3.0
    PULSE_WEIGHT = 3.0
    PATHOGENESIS_WEIGHT = 1.0
    RELATIVE_CONTRA_PENALTY = 0.7
    CLASSICAL_PRECEDENT_PENALTY = 0.7
    NO_PRECEDENT_PENALTY = 0.5

    # ===== 阈值 =====
    BM25_TOP_K = 10
    FORMULA_TOP_K = 5
    EMERGENCY_DEFAULT_THRESHOLD = 2

    # ===== 六经置信度计算参数 =====
    SHARED_EVIDENCE_DISCOUNT = 0.5    # 共享证据折扣系数
    MIN_EVIDENCE_THRESHOLD = 3.0      # 最低调整分阈值（低于此值置信度封顶）
    MULTI_SOURCE_BONUS = 0.08         # 多源收敛加分（每多一层+0.08，最多+0.16）
    EVIDENCE_FLOOR_CONFIDENCE = 0.45  # 证据不足时置信度上限

    # ===== 矛盾组合基础加分 =====
    CONTRADICTORY_COMBO_BONUS = 3.0
