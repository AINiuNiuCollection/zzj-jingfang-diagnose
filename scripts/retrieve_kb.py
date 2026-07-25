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
import sys

# Windows 控制台 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 确保依赖可用
try:
    import jieba
    jieba.setLogLevel(20)
except ImportError:
    print(json.dumps({"error": "缺少依赖，请运行: pip install rank_bm25 jieba"}, ensure_ascii=False))
    sys.exit(1)

from kb_modules import JingFangKB


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

    kb = JingFangKB()
    output = kb.search_from_args(args)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
