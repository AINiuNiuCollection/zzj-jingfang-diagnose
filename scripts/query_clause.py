#!/usr/bin/env python3
"""
条文精准查询脚本 - 按方剂名/症状/编号/关键词查询原典条文

用法：
  python query_clause.py --keyword "桂枝汤"           # 按关键词查询
  python query_clause.py --formula "桂枝汤"            # 按方剂名查询
  python query_clause.py --clause-id "SHL-012"         # 按条文编号查询
  python query_clause.py --symptom "往来寒热"           # 按症状查询
  python query_clause.py --chapter "辨太阳病"           # 按篇章查询

输出：JSON 格式的条文列表
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"


def load_clauses():
    path = ASSETS_DIR / "clauses.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_formulas():
    path = ASSETS_DIR / "formulas.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def search_by_keyword(clauses, keyword, limit=20):
    """关键词全文搜索"""
    results = []
    for cl in clauses:
        text = cl.get("original_text", "") + " ".join(cl.get("main_symptoms", [])) + " ".join(cl.get("pulse", []))
        if keyword in text:
            results.append(cl)
        if len(results) >= limit:
            break
    return results


def search_by_formula(clauses, formulas, formula_name, limit=20):
    """按方剂名查询相关条文"""
    # 先找到方剂对应的条文编号
    source_clauses = []
    for f in formulas:
        if formula_name in f.get("name", ""):
            source_clauses.append(f.get("source_clause", ""))

    results = []
    # 按方剂名在条文中搜索
    for cl in clauses:
        text = cl.get("original_text", "")
        if formula_name in text:
            results.append(cl)
        # 也匹配方剂ID
        for sc in source_clauses:
            if sc and sc in cl.get("id", ""):
                results.append(cl)
                break
        if len(results) >= limit:
            break
    return results


def search_by_clause_id(clauses, clause_id):
    """按条文编号精确查询"""
    for cl in clauses:
        if cl.get("id") == clause_id:
            return cl
    return None


def search_by_symptom(clauses, symptom, limit=20):
    """按症状查询"""
    results = []
    for cl in clauses:
        main_symptoms = cl.get("main_symptoms", [])
        secondary = cl.get("secondary_symptoms", [])
        original_text = cl.get("original_text", "")
        if symptom in main_symptoms or symptom in secondary or symptom in original_text:
            results.append(cl)
        if len(results) >= limit:
            break
    return results


def search_by_chapter(clauses, chapter_keyword, limit=50):
    """按篇章查询"""
    results = []
    for cl in clauses:
        if chapter_keyword in cl.get("chapter", ""):
            results.append(cl)
        if len(results) >= limit:
            break
    return results


def main():
    parser = argparse.ArgumentParser(description="条文精准查询")
    parser.add_argument("--keyword", default="", help="关键词全文搜索")
    parser.add_argument("--formula", default="", help="按方剂名查询")
    parser.add_argument("--clause-id", default="", help="按条文编号精确查询")
    parser.add_argument("--symptom", default="", help="按症状查询")
    parser.add_argument("--chapter", default="", help="按篇章查询")
    parser.add_argument("--limit", type=int, default=20, help="返回数量上限")
    args = parser.parse_args()

    clauses = load_clauses()
    formulas = load_formulas()

    results = []
    if args.clause_id:
        cl = search_by_clause_id(clauses, args.clause_id)
        results = [cl] if cl else []
    elif args.formula:
        results = search_by_formula(clauses, formulas, args.formula, args.limit)
    elif args.symptom:
        results = search_by_symptom(clauses, args.symptom, args.limit)
    elif args.chapter:
        results = search_by_chapter(clauses, args.chapter, args.limit)
    elif args.keyword:
        results = search_by_keyword(clauses, args.keyword, args.limit)

    output = {
        "query": {
            "keyword": args.keyword,
            "formula": args.formula,
            "clause_id": args.clause_id,
            "symptom": args.symptom,
            "chapter": args.chapter,
        },
        "total": len(results),
        "clauses": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
