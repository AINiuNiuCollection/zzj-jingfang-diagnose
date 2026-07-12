# coding: utf-8
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')

p = pathlib.Path(__file__).parent.resolve() / 'assets' / 'formulas.json'
formulas = json.loads(p.read_text(encoding='utf-8'))

# Manual fixes for remaining 15 unmatched formulas
# All data verified from original texts (see mismatches_report.md)

manual_fixes = {
    '三物备急丸': {
        'core_indicators': ['心腹诸卒暴百病', '心腹胀满', '卒痛如锥刺', '气急口噤', '停尸卒死'],
        'core_pathogenesis': '寒实内结，卒暴诸病',
        'source_clause': 'JKYL-023',
    },
    '厚朴三物汤': {
        'core_indicators': ['腹满', '腹痛', '大便不通'],
        'core_pathogenesis': '实热气滞，腹满痛',
        'source_clause': 'JKYL-010',
    },
    '厚朴大黄汤': {
        'core_indicators': ['胸满', '腹满', '支饮'],
        'core_pathogenesis': '饮热互结，胸腹满',
        'source_clause': 'JKYL-012',
    },
    '厚朴麻黄汤': {
        'core_indicators': ['咳', '喘', '胸满', '上气'],
        'core_pathogenesis': '寒饮郁肺，咳逆上气',
        'source_clause': 'JKYL-007',
    },
    '去桂加白汤': {
        'core_indicators': ['头项强痛', '翕翕发热', '无汗', '心下满微痛', '小便不利'],
        'core_pathogenesis': '水饮内停，太阳经气不利',
        'source_clause': 'SHL-028',
    },
    '大黄䗪虫丸': {
        'core_indicators': ['虚劳羸瘦', '腹满不能食', '肌肤甲错', '两目黯黑'],
        'core_pathogenesis': '虚劳干血，瘀血内停',
        'source_clause': 'JKYL-018',
    },
    '柴胡饮子': {
        'core_indicators': ['五脏虚热', '四体壅'],
        'core_pathogenesis': '五脏虚热',
        'source_clause': 'JKYL-023',
    },
    '栀子厚朴汤': {
        'core_indicators': ['心烦', '腹满', '卧起不安'],
        'core_pathogenesis': '热扰胸膈，气滞腹满',
        'source_clause': 'SHL-079',
    },
    '桂枝二麻黄一汤': {
        'core_indicators': ['大汗出', '脉洪大', '形似疟', '日再发'],
        'core_pathogenesis': '汗后邪郁，营卫不和',
        'source_clause': 'SHL-025',
    },
    '桂枝加黄耆汤': {
        'core_indicators': ['黄汗', '发热', '两胫自冷', '身肿', '汗出沾衣'],
        'core_pathogenesis': '黄汗，表虚湿郁',
        'source_clause': 'JKYL-014',
    },
    '橘皮汤': {
        'core_indicators': ['干呕', '哕', '手足厥'],
        'core_pathogenesis': '胃寒气逆',
        'source_clause': 'JKYL-017',
    },
    '橘皮竹茹汤': {
        'core_indicators': ['哕逆', '虚热'],
        'core_pathogenesis': '胃虚有热，气逆作哕',
        'source_clause': 'JKYL-017',
    },
    '烧褌散': {
        'core_indicators': ['阴阳易', '身重', '少气', '少腹里急', '热上冲胸', '头重不欲举'],
        'core_pathogenesis': '阴阳易病，精气亏损',
        'source_clause': 'SHL-392',
    },
    '耆芍桂酒汤': {
        'core_indicators': ['黄汗', '身肿', '发热汗出', '汗沾衣'],
        'core_pathogenesis': '黄汗，湿热交蒸',
        'source_clause': 'JKYL-014',
    },
    '诃黎勒丸': {
        'core_indicators': ['长服', '气滞'],
        'core_pathogenesis': '气滞不和',
        'source_clause': 'JKYL-023',
    },
}

for fm in formulas:
    name = fm['name']
    if name in manual_fixes:
        fm.update(manual_fixes[name])

# Stats
with_data = sum(1 for fm in formulas if fm.get('core_indicators') and len(fm['core_indicators']) > 0)
still_missing = [fm['name'] for fm in formulas if not fm.get('core_indicators') or len(fm['core_indicators']) == 0]
print(f'With clinical data: {with_data}/{len(formulas)}')
print(f'Still missing: {len(still_missing)}')

# Save
p.write_text(json.dumps(formulas, ensure_ascii=False, indent=2), encoding='utf-8')
print('Saved formulas.json')
