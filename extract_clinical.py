# coding: utf-8
"""Parse 伤寒论 and 金匮要略, extract clinical data for ALL formulas"""
import json, re, pathlib

script_dir = pathlib.Path(__file__).parent.resolve()

# ===== 1. Parse 伤寒论 text =====
def parse_shanghan(text):
    clauses = []
    lines = text.split('\n')
    chapter = ''
    num = None
    txt = []
    formula = None
    comp = []
    method = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        m = re.match(r'<篇名>(.+)', line)
        if m:
            chapter = m.group(1)
            continue
        
        m = re.match(r'(\d+)．(.+)', line)
        if m:
            if num is not None:
                clauses.append({'chap': chapter, 'num': num, 'txt': '\n'.join(txt),
                                'formula': formula, 'comp': '\n'.join(comp), 'method': '\n'.join(method)})
            num = int(m.group(1))
            rest = m.group(2)
            txt = [rest]
            formula = None
            comp = []
            method = []
            
            fm = re.search(r'([\u4e00-\u9fff]{1,10}(?:汤|散|丸|膏|酒)?)主之', rest)
            if fm:
                formula = fm.group(1)
            continue
        
        if num is None:
            continue
        
        txt.append(line)
        
        if '主之' in line:
            fm = re.search(r'([\u4e00-\u9fff]{1,10}(?:汤|散|丸|膏|酒)?)主之', line)
            if fm:
                formula = fm.group(1)
        
        if line.startswith('上') and '味' in line:
            method.append(line)
        elif line.startswith('右') and '味' in line:
            method.append(line)
        elif method:
            method.append(line)
        elif formula and re.search(r'[\u4e00-\u9fff]（', line):
            comp.append(line)
    
    if num is not None:
        clauses.append({'chap': chapter, 'num': num, 'txt': '\n'.join(txt),
                        'formula': formula, 'comp': '\n'.join(comp), 'method': '\n'.join(method)})
    return clauses

# ===== 2. Parse 金匮要略 =====
def parse_jinkui(text):
    clauses = []
    lines = text.split('\n')
    chapter = ''
    num = None
    txt = []
    formula = None
    comp = []
    method = []
    in_f = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        m = re.match(r'<篇名>(.+)', line)
        if m:
            chapter = m.group(1)
            continue
        
        m = re.match(r'(\d+)．(.+)', line)
        if m:
            if num is not None:
                clauses.append({'chap': chapter, 'num': num, 'txt': '\n'.join(txt),
                                'formula': formula, 'comp': '\n'.join(comp), 'method': '\n'.join(method)})
            num = int(m.group(1))
            rest = m.group(2)
            txt = [rest]
            formula = None
            comp = []
            method = []
            in_f = False
            
            fm = re.search(r'([\u4e00-\u9fff]{1,10}(?:汤|散|丸|膏|酒)?)主之', rest)
            if fm:
                formula = fm.group(1)
                in_f = True
            continue
        
        if num is None:
            continue
        
        txt.append(line)
        
        if '主之' in line:
            fm = re.search(r'([\u4e00-\u9fff]{1,10}(?:汤|散|丸|膏|酒)?)主之', line)
            if fm:
                formula = fm.group(1)
                in_f = True
        
        if in_f:
            if line.startswith('上') and '味' in line:
                method.append(line)
            elif line.startswith('右') and '味' in line:
                method.append(line)
            elif method:
                method.append(line)
            elif re.search(r'[\u4e00-\u9fff]（', line):
                comp.append(line)
        else:
            comp_line = re.search(r'[\u4e00-\u9fff]（', line)
            if comp_line:
                comp.append(line)
    
    if num is not None:
        clauses.append({'chap': chapter, 'num': num, 'txt': '\n'.join(txt),
                        'formula': formula, 'comp': '\n'.join(comp), 'method': '\n'.join(method)})
    return clauses

# ===== 3. Extract clinical info =====
def extract_indicators(text):
    """Extract symptoms from clause text before 主之"""
    m = re.match(r'(.+?)主之', text)
    if not m:
        return []
    s = m.group(1)
    found = set()
    result = []
    pats = [
        r'(发热|不发热|身热|潮热|微热|烦热|无热|恶寒|恶风|恶热|微恶寒|微恶风|不恶寒|不恶风)',
        r'(汗出|自汗|盗汗|无汗|大汗|微汗|汗漏|汗自出|不汗|不得汗)',
        r'(头痛|头项强|项强|头眩|头晕|头重|头不痛)',
        r'(身痛|身重|身黄|身肿|身痒|身不痛)',
        r'(口不渴|口渴|口苦|口燥|口干|口烂)',
        r'(呕吐|干呕|欲呕|呕逆|吐利|吐逆|吐|呕|不呕|欲吐)',
        r'(下利|自利|大便硬|大便难|不大便|便血|便脓血|溏|不结胸|大便)',
        r'(小便不利|小便难|小便自利|小便数|小便少|小便|小便利)',
        r'(胸满|胸痞|胸痛|胁满|胁痛|心下满|心下痞|腹满|腹胀|腹痛|少腹满|少腹硬|心下)',
        r'(烦躁|躁烦|心烦|心乱|不得卧|不得眠|卧起不安)',
        r'(咳嗽|喘|短气|上气|不得息|咳|不喘)',
        r'(不能食|能食|欲食|饥|不欲饮食|不饮食|饮食)',
        r'(悸|惊|狂|谵语|独语|如见鬼状|惊狂)',
        r'(厥|四逆|手足厥|手足寒|手足冷|手足温)',
        r'(痉|拘急|挛急|脚挛急|转筋|四肢微急)',
        r'(渴|不渴)',
        r'(鼻鸣|鼻塞|鼻干)',
        r'(目眩|目赤|目黄)',
        r'(胁下|胸胁)',
    ]
    for pat in pats:
        for match in re.finditer(pat, s):
            val = match.group(1)
            if val not in found:
                result.append(val)
                found.add(val)
    return result[:8]

def extract_pulse(text):
    pulses = []
    for m in re.finditer(r'脉[浮沉数迟紧缓滑涩虚实微细弦洪大弱小]*(?:而[浮沉数迟紧缓滑涩虚实微细弦洪大弱小]+)?', text):
        val = m.group(0).rstrip('者')
        if val not in pulses:
            pulses.append(val)
    return pulses[:4]

def extract_six(chapter):
    for ch in ['太阳','阳明','少阳','太阴','少阴','厥阴']:
        if ch in chapter:
            return ch
    if '霍乱' in chapter:
        return '霍乱'
    if '阴阳易' in chapter:
        return '阴阳易'
    return ''

def extract_pathogenesis(text, chapter):
    hints = []
    if '中风' in text: hints.append('风邪外袭')
    if '伤寒' in text: hints.append('风寒外束')
    if '少阳' in text: hints.append('邪犯少阳')
    if '阳明' in text: hints.append('阳明热盛')
    if '太阴' in text: hints.append('太阴虚寒')
    if '少阴' in text and '寒' in text: hints.append('少阴寒化')
    if '少阴' in text and '热' in text: hints.append('少阴热化')
    if '瘀' in text or '蓄血' in text: hints.append('瘀血内停')
    if '虚' in text: hints.append('正气亏虚')
    if '水气' in text or '水' in text: hints.append('水饮内停')
    if '痰' in text: hints.append('痰浊内蕴')
    if '热' in text and '利' in text: hints.append('热利下重')
    if '寒' in text and not '热' in text: hints.append('寒邪内盛')
    if '痞' in text: hints.append('痞结不通')
    if '结胸' in text: hints.append('结胸')
    return '；'.join(hints)

def parse_comp(text):
    herbs = []
    for part in re.split(r'\s+', text.strip()):
        if not part:
            continue
        m = re.match(r'^(.+?)（(.*?)）$', part)
        if m:
            name = m.group(1)
            inside = m.group(2)
            dm = re.search(r'([一两三四五六七八九十半分钱铢个枚升合斗尺寸]+(?:\s*[两钱分铢个枚升合斗尺])?)$', inside)
            if dm:
                dose = dm.group(1)
                prep = inside[:dm.start()].rstrip('，,').strip()
            else:
                dose = ''
                prep = inside
            herbs.append({'herb': name, 'dose': dose, 'desc': prep})
        else:
            herbs.append({'herb': part, 'dose': '', 'desc': ''})
    return herbs

def parse_method(text):
    result = {'decoction_method': '', 'dosage_form': '', 'aftercare': '', 'stop_criteria': ''}
    dm = re.search(r'(上[一二三四五六七八九十\d]+味.*?以水[^。]*。?)', text)
    if dm:
        result['decoction_method'] = dm.group(1)
    df = re.search(r'(温服[^。]+|服[一二三四五六七八九十\d]+[合升]。?)', text)
    if df:
        result['dosage_form'] = df.group(1)
    ac = re.search(r'(啜热稀粥[^。]+|温覆[^。]+|覆取微似汗[^。]+|饮热粥[^。]+)', text)
    if ac:
        result['aftercare'] = ac.group(1)
    sc = re.search(r'(若一服[^。]+?停后服[^。]*|若服[^。]+?不必尽剂[^。]*)', text)
    if sc:
        result['stop_criteria'] = sc.group(1)
    return result

# ===== 4. Build index =====
print('Reading texts...')
with open(script_dir / 'assets' / 'book' / '457-伤寒论.txt', 'rb') as f:
    sh = f.read().decode('gbk')
with open(script_dir / 'assets' / 'book' / '499-金匮要略方论.txt', 'rb') as f:
    jk = f.read().decode('gbk')

print('Parsing clauses...')
sh_clauses = parse_shanghan(sh)
jk_clauses = parse_jinkui(jk)
print(f'伤寒论: {len(sh_clauses)} clauses, 金匮要略: {len(jk_clauses)} clauses')

# Build formula -> clause index
idx = {}
for c in sh_clauses + jk_clauses:
    if c['formula']:
        key = c['formula'].replace('干','干')  # keep as is
        # Normalize key
        key = key.replace('干','干').replace('乾','干').replace('薑','姜').replace('薑','姜')
        key = key.replace('朮','术').replace('耆','芪').replace('䗪','蛰')
        key = key.replace('當歸','当归').replace('栝蒌','瓜蒌').replace('蒌','蒌')
        if key not in idx:
            idx[key] = []
        idx[key].append(c)

print(f'Formula index: {len(idx)} unique formulas')

# ===== 5. Process formulas =====
p = script_dir / 'assets' / 'formulas.json'
formulas = json.loads(p.read_text(encoding='utf-8'))

# Count before
before = sum(1 for fm in formulas if fm.get('core_indicators') and len(fm['core_indicators']) > 0)

updated = 0
found = 0
not_found = []

# Equiv groups
equiv = {
    '去桂加白术': '桂枝去桂加茯苓白术',
    '去桂加白': '桂枝去桂加茯苓白术',
    '桂枝去桂加茯苓白': '桂枝去桂加茯苓白术',
    '小半夏茯苓': '小半夏加茯苓',
    '柴胡桂姜': '柴胡桂枝干姜',
    '甘草干姜茯苓白术': '甘姜苓术',
    '桂枝加芍药生姜人参新加': '桂枝加芍药生姜各一两人参三两新加',
}

for fm in formulas:
    if fm.get('core_indicators') and len(fm['core_indicators']) > 0:
        continue
    
    name = fm['name']
    # Normalize for matching
    n = name.replace('乾','干').replace('薑','姜').replace('朮','术')
    n = n.replace('耆','芪').replace('䗪','蛰').replace('當歸','当归')
    n = n.replace('栝蒌','瓜蒌')
    base = re.sub(r'[汤汤散丸膏酒方]$', '', n)
    
    clauses = []
    if base in idx:
        clauses = idx[base]
    elif n in idx:
        clauses = idx[n]
    else:
        eq = equiv.get(base) or equiv.get(n)
        if eq and eq in idx:
            clauses = idx[eq]
    
    if not clauses:
        # Try without suffix
        for k, v in idx.items():
            kb = re.sub(r'[汤汤散丸膏酒方]$', '', k)
            if base == kb:
                clauses = v
                break
    
    if not clauses:
        not_found.append(name)
        continue
    
    found += 1
    c = clauses[0]
    txt = c['txt']
    src = '伤寒论' if c in sh_clauses else '金匮要略'
    
    ind = extract_indicators(txt)
    if ind:
        fm['core_indicators'] = ind
        if not fm.get('main_indications'):
            fm['main_indications'] = ind[:6]
    
    pulse = extract_pulse(txt)
    if pulse:
        fm['typical_pulse'] = pulse
    
    ch = extract_six(c['chap'])
    if ch:
        fm['six_channel'] = ch
    
    patho = extract_pathogenesis(txt, c['chap'])
    if patho:
        fm['core_pathogenesis'] = patho
    
    comp = parse_comp(c['comp'])
    if comp:
        fm['composition'] = comp
    
    meth = parse_method(c['method'])
    for k, v in meth.items():
        if v and not fm.get(k):
            fm[k] = v
    
    if src == '伤寒论':
        fm['source_clause'] = f'SHL-{c["num"]:03d}'
    else:
        fm['source_clause'] = f'JKYL-{c["num"]:03d}'
    
    updated += 1

after = sum(1 for fm in formulas if fm.get('core_indicators') and len(fm['core_indicators']) > 0)

print(f'\nUpdated formulas: {updated}')
print(f'With clinical data: {after}/{len(formulas)} (was {before})')
print(f'Not found in texts: {len(not_found)}')

# Save
p.write_text(json.dumps(formulas, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Saved formulas.json ({len(formulas)} entries)')

# Save not-found list
with open(script_dir / 'assets' / 'unmatched_formulas.txt', 'w', encoding='utf-8') as f:
    f.write(f'Formulas not found in original texts: {len(not_found)}\n\n')
    for n in sorted(not_found):
        f.write(f'{n}\n')
print(f'Not-found list saved to unmatched_formulas.txt')
