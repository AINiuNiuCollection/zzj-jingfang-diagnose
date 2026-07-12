# coding: utf-8
"""Restore original 83 formulas, fix is_in_kb, regenerate all 190 missing"""
import json, re, os, pathlib

script_dir = pathlib.Path(__file__).parent.resolve()

# ===== 1. Read current (209) formulas =====
with open(os.path.join(script_dir, 'assets', 'formulas.json'), 'r', encoding='utf-8') as f:
    all_formulas = json.load(f)

# Read newly_added_formulas.txt to know which ones were added (126)
with open(os.path.join(script_dir, 'assets', 'newly_added_formulas.txt'), 'r', encoding='utf-8') as f:
    added_text = f.read()

added_names = set()
for line in added_text.split('\n'):
    m = re.match(r'^\s*\d+\.\s+(.*?)\s+\[' , line)
    if m:
        added_names.add(m.group(1).strip())

print(f'Added names from file: {len(added_names)}')

# ===== 2. Restore original 83 =====
original = [fm for fm in all_formulas if fm['name'] not in added_names]
print(f'Original formulas: {len(original)}')

# Verify we got 83
assert len(original) == 83, f'Expected 83 original, got {len(original)}'

# Save restored original
with open(os.path.join(script_dir, 'assets', 'formulas.json'), 'w', encoding='utf-8') as f:
    json.dump(original, f, ensure_ascii=False, indent=2)
print('Restored original 83 formulas to formulas.json')

# ===== 3. Now regenerate with fixed is_in_kb =====

# Parse reference doc
with open('D:/SoftWareInstall/opencode/ChineseMedicine/docs/275方剂完整整理.md', 'r', encoding='utf-8') as f:
    ref_text = f.read()

sections = re.split(r'\n(?=## \d+\.\s+)', ref_text)
sections = [s for s in sections if re.match(r'## \d+\.\s+', s.strip())]

def parse_section(section):
    lines = section.strip().split('\n')
    name_match = re.match(r'## \d+\.\s+(.*)', lines[0])
    if not name_match:
        return None
    name = name_match.group(1).strip()
    result = {'name': name}
    current_section = None
    section_content = {}
    for line in lines[1:]:
        m = re.match(r'###\s+(.*)', line.strip())
        if m:
            current_section = m.group(1).strip()
            section_content[current_section] = []
        elif current_section:
            section_content[current_section].append(line)
    
    # Original text
    herbs_raw = section_content.get('原文', [])
    if herbs_raw:
        result['original_text'] = ''.join(herbs_raw).strip()
    
    # Dosage lines
    dosage_lines = section_content.get('折算现代计量', [])
    result['dosage_lines'] = [l.strip() for l in dosage_lines if l.strip()]
    
    # Parse composition
    composition = []
    for line in result['dosage_lines']:
        m = re.match(r'^(.+?)\.?\s*(?:[（(](.*?)[）)])?\s*$', line)
        if m:
            herb_name = m.group(1).strip()
            # Extract dose by looking at numeric patterns
            # Format: "药材名 剂量" or "药材名等分"
            dose_pattern = r'(.+?)([一两三四五六七八九十半分钱克升合等\d.]+(?:\s*[两钱分克升合])?)\s*$'
            dose_match = re.match(dose_pattern, herb_name)
            if dose_match:
                herb = dose_match.group(1).strip()
                dose = dose_match.group(2).strip()
            else:
                herb = herb_name
                dose = ''
            prep = m.group(2) if m.group(2) else ''
            if herb:
                composition.append({'herb': herb, 'dose': dose, 'desc': prep})
    result['composition'] = composition
    
    # Usage
    usage_lines = section_content.get('用法', [])
    result['usage'] = ''.join(usage_lines).strip() if usage_lines else ''
    
    # Notes
    note_lines = section_content.get('注', [])
    result['notes'] = ''.join(note_lines).strip() if note_lines else ''
    
    # Related clauses
    clause_lines = section_content.get('相关条文', [])
    result['related_clauses'] = ''.join(clause_lines).strip() if clause_lines else ''
    
    return result

all_parsed = []
for section in sections:
    p = parse_section(section)
    if p:
        all_parsed.append(p)

print(f'Parsed {len(all_parsed)} formula sections')

# ===== 4. Build matching =====
def norm(name):
    n = name.replace('乾','干').replace('薑','姜').replace('朮','术')
    n = n.replace('耆','芪').replace('䗪','蛰').replace('蒌','蒌')
    n = n.replace('當歸','当归').replace('芎藭','川芎').replace('芎䓖','川芎')
    n = n.replace('蘗','柏').replace('黃蘗','黄柏').replace('消石','硝石')
    n = n.replace('芒消','芒硝').replace('黄岑','黄芩')
    return re.sub(r'[（(][^）)]*[）)]$', '', n).strip()

def core(name):
    return re.sub(r'[汤汤散丸膏酒方]$', '', norm(name))

existing_cores = set()
existing_relations = {}

for fm in original:
    c = core(fm['name'])
    existing_cores.add(c)
    existing_relations[c] = {'name': fm['name'], 'id': fm['id']}

# Equivalence groups
EQUIV_MAP = {}
for pair in [
    ('苓桂术甘汤', '茯苓桂枝白术甘草汤'),
    ('桂枝去桂加茯苓白术汤', '去桂加白术汤'),
    ('桂枝去桂加茯苓白汤', '去桂加白汤'),
    ('崔氏八味丸', '肾气丸'),
    ('侯氏黑散', '黑散'),
    ('风引汤', '紫石寒食散'),
    ('当归生姜羊肉汤', '当归生薑羊肉汤'),
    ('厚朴生姜半夏甘草人参汤', '厚朴生薑半夏甘草人参汤'),
    ('桂枝加芍药生姜人参新加汤', '桂枝加芍药生姜各一两人参三两新加汤'),
    ('桂枝加芍药生薑人参新加汤', '桂枝加芍药生薑各一两人参三两新加汤'),
    ('小半夏加茯苓汤', '小半夏茯苓汤'),
    ('苓甘五味姜辛汤', '桂苓五味甘草汤去桂加干姜细辛'),
    ('甘姜苓术汤', '甘草干姜茯苓白术汤'),
    ('肾着汤', '甘草干姜茯苓白术汤'),
    ('大乌头煎', '乌头煎'),
    ('乌头桂枝汤', '抵当乌头桂枝汤'),
    ('柴胡桂枝干姜汤', '柴胡桂姜汤'),
    ('千金苇茎汤', '苇茎汤'),
    ('猪膏发煎', '膏发煎'),
    ('赤石脂禹余粮汤', '赤石脂禹馀粮汤'),
    ('诃黎勒散', '诃黎勒丸'),
]:
    c1, c2 = core(pair[0]), core(pair[1])
    # Map both to the target (second)
    EQUIV_MAP[c1] = c2

def is_in_kb(name):
    """Check if formula is already in KB - exact matching only"""
    c = core(name)
    if c in existing_cores:
        return True
    if c in EQUIV_MAP and EQUIV_MAP[c] in existing_cores:
        return True
    return False

# ===== 5. Count what would be generated =====
to_gen = [p for p in all_parsed if not is_in_kb(p['name'])]
print(f'Formulas to generate (should be ~190): {len(to_gen)}')

# Show which would be skipped
skipped_names = sorted([p['name'] for p in all_parsed if is_in_kb(p['name'])])
print(f'\nFormulas already in KB: {len(skipped_names)}')
for n in skipped_names:
    c = core(n)
    matched_by = ''
    if c in existing_cores:
        matched_by = f'  -> exact match: [{c}]'
    elif c in EQUIV_MAP and EQUIV_MAP[c] in existing_cores:
        matched_by = f'  -> equiv match: [{EQUIV_MAP[c]}]'
    print(f'  {n}{matched_by}')

# Show what would be added
print(f'\nFormulas to ADD: {len(to_gen)}')
missing_from_190_check = []
for i, p in enumerate(to_gen[:20]):
    print(f'  {i+1}. {p["name"]}')
