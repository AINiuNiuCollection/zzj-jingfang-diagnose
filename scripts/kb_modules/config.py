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

    # ===== 特异性加权系数（v2） =====
    SPEC_WEIGHT_1CHAR = 0.3       # 单字指示词（"痞""渴""呕"）
    SPEC_WEIGHT_2CHAR_GENERIC = 0.6   # 2字通用词（"汗出""发热""下利"）
    SPEC_WEIGHT_2CHAR_SPECIFIC = 0.8  # 2字特异性词（"恶寒""往来"）
    SPEC_WEIGHT_3CHAR = 1.0       # 3字指示词（"心下痞""不得眠"）
    SPEC_WEIGHT_4CHAR_PLUS = 1.2  # 4字+指示词（"往来寒热""干噫食臭"）

    # ===== 复合指示词拆分匹配系数 =====
    COMPOUND_FULL_RATIO = 1.0     # 整体连续命中
    COMPOUND_SPLIT_ALL_RATIO = 0.8  # 拆分后全部命中（非连续）
    COMPOUND_SPLIT_PARTIAL_FACTOR = 0.5  # 拆分后部分命中（按命中比例×此系数）
