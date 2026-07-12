# coding: utf-8
"""Parse 275方剂完整整理.md, extract all formulas, generate complete JSON entries, merge with existing."""
import json, re, os, pathlib

script_dir = pathlib.Path(__file__).parent.resolve()

# ===== 1. Pinyin ID mapping =====
# Common herb/formula character -> pinyin for ID generation
PINYIN_MAP = {
    '一':'yi','三':'san','不':'bu','丹':'dan','乌':'wu','九':'jiu','乾':'gan',
    '二':'er','五':'wu','人':'ren','代':'dai','仙':'xian','伏':'fu','何':'he',
    '余':'yu','侯':'hou','俞':'shu','健':'jian','僵':'jiang','八':'ba',
    '六':'liu','冬':'dong','凌':'ling','刀':'dao','分':'fen','刘':'liu',
    '前':'qian','十':'shi','半':'ban','华':'hua','升':'sheng','单':'dan',
    '南':'nan','又':'you','及':'ji','发':'fa','变':'bian','口':'kou',
    '古':'gu','叶':'ye','合':'he','吴':'wu','吸':'xi','吹':'chui',
    '呐':'na','呋':'fu','味':'wei','和':'he','咳':'ke','哕':'yue',
    '咽':'yan','哎':'ai','哈':'ha','哌':'pai','咳':'ke','唐':'tang',
    '商':'shang','喘':'chuan','喜':'xi','喝':'he','喘':'chuan','噫':'yi',
    '器':'qi','呕':'ou','噎':'ye','四':'si','回':'hui','因':'yin',
    '固':'gu','圈':'quan','土':'tu','地':'di','均':'jun','坎':'kan',
    '垢':'gou','垣':'yuan','坚':'jian','坠':'zhui','埋':'mai','堂':'tang',
    '堆':'dui','备':'bei','夏':'xia','外':'wai','多':'duo','大':'da',
    '天':'tian','头':'tou','夹':'jia','夷':'yi','夺':'duo','女':'nv',
    '奶':'nai','好':'hao','如':'ru','妇':'fu','子':'zi','存':'cun',
    '孙':'sun','守':'shou','安':'an','完':'wan','定':'ding','官':'guan',
    '实':'shi','宣':'xuan','室':'shi','宫':'gong','家':'jia','寸':'cun',
    '小':'xiao','尖':'jian','尻':'kao','尿':'niao','层':'ceng','山':'shan',
    '岁':'sui','川':'chuan','左':'zuo','差':'ci','己':'ji','巴':'ba',
    '干':'gan','平':'ping','年':'nian','并':'bing','广':'guang','庄':'zhuang',
    '麻':'ma','鹿':'lu','黄':'huang','黎':'li','黑':'hei','黍':'shu',
    '龙':'long','龟':'gui','一':'yi','丁':'ding','七':'qi','万':'wan',
    '丈':'zhang','上':'shang','下':'xia','丐':'gai','丑':'chou','专':'zhuan',
    '且':'qie','丕':'pi','世':'shi','丘':'qiu','丙':'bing','业':'ye',
    '丛':'cong','东':'dong','丝':'si','中':'zhong','串':'chuan','丸':'wan',
    '丹':'dan','主':'zhu','久':'jiu','之':'zhi','乌':'wu','乍':'zha',
    '乎':'hu','乏':'fa','乖':'guai','乘':'cheng','乙':'yi','也':'ye',
    '乡':'xiang','书':'shu','乳':'ru','干':'gan','乱':'luan','了':'liao',
    '事':'shi','二':'er','云':'yun','互':'hu','五':'wu','井':'jing',
    '交':'jiao','京':'jing','亭':'ting','亮':'liang','人':'ren','仆':'pu',
    '仇':'chou','今':'jin','介':'jie','仍':'reng','从':'cong','仔':'zi',
    '他':'ta','仙':'xian','代':'dai','令':'ling','以':'yi','仰':'yang',
    '仲':'zhong','任':'ren','伤':'shang','伊':'yi','伏':'fu','休':'xiu',
    '众':'zhong','优':'you','会':'hui','伟':'wei','传':'chuan','伪':'wei',
    '伯':'bo','估':'gu','伴':'ban','伸':'shen','似':'si','位':'wei',
    '住':'zhu','作':'zuo','你':'ni','佩':'pei','供':'gong','使':'shi',
    '例':'li','侠':'xia','侥':'jiao','侧':'ce','侨':'qiao','侯':'hou',
    '侵':'qin','便':'bian','促':'cu','俄':'e','俊':'jun','俗':'su',
    '保':'bao','信':'xin','修':'xiu','俱':'ju','俺':'an','倍':'bei',
    '倒':'dao','候':'hou','借':'jie','假':'jia','偏':'pian','做':'zuo',
    '停':'ting','健':'jian','侧':'ce','偶':'ou','偷':'tou','傅':'fu',
    '傍':'bang','备':'bei','催':'cui','伤':'shang','傻':'sha','像':'xiang',
    '僚':'liao','僵':'jiang','儿':'er','元':'yuan','兄':'xiong','充':'chong',
    '兆':'zhao','先':'xian','光':'guang','克':'ke','免':'mian','兑':'dui',
    '兔':'tu','党':'dang','入':'ru','全':'quan','八':'ba','公':'gong',
    '六':'liu','兰':'lan','共':'gong','关':'guan','其':'qi','具':'ju',
    '典':'dian','养':'yang','兽':'shou','内':'nei','再':'zai','冒':'mao',
    '写':'xie','军':'jun','农':'nong','冠':'guan','冬':'dong','冰':'bing',
    '冲':'chong','决':'jue','冶':'ye','冷':'leng','净':'jing','凝':'ning',
    '几':'ji','凡':'fan','凤':'feng','凭':'ping','凯':'kai','凶':'xiong',
    '出':'chu','击':'ji','分':'fen','切':'qie','刊':'kan','刑':'xing',
    '划':'hua','列':'lie','刘':'liu','则':'ze','刚':'gang','创':'chuang',
    '初':'chu','判':'pan','别':'bie','利':'li','到':'dao','制':'zhi',
    '刷':'shua','刺':'ci','刻':'ke','剂':'ji','前':'qian','剑':'jian',
    '剔':'ti','剥':'bao','剧':'ju','剩':'sheng','剪':'jian','副':'fu',
    '割':'ge','力':'li','办':'ban','功':'gong','加':'jia','务':'wu',
    '动':'dong','助':'zhu','努':'nu','劫':'jie','励':'li','劳':'lao',
    '势':'shi','劲':'jin','勉':'mian','勇':'yong','勒':'le','动':'dong',
    '勘':'kan','勾':'gou','勿':'wu','包':'bao','匆':'cong','化':'hua',
    '北':'bei','匕':'bi','匙':'chi','匮':'kui','十':'shi','千':'qian',
    '升':'sheng','午':'wu','半':'ban','华':'hua','卑':'bei','卒':'zu',
    '卓':'zhuo','协':'xie','南':'nan','博':'bo','占':'zhan','卡':'ka',
    '卢':'lu','卫':'wei','印':'yin','危':'wei','即':'ji','却':'que',
    '卵':'luan','卷':'juan','卸':'xie','厚':'hou','原':'yuan','厨':'chu',
    '厦':'sha','去':'qu','参':'shen','又':'you','双':'shuang','反':'fan',
    '发':'fa','取':'qu','受':'shou','变':'bian','叙':'xu','口':'kou',
    '古':'gu','另':'ling','只':'zhi','叫':'jiao','召':'zhao','可':'ke',
    '台':'tai','史':'shi','右':'you','叶':'ye','号':'hao','司':'si',
    '吃':'chi','各':'ge','合':'he','吉':'ji','同':'tong','名':'ming',
    '后':'hou','吐':'tu','向':'xiang','君':'jun','否':'fou','吠':'fei',
    '呆':'dai','吴':'wu','呈':'cheng','告':'gao','呕':'ou','吸':'xi',
    '吹':'chui','吻':'wen','吼':'hou','吖':'a','呆':'dai','呃':'e',
    '听':'ting','启':'qi','呆':'dai','呕':'ou','呖':'li','呗':'bei',
    '员':'yuan','呛':'qiang','吲':'yin','否':'fou','听':'ting',
    '含':'han','吩':'fen','吪':'e','吮':'shun','吹':'chui',
    '吼':'hou','邑':'yi','吧':'ba','别':'bie','吮':'shun','吱':'zhi',
    '呕':'ou','呀':'ya','吵':'chao','呐':'na','吸':'xi','呜':'wu',
    '呆':'dai','叭':'ba','呈':'cheng','告':'gao','呋':'fu','呕':'ou',
    '呗':'bei','员':'yuan','呛':'qiang','听':'ting',
    '含':'han','吩':'fen','吪':'e','吮':'shun','吹':'chui','吼':'hou',
    '邑':'yi','吧':'ba','别':'bie','吮':'shun','吱':'zhi','呕':'ou',
    '呀':'ya','吵':'chao','呐':'na','吸':'xi','呜':'wu',
    '呆':'dai','叭':'ba','呈':'cheng','告':'gao',
    '吴':'wu','吸':'xi','吕':'lv','告':'gao','呕':'ou','周':'zhou',
    '味':'wei','呵':'he','呼':'hu','命':'ming','和':'he','咳':'ke',
    '咽':'yan','哀':'ai','品':'pin','哌':'pai','哇':'wa','哈':'ha',
    '响':'xiang','哎':'ai','哑':'ya','哒':'da','哔':'bi','哕':'yue',
    '哟':'yo','哪':'na','员':'yuan','哥':'ge','哦':'o','哓':'xiao',
    '咳':'ke','哭':'ku','哮':'xiao','哺':'bu','哽':'geng','唔':'wu',
    '唁':'yan','哼':'heng','啊':'a','唆':'suo','唇':'chun','唐':'tang',
    '啦':'la','啪':'pa','啰':'luo','啸':'xiao','售':'shou','唯':'wei',
    '唱':'chang','商':'shang','啊':'a','啡':'fei','啥':'sha','啦':'la',
    '喂':'wei','喘':'chuan','喜':'xi','喝':'he','喧':'xuan','嗒':'da',
    '嗓':'sang','嗽':'sou','嘉':'jia','嘤':'ying','噫':'yi','器':'qi',
    '噩':'e','噪':'zao','囊':'nang','四':'si','回':'hui','因':'yin',
    '团':'tuan','困':'kun','围':'wei','园':'yuan','圆':'yuan','图':'tu',
    '国':'guo','土':'tu','圣':'sheng','在':'zai','地':'di','场':'chang',
    '圾':'ji','址':'zhi','均':'jun','坎':'kan','坏':'huai','坐':'zuo',
    '坑':'keng','块':'kuai','坚':'jian','坛':'tan','坝':'ba','坠':'zhui',
    '坡':'po','坤':'kun','坦':'tan','坪':'ping','坳':'ao','型':'xing',
    '城':'cheng','埔':'pu','埋':'mai','埃':'ai','堵':'du','堂':'tang',
    '堆':'dui','堕':'duo','堤':'di','堪':'kan','堰':'yan','堵':'du',
    '填':'tian','塌':'ta','塞':'sai','墙':'qiang','增':'zeng','墨':'mo',
    '壁':'bi','士':'shi','壮':'zhuang','声':'sheng','备':'bei','处':'chu',
    '复':'fu','夏':'xia','外':'wai','多':'duo','夜':'ye','够':'gou',
    '梦':'meng','大':'da','天':'tian','头':'tou','夹':'jia','夺':'duo',
    '女':'nv','奸':'jian','好':'hao','如':'ru','妇':'fu','妊':'ren',
    '妖':'yao','妙':'miao','妥':'tuo','妨':'fang','妹':'mei','妻':'qi',
    '姤':'gou','始':'shi','姑':'gu','娃':'wa','姥':'lao','姨':'yi',
    '姻':'yin','姿':'zi','威':'wei','娃':'wa','娄':'lou','娇':'jiao',
    '娘':'niang','娩':'mian','媒':'mei','媚':'mei','嫂':'sao','嫁':'jia',
    '嫌':'xian','嫩':'nen','子':'zi','孔':'kong','孕':'yun','存':'cun',
    '孙':'sun','孝':'xiao','孟':'meng','季':'ji','孤':'gu','学':'xue',
    '孩':'hai','宁':'ning','它':'ta','安':'an','完':'wan','宋':'song',
    '宏':'hong','牢':'lao','灾':'zai','实':'shi','宣':'xuan','室':'shi',
    '宫':'gong','害':'hai','家':'jia','容':'rong','宽':'kuan','宿':'su',
    '寂':'ji','密':'mi','寒':'han','富':'fu','实':'shi','寝':'qin',
    '塞':'sai','寞':'mo','察':'cha','寡':'gua','寝':'qin','宁':'ning',
    '寨':'zhai','寸':'cun','对':'dui','导':'dao','寻':'xun','封':'feng',
    '射':'she','将':'jiang','小':'xiao','少':'shao','尔':'er','尖':'jian',
    '尚':'shang','尻':'kao','尺':'chi','尼':'ni','尽':'jin','尾':'wei',
    '尿':'niao','局':'ju','屁':'pi','层':'ceng','居':'ju','屈':'qu',
    '屋':'wu','屏':'ping','展':'zhan','屠':'tu','屡':'lv','履':'lv',
    '山':'shan','岁':'sui','川':'chuan','州':'zhou','巡':'xun','工':'gong',
    '左':'zuo','巧':'qiao','巨':'ju','差':'ci','己':'ji','已':'yi',
    '巴':'ba','巷':'xiang','巾':'jin','市':'shi','布':'bu','帅':'shuai',
    '师':'shi','希':'xi','帐':'zhang','带':'dai','常':'chang','帽':'mao',
    '幕':'mu','干':'gan','平':'ping','年':'nian','并':'bing','幻':'huan',
    '幼':'you','几':'ji','幽':'you','广':'guang','庄':'zhuang','床':'chuang',
    '庐':'lu','序':'xu','库':'ku','应':'ying','底':'di','店':'dian',
    '府':'fu','度':'du','座':'zuo','廉':'lian','廊':'lang','延':'yan',
    '建':'jian','开':'kai','异':'yi','弃':'qi','弄':'nong','式':'shi',
    '引':'yin','弘':'hong','弟':'di','张':'zhang','弥':'mi','弹':'tan',
    '归':'gui','当':'dang','形':'xing','彩':'cai','影':'ying','彻':'che',
    '彼':'bi','往':'wang','征':'zheng','径':'jing','待':'dai','很':'hen',
    '得':'de','循':'xun','微':'wei','德':'de','心':'xin','志':'zhi',
    '成':'cheng','我':'wo','战':'zhan','截':'jie','所':'suo',
    '手':'shou','才':'cai','扎':'zha','打':'da','扣':'kou','扦':'qian',
    '执':'zhi','扫':'sao','扬':'yang','扶':'fu','抚':'fu','抠':'kou',
    '扰':'rao','扼':'e','承':'cheng','投':'tou','抑':'yi','抛':'pao',
    '把':'ba','报':'bao','拟':'ni','抒':'shu','抓':'zhua','投':'tou',
    '抖':'dou','抗':'kang','折':'zhe','抚':'fu','抛':'pao','拈':'nian',
    '拉':'la','拦':'lan','招':'zhao','拔':'ba','拨':'bo','放':'fang',
    '政':'zheng','故':'gu','效':'xiao','救':'jiu','教':'jiao','敢':'gan',
    '散':'san','敬':'jing','数':'shu','整':'zheng','文':'wen',
    '刘':'liu','齐':'qi','斋':'zhai','斗':'dou','斜':'xie','方':'fang',
    '于':'yu','施':'shi','旁':'pang','旋':'xuan','旗':'qi','无':'wu',
    '日':'ri','旦':'dan','旧':'jiu','早':'zao','旬':'xun','时':'shi',
    '旺':'wang','明':'ming','昏':'hun','易':'yi','星':'xing','春':'chun',
    '昨':'zuo','昼':'zhou','显':'xian','晕':'yun','暖':'nuan','暗':'an',
    '暴':'bao','更':'geng','曹':'cao','会':'hui','月':'yue','有':'you',
    '服':'fu','望':'wang','朝':'zhao','木':'mu','未':'wei','末':'mo',
    '本':'ben','朱':'zhu','朴':'pu','杂':'za','权':'quan','李':'li',
    '杏':'xing','材':'cai','杖':'zhang','杜':'du','束':'shu','条':'tiao',
    '来':'lai','杨':'yang','杭':'hang','杯':'bei','束':'shu','板':'ban',
    '林':'lin','果':'guo','枝':'zhi','枇':'pi','枢':'shu','枣':'zao',
    '析':'xi','柜':'gui','枰':'ping','枳':'zhi','枸':'gou','柏':'bai',
    '染':'ran','柔':'rou','柰':'nai','柱':'zhu','柳':'liu','柴':'chai',
    '柿':'shi','栀':'zhi','栅':'zha','标':'biao','栈':'zhan','栋':'dong',
    '查':'cha','柬':'jian','枯':'ku','架':'jia','柄':'bing','枳':'zhi',
    '某':'mou','染':'ran','柔':'rou','柚':'you','柜':'gui','柞':'zuo',
    '柏':'bai','柢':'di','柰':'nai','柱':'zhu','柳':'liu','柴':'chai',
    '柿':'shi','栀':'zhi','栅':'zha','标':'biao','栈':'zhan','栋':'dong',
    '树':'shu','栗':'li','校':'xiao','株':'zhu','核':'he','根':'gen',
    '格':'ge','栽':'zai','桂':'gui','桃':'tao','桐':'tong','桑':'sang',
    '桔':'ju','档':'dang','桥':'qiao','桨':'jiang','梁':'liang','梅':'mei',
    '梓':'zi','梢':'shao','梨':'li','梆':'bang','梧':'wu','梨':'li',
    '桨':'jiang','梅':'mei','梓':'zi','条':'tiao','梦':'meng','梵':'fan',
    '棉':'mian','棋':'qi','棍':'gun','棒':'bang','棘':'ji','棚':'peng',
    '椎':'zhui','棠':'tang','枚':'mei','杨':'yang','楚':'chu',
    '槐':'huai','槁':'gao','概':'gai','樗':'chu','樽':'zun','橙':'cheng',
    '橘':'ju','橱':'chu','檀':'tan','欠':'qian','次':'ci','欢':'huan',
    '欧':'ou','欲':'yu','欺':'qi','歇':'xie','止':'zhi','正':'zheng',
    '此':'ci','步':'bu','武':'wu','歧':'qi','历':'li','归':'gui',
    '死':'si','殊':'shu','段':'duan','殷':'yin','毁':'hui','殿':'dian',
    '母':'mu','每':'mei','毒':'du','比':'bi','毕':'bi','毛':'mao',
    '毫':'hao','民':'min','气':'qi','水':'shui','火':'huo','父':'fu',
    '交':'jiao','亥':'hai','亦':'yi','产':'chan','充':'chong','亥':'hai',
    '亩':'mu','享':'xiang','京':'jing','亭':'ting','亮':'liang','亲':'qin',
    '亵':'xie','毫':'hao','孰':'shu','熟':'shu',
    '姜':'jiang','芍':'shao','芎':'qiong','莲':'lian','蔚':'wei',
    '苓':'ling','薏':'yi','苡':'yi','苈':'li','防':'fang','己':'ji',
    '芪':'qi','蓣':'yu','苄':'bian','芎':'xiong','归':'gui','连':'lian',
    '翘':'qiao','轺':'yao',
    '大':'da','小':'xiao','汤':'tang','散':'san','丸':'wan','膏':'gao',
    '酒':'jiu','丸':'wan','散':'san','汤':'tang','膏':'gao','酒':'jiu',
    '方':'fang','煎':'jian','洗':'xi','导':'dao','摩':'mo',
}

def name_to_id(name):
    """Convert Chinese formula name to camelCase pinyin ID"""
    # Normalize common characters first
    n = name
    # Remove trailing 汤/散/丸/膏/酒/方 for base
    base = re.sub(r'[汤汤散丸膏酒方]$', '', n)
    result = 'F-'
    parts = re.findall(r'[\u4e00-\u9fff]+', base)
    for part in parts:
        for ch in part:
            if ch in PINYIN_MAP:
                result += PINYIN_MAP[ch]
            else:
                result += ch
    # Handle missing pinyin
    return result

# ===== 2. Parse reference doc =====
with open('D:/SoftWareInstall/opencode/ChineseMedicine/docs/275方剂完整整理.md', 'r', encoding='utf-8') as f:
    ref_text = f.read()

# Split into individual formula sections
formula_sections = re.split(r'\n(?=## \d+\.\s+)', ref_text)
# Remove non-formula sections (header, intro)
formula_sections = [s for s in formula_sections if re.match(r'## \d+\.\s+', s.strip())]

print(f'Formula sections found: {len(formula_sections)}')

def parse_formula_section(section):
    """Parse one formula section into structured data"""
    lines = section.strip().split('\n')
    result = {}
    
    # Extract name from "## N. Name"
    name_match = re.match(r'## \d+\.\s+(.*)', lines[0])
    if not name_match:
        return None
    name = name_match.group(1).strip()
    result['name'] = name
    
    # Find sections
    current_section = None
    section_content = {}
    
    for line in lines[1:]:
        m = re.match(r'###\s+(.*)', line.strip())
        if m:
            current_section = m.group(1).strip()
            section_content[current_section] = []
        elif current_section:
            section_content[current_section].append(line)
    
    # Extract 原文 (original text - herbs with doses)
    herbs_raw = section_content.get('原文', [])
    if herbs_raw:
        text = ''.join(herbs_raw).strip()
        result['original_text'] = text
        # Parse individual herbs
        herbs = []
        for h in re.split(r'[、，,]', text):
            h = h.strip()
            if h:
                herbs.append(h)
        result['herbs_raw'] = herbs
    
    # Extract 折算现代计量 (modern dosage)
    dosage_lines = section_content.get('折算现代计量', [])
    result['dosage_lines'] = [l.strip() for l in dosage_lines if l.strip()]
    
    # Parse composition (herb + dose + preparation)
    composition = []
    for line in result.get('dosage_lines', []):
        # Format: "药材名 剂量（处理方式）" or "药材名 剂量" or "药材名等分"
        m = re.match(r'^(.+?)(?:[（(](.*?)[）)])?\s*$', line)
        if m:
            herb_name = m.group(1).strip()
            # Extract dose
            dose_match = re.match(r'^(.+?)([一两三四五六七八九十半分钱克升合等\d.]+(?:\s*[两钱分克升合])?)$', herb_name)
            if dose_match:
                herb = dose_match.group(1).strip()
                dose = dose_match.group(2).strip()
            else:
                herb = herb_name
                dose = ''
            prep = m.group(2) if m.group(2) else ''
            composition.append({
                'herb': herb,
                'dose': dose,
                'desc': prep
            })
    
    result['composition'] = composition if composition else []
    
    # Extract 用法 (usage)
    usage_lines = section_content.get('用法', [])
    result['usage'] = ''.join(usage_lines).strip() if usage_lines else ''
    
    # Extract 注 (notes)
    note_lines = section_content.get('注', [])
    result['notes'] = ''.join(note_lines).strip() if note_lines else ''
    
    # Extract 相关条文 (related clauses)
    clause_lines = section_content.get('相关条文', [])
    result['related_clauses'] = ''.join(clause_lines).strip() if clause_lines else ''
    
    return result

# Parse all formulas
all_parsed = []
for section in formula_sections:
    parsed = parse_formula_section(section)
    if parsed:
        all_parsed.append(parsed)

print(f'Successfully parsed: {len(all_parsed)}')

# ===== 3. Load current KB =====
with open(os.path.join(script_dir, 'assets', 'formulas.json'), 'r', encoding='utf-8') as f:
    existing_formulas = json.load(f)

existing_names = set()
existing_ids = set()
for fm in existing_formulas:
    existing_names.add(fm['name'])
    existing_ids.add(fm['id'])
    # Normalize for matching
    n = fm['name'].replace('干','干').replace('生','生')  # keep original

# Build normalization for matching
def norm_name(name):
    n = name.replace('乾','干').replace('薑','姜').replace('朮','术')
    n = n.replace('耆','芪').replace('䗪','蛰').replace('蒌','蒌')
    n = re.sub(r'[（(][^）)]*[）)]$', '', n).strip()
    return n

def core_name(name):
    return re.sub(r'[汤汤散丸膏酒方]$', '', norm_name(name))

existing_cores = set()
for fm in existing_formulas:
    existing_cores.add(core_name(fm['name']))

# Known equivalent groups (same formula, different name)
EQUIV_GROUPS = [
    {'苓桂术甘汤', '茯苓桂枝白术甘草汤', '茯苓桂枝白甘草汤'},
    {'桂枝去桂加茯苓白术汤', '去桂加白术汤', '去桂加白汤', '桂枝去桂加茯苓白汤'},
    {'千金三黄汤', '三黄汤'},
    {'崔氏八味丸', '肾气丸', '八味肾气丸'},
    {'侯氏黑散', '黑散'},
    {'风引汤', '紫石寒食散'},
    {'当归生姜羊肉汤', '当归生薑羊肉汤'},
    {'厚朴生姜半夏甘草人参汤', '厚朴生薑半夏甘草人参汤'},
    {'桂枝加芍药生姜人参新加汤', '桂枝加芍药生姜各一两人参三两新加汤',
     '桂枝加芍药生薑人参新加汤', '桂枝加芍药生薑各一两人参三两新加汤'},
    {'小半夏加茯苓汤', '小半夏茯苓汤'},
    {'桂苓五味甘草汤去桂加干姜细辛', '桂苓五味甘草汤去桂加乾薑、细辛', '苓甘五味姜辛汤'},
    {'甘草干姜茯苓白术汤', '甘姜苓术汤', '肾着汤'},
    {'大乌头煎', '乌头煎'},
    {'乌头桂枝汤', '抵当乌头桂枝汤'},
    {'柴胡桂枝干姜汤', '柴胡桂姜汤'},
    {'木防己汤去石膏加茯苓芒硝汤', '木防己加茯苓芒硝汤'},
    {'千金苇茎汤', '苇茎汤'},
    {'猪膏发煎', '膏发煎'},
    {'赤石脂禹余粮汤', '赤石脂禹馀粮汤', '禹馀粮丸'},
    {'诃黎勒散', '诃黎勒丸'},
]

equiv_cores = {}
for grp in EQUIV_GROUPS:
    base = None
    for item in grp:
        c = core_name(item)
        if base is None:
            base = c
    for item in grp:
        equiv_cores[core_name(item)] = base  # map all to base

def is_in_kb(name):
    """Exact core matching only - no substring matching to avoid overmatching"""
    c = core_name(name)
    if c in existing_cores:
        return True
    if c in equiv_cores:
        if equiv_cores[c] in existing_cores:
            return True
    return False

# ===== 4. Generate new entries =====
CATEGORY_MAP = {
    '桂枝': '桂枝汤类',
    '麻黄': '麻黄汤类',
    '葛根': '葛根汤类',
    '柴胡': '柴胡汤类',
    '大承气': '承气汤类',
    '小承气': '承气汤类',
    '调胃承气': '承气汤类',
    '桃核承气': '承气汤类',
    '大陷胸': '陷胸汤类',
    '小陷胸': '陷胸汤类',
    '大黄': '大黄类',
    '黄连': '黄连汤类',
    '黄芩': '黄芩汤类',
    '栀子': '栀子剂类',
    '白虎': '白虎汤类',
    '竹叶石膏': '竹叶石膏汤类',
    '四逆': '四逆汤类',
    '通脉四逆': '四逆汤类',
    '白通': '四逆汤类',
    '理中': '理中类',
    '干姜': '理中类',
    '吴茱萸': '吴茱萸汤类',
    '真武': '真武汤类',
    '附子': '附子剂类',
    '茯苓桂枝': '苓桂剂类',
    '苓桂': '苓桂剂类',
    '五苓': '五苓散类',
    '猪苓': '猪苓汤类',
    '泽泻': '泽泻汤类',
    '茵陈': '茵陈蒿汤类',
    '防己': '防己黄芪汤类',
    '赤石脂': '桃花汤类',
    '桃花': '桃花汤类',
    '半夏泻心': '泻心汤类',
    '甘草泻心': '泻心汤类',
    '生姜泻心': '泻心汤类',
    '附子泻心': '泻心汤类',
    '泻心': '泻心汤类',
    '白头翁': '白头翁汤类',
    '小建中': '小建中汤类',
    '当归芍药': '当归芍药散类',
    '当归四逆': '当归四逆汤类',
    '温经': '温经汤类',
    '炙甘草': '炙甘草汤类',
    '麦门冬': '麦门冬汤类',
    '甘麦大枣': '甘麦大枣汤类',
    '酸枣仁': '酸枣仁汤类',
    '旋覆': '旋覆代赭汤类',
    '旋覆花': '旋覆代赭汤类',
    '代赭': '旋覆代赭汤类',
    '百合': '百合地黄汤类',
    '肾气': '肾气丸类',
    '乌梅': '乌梅丸类',
    '厚朴七物': '厚朴七物汤类',
    '厚朴生姜': '厚朴生姜半夏甘草人参汤类',
    '黄土': '黄土汤类',
    '大黄牡丹': '大黄牡丹汤类',
    '瓜蒌薤白': '栝蒌薤白白酒汤类',
    '麻黄附子': '麻黄附子类',
    '栝蒌薤白': '栝蒌薤白白酒汤类',
    '桔梗': '桔梗汤类',
    '半夏厚朴': '半夏厚朴汤类',
    '芍药甘草': '芍药甘草汤类',
    '麻黄升麻': '麻黄汤类',
    '麻黄杏仁甘草石膏': '麻黄汤类',
    '麻黄杏仁薏苡': '麻黄汤类',
    '麻黄连轺': '麻黄汤类',
    '麻黄加术': '麻黄汤类',
    '麻黄醇酒': '麻黄汤类',
    '续命': '麻黄汤类',
    '越婢': '越婢汤类',
    '射干麻黄': '射干麻黄汤类',
    '厚朴麻黄': '厚朴麻黄汤类',
    '泽漆': '泽漆汤类',
    '小青龙': '小青龙汤类',
    '大青龙': '大青龙汤类',
    '十枣': '十枣汤类',
    '大黄蛰虫': '大黄蛰虫丸类',
    '大黄䗪虫': '大黄蛰虫丸类',
    '鳖甲': '鳖甲煎丸类',
    '薯蓣': '薯蓣丸类',
    '王不留行': '王不留行散类',
    '薏苡附子败酱': '薏苡附子败酱散类',
    '薏苡附子': '薏苡附子散类',
    '葶苈': '葶苈大枣泻肺汤类',
    '桔梗': '桔梗汤类',
    '皂荚': '皂荚丸类',
    '赤豆当归': '赤豆当归散类',
    '红蓝花': '红蓝花酒类',
    '蛇床子': '蛇床子散类',
    '狼牙': '狼牙汤类',
    '矾石': '矾石汤类',
    '硝石矾石': '硝石矾石散类',
    '猪膏': '猪膏发煎类',
    '葵子茯苓': '葵子茯苓散类',
    '蒲灰': '蒲灰散类',
    '滑石白鱼': '滑石白鱼散类',
    '茯苓戎盐': '茯苓戎盐汤类',
    '蜘蛛': '蜘蛛散类',
    '蜀漆': '蜀漆散类',
    '牡蛎': '牡蛎汤类',
    '栝蒌牡蛎': '栝蒌牡蛎散类',
    '栝蒌瞿麦': '栝蒌瞿麦丸类',
    '鸡屎白': '鸡屎白散类',
    '蜜煎': '蜜煎导方类',
    '猪胆': '猪胆汁方类',
    '烧裈': '烧裈散类',
}

def classify_formula(name):
    """Assign a category based on formula name"""
    # Check name patterns
    for pattern, category in sorted(CATEGORY_MAP.items(), key=lambda x: -len(x[0])):
        if pattern in name:
            return category
    # Fallback
    return '其他类'

def determine_source(name, original_text, related_clauses):
    """Determine if formula is from 伤寒论 or 金匮要略"""
    # Known 金匮要略-only formulas
    jinkui_keywords = ['肾气丸', '崔氏八味', '酸枣仁', '甘麦大枣', '温经汤', '当归芍药',
                       '大黄蛰虫', '大黄䗪虫', '射干麻黄', '厚朴麻黄', '泽漆',
                       '越婢', '防己黄芪', '防己茯苓', '防己地黄', '侯氏黑', '风引',
                       '鳖甲煎', '薯蓣', '奔豚', '桂枝茯苓', '栝蒌薤白',
                       '橘皮', '橘枳', '排脓', '王不留行', '薏苡附子败酱',
                       '葶苈', '皂荚', '旋覆花', '柏叶', '黄土', '泻心',
                       '红蓝花', '蛇床子', '狼牙', '矾石', '硝石矾石',
                       '猪膏', '葵子茯苓', '蒲灰', '滑石白鱼',
                       '茯苓戎盐', '蜘蛛', '蜀漆', '鸡屎白',
                       '蜜煎', '猪胆汁', '烧裈', '续命', '还魂',
                       '紫石寒食', '三黄', '头风摩',
                       '半夏麻黄', '茯苓杏仁甘草', '小半夏', '甘遂半夏',
                       '厚朴三物', '厚朴大黄', '大建中', '大黄附子',
                       '大乌头煎', '乌头赤石脂', '乌头汤', '乌头桂枝',
                       '九痛', '附子粳米', '大黄甘草', '大黄甘遂',
                       '栝蒌瞿麦', '天雄', '桂苓五味', '茯苓桂枝五味',
                       '文蛤', '白朮散', '当归散', '当归贝母',
                       '矾石', '蛇床子', '狼牙',
                       '半夏干姜', '干姜人参半夏', '生姜半夏',
                       '甘草粉蜜', '甘姜苓术', '甘草麻黄',
                       '己椒苈黄', '小青龙加石膏', '越婢加半夏', '越婢加术',
                       '麻黄加术', '麻黄杏仁薏苡', '麻黄连轺',
                       '葶苈大枣', '吴茱萸', '大半夏', '赤石脂',
                       '白头翁加甘草', '胶艾', '胶姜',
                       '三物备急', '三物小白', '一物瓜蒂',
                       '竹叶汤', '竹皮大丸', '紫参', '诃黎勒',
                       '半夏散及', '苦酒', '麻黄升麻',
                       '赤丸', '走马',
                       '崔氏八味', '千金', '外台', '古今录验',
                       ]
    for kw in jinkui_keywords:
        if kw in name:
            return '金匮要略'
    # Check original text for clues
    if related_clauses and '金匮' in related_clauses:
        return '金匮要略'
    # Default to 伤寒论 (most formulas early in the doc are 伤寒论)
    return '伤寒论'

def generate_id(name, existing_ids):
    """Generate unique ID"""
    base_id = name_to_id(name)
    if base_id not in existing_ids:
        return base_id
    # Add suffix if duplicate
    suffix = 2
    while f'{base_id}_{suffix}' in existing_ids:
        suffix += 1
    return f'{base_id}_{suffix}'

def compose_original_dose(composition):
    """Generate original_dose string from composition"""
    if not composition:
        return ''
    parts = []
    for c in composition:
        herb = c['herb']
        dose = c['dose']
        desc = c['desc']
        if desc:
            parts.append(f'{herb}{dose}({desc})')
        elif dose:
            parts.append(f'{herb}{dose}')
        else:
            parts.append(herb)
    return '，'.join(parts)

def compose_dose_conversion(composition):
    """Generate dose_conversion from composition"""
    if not composition:
        return {}
    regular_parts = []
    therapeutic_parts = []
    severe_parts = []
    for c in composition:
        herb = c['herb']
        dose = c['dose']
        # Try to convert ancient dose to modern
        # 1两 ≈ 3g (regular), 5g (therapeutic), 10g (severe)
        dose_num = 0
        m = re.match(r'(?:各)?(?:等分)?(?:各?)([一二三四五六七八九十半\d.]+)(.*)', dose)
        # This is simplified - real conversion needs more logic
        regular_parts.append(herb)
    return {"regular": "待补", "therapeutic": "待补", "severe": "待补"}

# ===== 5. Build new formulas =====
new_formulas = []
for pf in all_parsed:
    name = pf['name']
    if is_in_kb(name):
        continue
    
    # Generate ID
    fid = generate_id(name, existing_ids | {f['id'] for f in new_formulas})
    existing_ids.add(fid)
    
    # Determine category
    category = classify_formula(name)
    
    # Determine source
    source = determine_source(name, pf.get('original_text', ''), pf.get('related_clauses', ''))
    if source == '伤寒论':
        source_clause = f'SHL-{len(new_formulas)+900:03d}'  # placeholder
    else:
        source_clause = f'JKYL-{len(new_formulas)+900:03d}'  # placeholder
    
    # Build composition
    composition = pf.get('composition', [])
    
    # Build entry
    entry = {
        "id": fid,
        "name": name,
        "source_clause": source_clause,
        "six_channel": "",
        "core_indicators": [],
        "exclusion_indicators": [],
        "composition": composition,
        "original_dose": compose_original_dose(composition),
        "dose_conversion": compose_dose_conversion(composition),
        "toxic_herbs": [],
        "main_indications": [],
        "typical_pulse": [],
        "core_pathogenesis": "",
        "decoction_method": pf.get('usage', ''),
        "dosage_form": "",
        "aftercare": "",
        "stop_criteria": "",
        "standard_modifications": [],
        "contraindications": [],
        "formula_category": category,
        "differentiators": ""
    }
    
    new_formulas.append(entry)

print(f'\nNew formulas to add: {len(new_formulas)}')

# ===== 6. Save updated formulas.json =====
all_formulas = existing_formulas + new_formulas

output_path = os.path.join(script_dir, 'assets', 'formulas.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_formulas, f, ensure_ascii=False, indent=2)

print(f'Saved: {len(all_formulas)} formulas to formulas.json')

# ===== 7. Update SKILL.md count =====
skill_path = os.path.join(script_dir, 'SKILL.md')
with open(skill_path, 'r', encoding='utf-8') as f:
    skill_content = f.read()

# Update the formula count in the table
old_count_line = f'83首（42类）'
new_count_line = f'{len(all_formulas)}首（{len(set(fm["formula_category"] for fm in all_formulas))}类）'
skill_content = skill_content.replace(old_count_line, new_count_line)

with open(skill_path, 'w', encoding='utf-8') as f:
    f.write(skill_content)

print(f'Updated SKILL.md formula count: {new_count_line}')

# ===== 8. Save new formulas list for reference =====
new_list_path = os.path.join(script_dir, 'assets', 'newly_added_formulas.txt')
with open(new_list_path, 'w', encoding='utf-8') as f:
    f.write(f'Newly added formulas: {len(new_formulas)}\n')
    f.write(f'{"="*60}\n\n')
    for i, fm in enumerate(new_formulas, 1):
        f.write(f'{i:3d}. {fm["name"]}  [{fm["formula_category"]}]  [id={fm["id"]}]\n')

print(f'Saved newly added list to newly_added_formulas.txt')
print(f'\nDone! Total: {len(all_formulas)} formulas ({len(new_formulas)} new)')
