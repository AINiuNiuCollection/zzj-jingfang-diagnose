# coding: utf-8
"""Second-pass: direct text search for unmatched formulas"""
import json, re, pathlib

script_dir = pathlib.Path(__file__).parent.resolve()

# Read texts
with open(script_dir / 'assets' / 'book' / '457-伤寒论.txt', 'rb') as f:
    sh = f.read().decode('gbk')
with open(script_dir / 'assets' / 'book' / '499-金匮要略方论.txt', 'rb') as f:
    jk = f.read().decode('gbk')

# Load formulas
p = script_dir / 'assets' / 'formulas.json'
formulas = json.loads(p.read_text(encoding='utf-8'))

# ===== Name alias mapping =====
ALIASES = {
    '去桂加白汤': '桂枝去桂加茯苓白术汤',
    '朮附汤': '桂枝附子去桂加白术汤',
    '杏子汤': '麻黄杏子甘草石膏汤',
    '甘草汤': '甘草泻心汤',
    '生姜甘草汤': '生姜甘草汤',
    '瓜蒂散': '瓜蒂散',
    '旋覆花汤': '旋覆花汤',
    '小半夏茯苓汤': '小半夏加茯苓汤',
    '柴胡桂薑汤': '柴胡桂枝干姜汤',
    '柴胡去半夏加栝蒌汤': '柴胡去半夏加栝蒌汤',
    '柴胡饮子': '柴胡饮子',
    '桔梗白散': '桔梗白散',
    '当归散': '当归散',
    '排脓散': '排脓散',
    '薯蓣丸': '薯蓣丸',
    '鳖甲煎丸': '鳖甲煎丸',
    '防己地黄汤': '防己地黄汤',
    '阳旦汤': '阳旦汤',
    '三物备急丸': '三物备急丸',
    '三物小白散': '三物小白散',
    '三黄汤': '千金三黄汤',
    '下瘀血汤': '下瘀血汤',
    '乌头赤石脂丸': '赤石脂丸',
    '赤石脂丸': '乌头赤石脂丸',
    '九痛丸': '九痛丸',
    '人参汤': '人参汤',
    '侯氏黑散': '侯氏黑散',
    '厚朴三物汤': '厚朴三物汤',
    '厚朴大黄汤': '厚朴大黄汤',
    '厚朴麻黄汤': '厚朴麻黄汤',
    '射干麻黄汤': '射干麻黄汤',
    '崔氏八味丸': '肾气丸',
    '木防己汤': '木防己汤',
    '木防己汤去石膏加茯苓芒硝汤': '木防己去石膏加茯苓芒硝汤',
    '柴胡加芒硝汤': '柴胡加芒硝汤',
    '桂枝二越婢一汤': '桂枝二越婢一汤',
    '桂枝二麻黄一汤': '桂枝二麻黄一汤',
    '桂枝加大黄汤': '桂枝加大黄汤',
    '桂枝加芍药生薑人参新加汤': '桂枝加芍药生姜各一两人参三两新加汤',
    '桂枝加芍药生薑各一两人参三两新加汤': '桂枝加芍药生姜各一两人参三两新加汤',
    '桂枝加黄耆汤': '桂枝加黄芪汤',
    '桂枝加龙骨牡蛎汤': '桂枝加龙骨牡蛎汤',
    '桂枝去芍药加皂荚汤': '桂枝去芍药加皂荚汤',
    '桂枝去芍药加麻辛附子汤': '桂枝去芍药加麻黄细辛附子汤',
    '桂枝附子汤': '桂枝附子汤',
    '桂枝去桂加茯苓白朮汤': '桂枝去桂加茯苓白术汤',
    '桂枝去桂加茯苓白汤': '桂枝去桂加茯苓白术汤',
    '桂苓五味甘草汤去桂加乾薑、细辛': '苓甘五味姜辛汤',
    '甘草干姜茯苓白术汤': '甘姜苓术汤',
    '橘枳薑汤': '橘枳姜汤',
    '橘皮汤': '橘皮汤',
    '橘皮竹茹汤': '橘皮竹茹汤',
    '滑石白鱼散': '滑石白鱼散',
    '烧褌散': '烧裈散',
    '牡蛎汤': '牡蛎汤',
    '狼牙汤': '狼牙汤',
    '猪胆汁方': '猪胆汁方',
    '猪膏髮煎': '猪膏发煎',
    '膏髮煎': '猪膏发煎',
    '獭肝散': '獭肝散',
    '白头翁加甘草阿胶汤': '白头翁加甘草阿胶汤',
    '白朮附子汤': '白术附子汤',
    '百合洗方': '百合洗方',
    '百合鸡子汤': '百合鸡子汤',
    '禹馀粮丸': '禹余粮丸',
    '紫石寒食散': '紫石寒食散',
    '续命汤': '古今录验续命汤',
    '耆芍桂酒汤': '黄芪芍桂苦酒汤',
    '胶艾汤': '芎归胶艾汤',
    '苇茎汤': '千金苇茎汤',
    '茯苓戎盐汤': '茯苓戎盐汤',
    '茯苓桂枝五味甘草汤': '桂苓五味甘草汤',
    '茯苓桂枝白甘草汤': '茯苓桂枝白术甘草汤',
    '葵子茯苓散': '葵子茯苓散',
    '薏苡附子败酱散': '薏苡附子败酱散',
    '蜜煎导方': '蜜煎导',
    '赤石脂禹馀粮汤': '赤石脂禹余粮汤',
    '赤豆当归散': '赤小豆当归散',
    '还魂汤': '还魂汤',
    '风引汤': '风引汤',
    '麻黄加朮汤': '麻黄加术汤',
    '麻黄杏仁甘草石膏汤': '麻黄杏子甘草石膏汤',
    '麻黄杏仁薏苡甘草汤': '麻黄杏仁薏苡甘草汤',
    '麻黄醇酒汤': '麻黄醇酒汤',
    '麻黄附子汤': '麻黄附子汤',
    '麻黄附子甘草汤': '麻黄附子甘草汤',
    '黄耆建中汤': '黄芪建中汤',
    '黄耆桂枝五物汤': '黄芪桂枝五物汤',
    '土瓜根散': '土瓜根散',
    '土瓜根方': '土瓜根方',
    '大黄䗪虫丸': '大黄䗪虫丸',
    '大黄硝石汤': '大黄硝石汤',
    '大黄附子汤': '大黄附子汤',
    '天雄散': '天雄散',
    '头风摩散方': '头风摩散',
    '栀子厚朴汤': '栀子厚朴汤',
    '栀子甘草豉汤': '栀子甘草豉汤',
    '栀子生薑豉汤': '栀子生姜豉汤',
    '四逆加吴茱萸生薑汤': '四逆加吴茱萸生姜汤',
    '四逆加猪胆汁汤': '四逆加猪胆汁汤',
}

# ===== Helper: normalize name for search =====
def normalize(name):
    n = name.replace('乾','干').replace('薑','姜').replace('朮','术')
    n = n.replace('耆','芪').replace('䗪','蛰').replace('當歸','当归')
    n = n.replace('栝蒌','瓜蒌').replace('蒌','蒌')
    n = n.replace('發','发').replace('髮','发').replace('餘','余').replace('糧','粮')
    n = n.replace('黃','黄').replace('芐','苄').replace('纔','才')
    n = n.replace('湯','汤').replace('劑','剂').replace('黃','黄')
    return n

# ===== Helper: extract symptoms from text before formula =====
def extract_indicators_from_text(before_text):
    found = set()
    result = []
    pats = [
        r'(发热|不发热|身热|潮热|微热|烦热|无热|恶寒|恶风|恶热|微恶寒|微恶风|不恶寒|不恶风)',
        r'(汗出|自汗|盗汗|无汗|大汗|微汗|汗漏|汗自出|不汗|不得汗)',
        r'(头痛|头项强|项强|头眩|头晕|头重|头不痛)',
        r'(身痛|身重|身黄|身肿|身痒|身不痛|身润)',
        r'(口不渴|口渴|口苦|口燥|口干|口烂|口伤)',
        r'(呕吐|干呕|欲呕|呕逆|吐利|吐逆|吐水|吐涎|吐|不呕|欲吐)',
        r'(下利|自利|大便硬|大便难|不大便|便血|便脓血|溏|不结胸|大便)',
        r'(小便不利|小便难|小便自利|小便数|小便少|小便|小便利)',
        r'(胸满|胸痹|胸痞|胸痛|胁满|胁痛|心下满|心下痞|心下|腹满|腹胀|腹痛|少腹满|少腹硬|腹皮)',
        r'(烦躁|躁烦|心烦|心乱|不得卧|不得眠|卧起不安|但欲寐)',
        r'(咳嗽|喘|短气|上气|不得息|咳|不喘)',
        r'(不能食|能食|欲食|饥|不欲饮食|不饮食|饮食)',
        r'(悸|惊|狂|谵语|独语|如见鬼状|惊狂)',
        r'(厥|四逆|手足厥|手足寒|手足冷|手足温)',
        r'(痉|拘急|挛急|脚挛急|转筋|四肢微急)',
        r'(渴|不渴|消渴)',
        r'(鼻鸣|鼻塞|鼻干|鼻燥)',
        r'(目眩|目赤|目黄|目瞑)',
        r'(胁下|胸胁)',
        r'(少腹弦急|阴头寒|发落|精自出)',
        r'(中风|风痱|身不仁|身不收)',
        r'(匍匐|偏枯|半身不遂)',
    ]
    for pat in pats:
        for match in re.finditer(pat, before_text):
            val = match.group(1)
            if val not in found:
                result.append(val)
                found.add(val)
    return result[:10]

def extract_pulse_from_text(text):
    pulses = []
    for m in re.finditer(r'脉[浮沉数迟紧缓滑涩虚实微细弦洪大弱小结促代]*(?:而[浮沉数迟紧缓滑涩虚实微细弦洪大弱小结促代]+)?', text):
        val = m.group(0).rstrip('者,。；;')
        if len(val) >= 3 and val not in pulses:
            pulses.append(val)
    return pulses[:4]

# ===== Build search names for each formula =====
unmatched = [fm for fm in formulas if not fm.get('core_indicators') or len(fm['core_indicators']) == 0]
print(f'Unmatched formulas: {len(unmatched)}')

# Create text corpus with position tracking
corpus = [
    ('伤寒论', sh, 'SHL'),
    ('金匮要略', jk, 'JKYL'),
]

updated = 0
still_unmatched = 0

for fm in unmatched:
    name = fm['name']
    search_names = [name]
    
    # Add alias from mapping
    if name in ALIASES and ALIASES[name] != name:
        search_names.append(ALIASES[name])
    
    # Normalized variants
    search_names.append(normalize(name))
    
    # Remove duplicates
    seen = set()
    unique_names = []
    for sn in search_names:
        sn_clean = sn.replace('\u200b','')
        if sn_clean not in seen:
            seen.add(sn_clean)
            unique_names.append(sn_clean)
    
    found = False
    for src_name, src_text, src_prefix in corpus:
        if found:
            break
        
        for search_name in unique_names:
            idx = src_text.find(search_name)
            if idx < 0:
                continue
            
            # Found! Extract context
            start = max(0, idx - 300)
            end = min(len(src_text), idx + 400)
            context = src_text[start:end]
            
            # Extract symptoms from text before the formula name
            before = src_text[max(0, idx - 400):idx]
            symptoms = extract_indicators_from_text(before)
            if symptoms:
                fm['core_indicators'] = symptoms
            
            # Extract pulse
            pulse = extract_pulse_from_text(before)
            if pulse:
                if 'typical_pulse' not in fm or not fm['typical_pulse']:
                    fm['typical_pulse'] = pulse
            
            # Extract pathogenesis hints
            patho_parts = []
            if '中风' in before and '风' not in str(patho_parts): patho_parts.append('风邪外袭')
            if '伤寒' in before: patho_parts.append('风寒外束')
            if '少阴' in before:
                patho_parts.append('少阴病' if '寒' in before else '少阴热化')
            if '瘀' in before or '蓄血' in before: patho_parts.append('瘀血内停')
            if '水气' in before or '水' in before: patho_parts.append('水饮内停')
            if '虚' in before: patho_parts.append('正气亏虚')
            if '热' in before and '利' in before: patho_parts.append('热利下重')
            if patho_parts:
                fm['core_pathogenesis'] = '；'.join(patho_parts[:3])
            
            # Source reference
            # Find clause number
            clause_num = None
            if src_name == '伤寒论':
                m = re.search(r'(\d+)．[^。]*'+re.escape(search_name), src_text[max(0,idx-100):idx+100])
                if m:
                    clause_num = int(m.group(1))
                else:
                    m2 = re.search(r'(\d+)．', src_text[max(0,idx-200):idx])
                    if m2:
                        clause_num = int(m2.group(1))
                if clause_num:
                    fm['source_clause'] = f'SHL-{clause_num:03d}'
            else:
                m = re.search(r'(\d+)．[^。]*'+re.escape(search_name), src_text[max(0,idx-100):idx+100])
                if m:
                    clause_num = int(m.group(1))
                else:
                    m2 = re.search(r'(\d+)．', src_text[max(0,idx-200):idx])
                    if m2:
                        clause_num = int(m2.group(1))
                if clause_num:
                    fm['source_clause'] = f'JKYL-{clause_num:03d}'
            
            # Six channel
            chapter_name = ''
            chap_m = re.search(r'<篇名>([^<]+)', src_text[max(0,idx-500):idx])
            if chap_m:
                chapter_name = chap_m.group(1)
            for ch in ['太阳','阳明','少阳','太阴','少阴','厥阴']:
                if ch in chapter_name:
                    fm['six_channel'] = ch
                    break
            
            updated += 1
            found = True
            break
    
    if not found:
        still_unmatched += 1

# Stats
before_count = sum(1 for fm in formulas if fm.get('core_indicators') and len(fm['core_indicators']) > 0)
after_count = sum(1 for fm in formulas if fm.get('core_indicators') and len(fm['core_indicators']) > 0)

print(f'Second-pass updates: {updated}')
print(f'Still unmatched: {still_unmatched}')
print(f'Total with clinical data: {after_count}/{len(formulas)}')

# Save
p.write_text(json.dumps(formulas, ensure_ascii=False, indent=2), encoding='utf-8')
print('Saved formulas.json')
