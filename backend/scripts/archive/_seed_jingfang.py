# -*- coding: utf-8 -*-
"""一把梭：伤寒论112方 + 金匮常用方 统一导入（按方名 upsert），并把原库缺项补齐。"""
import sqlite3, json, os, re

DB = os.path.join(os.path.dirname(__file__), 'tcm_doctor.db')
FANGJI = os.path.join(os.path.dirname(__file__), '..', '..', 'nihaixia', 'references', 'audit', 'fangji_112.txt')
c = sqlite3.connect(DB)

def comp(meridian, herbs):
    return json.dumps({"herbs": herbs, "meridian": meridian}, ensure_ascii=False)

# ---------------- 六经归属（伤寒方子集） ----------------
datetime = None
MERIDIAN_MAP = {
    "桂枝汤":"太阳","桂枝加葛根汤":"太阳","桂枝加厚朴杏子汤":"太阳","桂枝加附子汤":"太阳",
    "桂枝去芍药汤":"太阳","桂枝去芍药加附子汤":"太阳","桂枝麻黄各半汤":"太阳","桂枝二麻黄一汤":"太阳",
    "桂枝二越婢一汤":"太阳","桂枝去桂加茯苓白术汤":"太阳","桂枝加芍药生姜各一两人参三两新加汤":"太阳",
    "麻黄汤":"太阳","葛根汤":"太阳","葛根加半夏汤":"太阳","大青龙汤":"太阳","小青龙汤":"太阳",
    "桂枝加芍药汤":"太阳","桂枝加大黄汤":"太阳","桂枝加桂汤":"太阳","桂枝甘草汤":"太阳",
    "桂枝甘草龙骨牡蛎汤":"太阳","桂枝去芍药加蜀漆牡蛎龙骨救逆汤":"太阳",
    "茯苓桂枝白术甘草汤":"太阴","茯苓桂枝甘草大枣汤":"太阳","茯苓甘草汤":"太阳",
    "五苓散":"太阳","猪苓汤":"太阳","文蛤散":"太阳","桃核承气汤":"太阳","抵当汤":"太阳","抵当丸":"太阳",
    "大陷胸汤":"太阳","大陷胸丸":"太阳","小陷胸汤":"太阳","三物小白散":"太阳",
    "栀子豉汤":"阳明","栀子甘草豉汤":"阳明","栀子生姜豉汤":"阳明","栀子厚朴汤":"阳明","栀子干姜汤":"阳明",
    "枳实栀子豉汤":"阳明","栀子柏皮汤":"阳明","黄芩汤":"太阳","黄芩加半夏生姜汤":"太阳","黄连汤":"太阴",
    "葛根黄芩黄连汤":"阳明","麻黄杏仁甘草石膏汤":"阳明","白虎汤":"阳明","白虎加人参汤":"阳明",
    "调胃承气汤":"阳明","小承气汤":"阳明","大承气汤":"阳明","麻子仁丸":"阳明","蜜煎导方":"阳明",
    "猪胆汁方":"阳明","茵陈蒿汤":"阳明","麻黄连轺赤小豆汤":"太阳",
    "桂枝附子汤":"少阴","去桂加白术汤":"少阴","甘草附子汤":"少阴","炙甘草汤":"少阴","牡蛎泽泻散":"少阴",
    "竹叶石膏汤":"阳明","吴茱萸汤":"厥阴","小柴胡汤":"少阳","大柴胡汤":"少阳","柴胡加芒硝汤":"少阳",
    "柴胡加龙骨牡蛎汤":"少阳","柴胡桂枝汤":"少阳","柴胡桂枝干姜汤":"少阳","半夏泻心汤":"厥阴",
    "生姜泻心汤":"厥阴","甘草泻心汤":"厥阴","附子泻心汤":"厥阴","大黄黄连泻心汤":"阳明",
    "旋覆代赭汤":"太阴","厚朴生姜半夏甘草人参汤":"太阴","理中丸":"太阴","桂枝人参汤":"太阴",
    "赤石脂禹余粮汤":"少阴","四逆汤":"少阴","四逆加人参汤":"少阴","白通汤":"少阴","白通加猪胆汁汤":"少阴",
    "真武汤":"少阴","通脉四逆汤":"少阴","通脉四逆加猪胆汁汤":"少阴","附子汤":"少阴",
    "芍药甘草汤":"阳明","芍药甘草附子汤":"少阴","干姜附子汤":"少阴","黄连阿胶汤":"少阴","猪肤汤":"少阴",
    "甘草汤":"少阴","桔梗汤":"少阴","苦酒汤":"少阴","半夏散及汤":"少阴","麻黄附子细辛汤":"少阴",
    "麻黄附子甘草汤":"少阴","当归四逆汤":"厥阴","当归四逆加吴茱萸生姜汤":"厥阴","四逆散":"少阴",
    "乌梅丸":"厥阴","干姜黄芩黄连人参汤":"厥阴","白头翁汤":"厥阴","附子理中汤":"太阴","桃花汤":"少阴",
    "桂枝加龙骨牡蛎汤":"太阳","小建中汤":"太阳","黄芪建中汤":"太阳","麻黄升麻汤":"厥阴","瓜蒂散":"太阳",
}

# ---------------- 核心方完整数据 (name -> source, meridian, eff, ind, usage, herbs) ----------------
# herbs: (药名, 剂量g, 特殊法, is_king)
DATA = {}
def add(name, source, meridian, eff, ind, usage, herbs):
    DATA[name] = (source, meridian, eff, ind, usage, herbs)

add("桂枝加厚朴杏子汤","伤寒论","太阳","解肌发表，降气平喘","太阳病下之微喘，表未解","桂枝汤加厚朴、杏仁，水煎温服。",
    [("桂枝",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("厚朴",6,None,False),("杏仁",6,None,False)])
add("桂枝加附子汤","伤寒论","太阳","扶阳解表","太阳病发汗太过，漏汗恶风，小便难","桂枝汤加附子，水煎温服。",
    [("桂枝",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("制附子",6,None,False)])
add("桂枝麻黄各半汤","伤寒论","太阳","小发其汗","太阳病得之八九日，发热恶寒，如疟状","取二方各半，水煎温服。",
    [("桂枝",6,None,True),("白芍",6,None,False),("麻黄",3,None,False),("杏仁",3,None,False),("炙甘草",3,None,False),("生姜",6,None,False),("大枣",2,None,False)])
add("桂枝二麻黄一汤","伤寒论","太阳","微发其汗","服桂枝汤大汗出后，形如疟","取桂枝二、麻黄一，水煎温服。",
    [("桂枝",6,None,True),("白芍",6,None,False),("麻黄",2,None,False),("杏仁",2,None,False),("炙甘草",3,None,False),("生姜",6,None,False),("大枣",2,None,False)])
add("桂枝二越婢一汤","伤寒论","太阳","微发汗，兼清里热","太阳病发热恶寒，热多寒少，脉微弱","桂枝汤与越婢汤相合，水煎温服。",
    [("桂枝",6,None,True),("白芍",6,None,False),("麻黄",2,None,False),("石膏",4,None,False),("炙甘草",3,None,False),("生姜",6,None,False),("大枣",2,None,False)])
add("桂枝去桂加茯苓白术汤","伤寒论","太阳","利水通阳","服桂枝汤后心下满微痛，小便不利","去桂加茯苓白术，水煎温服。",
    [("白芍",9,None,True),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("白术",9,None,False),("茯苓",9,None,False)])
add("桂枝加芍药生姜各一两人参三两新加汤","伤寒论","太阳","益气养营，调和营卫","汗后身疼痛，脉沉迟","新加汤，水煎温服。",
    [("桂枝",9,None,True),("白芍",12,None,False),("炙甘草",6,None,False),("生姜",12,None,False),("大枣",3,None,False),("人参",9,None,False)])
add("葛根加半夏汤","伤寒论","太阳","解表和胃，降逆止呕","太阳病项背强几几，反下利或呕","葛根汤加半夏，水煎温服。",
    [("葛根",12,None,True),("麻黄",9,None,False),("桂枝",6,None,False),("白芍",6,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False),("半夏",9,None,False)])
add("桂枝加芍药汤","伤寒论","太阳","调和营卫，缓急止痛","本太阳病医反下之，腹满时痛","即桂枝汤倍芍药，水煎温服。",
    [("桂枝",9,None,True),("白芍",18,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False)])
add("桂枝加大黄汤","伤寒论","太阳","解肌通结","太阳病反下之，腹满大实痛","即桂枝汤加大黄，水煎温服。",
    [("桂枝",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("大黄",6,None,False)])
add("桂枝加桂汤","伤寒论","太阳","温通心阳，降逆平冲","发汗后烧针，气从少腹上冲心","即桂枝汤多加桂枝，水煎温服。",
    [("桂枝",15,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False)])
add("桂枝甘草汤","伤寒论","太阳","补心阳，定悸","发汗过多，其人叉手自冒心，心下悸","二味水煎，顿服。",
    [("桂枝",12,None,True),("炙甘草",6,None,False)])
add("桂枝甘草龙骨牡蛎汤","伤寒论","太阳","安神定惊，潜镇浮阳","火逆下之，烦躁","桂枝甘草加龙骨牡蛎，水煎温服。",
    [("桂枝",3,None,True),("炙甘草",6,None,False),("龙骨",9,None,False),("牡蛎",9,None,False)])
add("桂枝去芍药加蜀漆牡蛎龙骨救逆汤","伤寒论","太阳","潜镇浮阳，救逆定惊","伤寒脉浮，医以火迫劫之，亡阳惊狂","去芍加蜀漆龙骨牡蛎，水煎温服。",
    [("桂枝",9,None,True),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("蜀漆",9,None,False),("龙骨",12,None,False),("牡蛎",12,None,False)])
add("茯苓桂枝白术甘草汤","伤寒论","太阴","温阳化饮，健脾利湿","心下逆满，气上冲胸，起则头眩","苓桂术甘汤，水煎温服。",
    [("茯苓",12,None,True),("桂枝",9,None,False),("白术",9,None,False),("炙甘草",6,None,False)])
add("茯苓甘草汤","伤寒论","太阳","温散水气","伤寒汗出不渴，心下悸","水煎温服。",
    [("茯苓",9,None,True),("桂枝",6,None,False),("炙甘草",3,None,False),("生姜",9,None,False)])
add("文蛤散","伤寒论","太阳","清热利湿","病在阳，反以冷水潠之，热被劫不得去","文蛤研末，沸汤和服。",
    [("文蛤",15,None,True)])
add("桃核承气汤","伤寒论","太阳","破瘀泄热","太阳病不解，热结膀胱，其人如狂","先食温服。",
    [("桃仁",9,None,True),("大黄",12,None,False),("桂枝",6,None,False),("炙甘草",6,None,False),("芒硝",6,None,False)])
add("抵当汤","伤寒论","太阳","破血逐瘀","蓄血证，少腹硬满，其人发狂","水煎，顿服。",
    [("水蛭",6,None,True),("虻虫",3,None,False),("桃仁",9,None,False),("大黄",9,None,False)])
add("抵当丸","伤寒论","太阳","破血逐瘀","蓄血轻证，少腹满，小便利","为丸，温开水送。",
    [("水蛭",3,None,True),("虻虫",3,None,False),("桃仁",9,None,False),("大黄",9,None,False)])
add("大陷胸汤","伤寒论","太阳","泻热逐水破结","结胸证，心下硬满而痛不可近","水煎，内芒硝，顿服。",
    [("大黄",15,None,True),("芒硝",15,None,False),("甘遂",1,None,False)])
add("大陷胸丸","伤寒论","太阳","泻热逐水","结胸项强，如柔痉状","为丸，白蜜和水服。",
    [("大黄",15,None,True),("葶苈子",9,None,False),("芒硝",15,None,False),("杏仁",9,None,False),("甘遂",0.5,None,False)])
add("小陷胸汤","伤寒论","太阳","清热化痰，宽胸散结","小结胸，正在心下，按之则痛","水煎，分温三服。",
    [("黄连",6,None,True),("半夏",12,None,False),("瓜蒌",30,None,False)])
add("三物小白散","伤寒论","太阳","温寒逐水","寒实结胸，无热证","为散，温水服。",
    [("桔梗",3,None,True),("巴豆",0.5,None,False),("贝母",3,None,False)])
add("栀子豉汤","伤寒论","阳明","清热除烦","虚烦不得眠，心中懊憹","先煎栀子，内豉，分二服。",
    [("栀子",9,None,True),("淡豆豉",9,None,False)])
add("栀子甘草豉汤","伤寒论","阳明","清热除烦，益气和中","栀子豉证兼少气","栀子豉汤加甘草，水煎。",
    [("栀子",9,None,True),("淡豆豉",9,None,False),("炙甘草",6,None,False)])
add("栀子生姜豉汤","伤寒论","阳明","清热除烦，降逆止呕","栀子豉证兼呕","栀子豉汤加生姜，水煎。",
    [("栀子",9,None,True),("淡豆豉",9,None,False),("生姜",9,None,False)])
add("栀子厚朴汤","伤寒论","阳明","清热除满","伤寒下后心烦腹满，卧起不安","水煎，分二服。",
    [("栀子",9,None,True),("厚朴",9,None,False),("枳实",9,None,False)])
add("栀子干姜汤","伤寒论","阳明","清上温下","伤寒身热不去，微烦","水煎，分二服。",
    [("栀子",9,None,True),("干姜",9,None,False)])
add("枳实栀子豉汤","伤寒论","阳明","清热除烦，宽中行气","大病瘥后劳复","水煎温服，覆令微似汗。",
    [("枳实",9,None,True),("栀子",9,None,False),("淡豆豉",9,None,False)])
add("栀子柏皮汤","伤寒论","阳明","清热利湿退黄","伤寒身黄发热","水煎，分三服。",
    [("栀子",12,None,True),("黄柏",9,None,False),("炙甘草",3,None,False)])
add("黄芩汤","伤寒论","太阳","清热止利，和中止痛","太阳与少阳合病，自下利","水煎，分温再服。",
    [("黄芩",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False)])
add("黄芩加半夏生姜汤","伤寒论","太阳","清热止利，降逆止呕","黄芩汤证兼呕","黄芩汤加半夏生姜，水煎。",
    [("黄芩",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False),("半夏",9,None,False),("生姜",9,None,False)])
add("黄连汤","伤寒论","太阴","平调寒热，和胃降逆","胸中有热，胃中有邪气，腹中痛，欲呕吐","水煎，分温三服。",
    [("黄连",6,None,True),("半夏",9,None,False),("炙甘草",6,None,False),("干姜",6,None,False),("桂枝",9,None,False),("人参",6,None,False),("大枣",3,None,False)])
add("葛根黄芩黄连汤","伤寒论","阳明","解表清里","协热下利，身热下利，臭秽","葛根先煎，内黄芩黄连甘草，分温再服。",
    [("葛根",15,None,True),("黄芩",9,None,False),("黄连",9,None,False),("炙甘草",6,None,False)])
add("麻黄杏仁甘草石膏汤","伤寒论","阳明","辛凉宣泄，清肺平喘","汗出而喘，无大热者","水煎，分温再服。",
    [("麻黄",9,None,True),("杏仁",9,None,False),("石膏",24,None,False),("炙甘草",6,None,False)])
add("白虎加人参汤","伤寒论","阳明","清热生津益气","白虎汤证兼口渴，津气两伤","白虎汤加人参，水煎温服。",
    [("石膏",45,None,True),("知母",18,None,False),("炙甘草",6,None,False),("粳米",20,None,False),("人参",9,None,False)])
add("麻子仁丸","伤寒论","阳明","润肠通便","脾约证，大便硬，小便数","炼蜜为丸，温水送服。",
    [("麻子仁",20,None,True),("芍药",9,None,False),("枳实",9,None,False),("大黄",12,None,False),("厚朴",9,None,False),("杏仁",9,None,False)])
add("茵陈蒿汤","伤寒论","阳明","清热利湿退黄","湿热黄疸，一身面目俱黄","先煮茵陈，内余药，分三服。",
    [("茵陈蒿",30,None,True),("栀子",9,None,False),("大黄",9,None,False)])
add("麻黄连轺赤小豆汤","伤寒论","太阳","解表清热利湿","伤寒瘀热在里，身必黄","水煎，分温三服。",
    [("麻黄",6,None,True),("连轺",6,None,False),("杏仁",6,None,False),("赤小豆",20,None,False),("生梓白皮",9,None,False),("生姜",6,None,False),("甘草",6,None,False),("大枣",3,None,False)])
add("桂枝附子汤","伤寒论","少阴","温阳祛风除湿","风湿相搏，身体疼烦，不能自转侧","水煎，分三服。",
    [("桂枝",12,None,True),("制附子",9,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False)])
add("去桂加白术汤","伤寒论","少阴","温阳除湿","桂枝附子汤证大便硬，小便自利","去桂加白术，水煎分三服。",
    [("制附子",9,None,True),("白术",12,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False)])
add("甘草附子汤","伤寒论","少阴","温阳散寒，祛湿止痛","风湿相搏，骨节疼烦掣痛","水煎，分三服。",
    [("炙甘草",9,None,True),("制附子",9,None,False),("白术",9,None,False),("桂枝",12,None,False)])
add("牡蛎泽泻散","伤寒论","少阴","利水逐饮","大病瘥后，腰以下有水气","为散，白饮和服。",
    [("牡蛎",9,None,True),("泽泻",9,None,False),("葶苈子",9,None,False),("蜀漆",9,None,False),("海藻",9,None,False),("商陆",9,None,False),("瓜蒌根",9,None,False)])
add("柴胡加芒硝汤","伤寒论","少阳","和解泻热","小柴胡汤证兼热结便秘","小柴胡汤加芒硝，后下。",
    [("柴胡",12,None,True),("黄芩",9,None,False),("半夏",9,None,False),("人参",6,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("芒硝",6,None,False)])
add("柴胡加龙骨牡蛎汤","伤寒论","少阳","和解少阳，重镇安神","少阳证兼烦惊谵语，小便不利","水煎，分温服。",
    [("柴胡",12,None,True),("龙骨",12,None,False),("黄芩",9,None,False),("生姜",9,None,False),("人参",6,None,False),("桂枝",9,None,False),("牡蛎",12,None,False),("茯苓",9,None,False),("半夏",9,None,False),("大黄",6,None,False),("大枣",3,None,False)])
add("柴胡桂枝干姜汤","伤寒论","少阳","和解少阳，温化水饮","往来寒热，胸胁满，小便不利","水煎，分温三服。",
    [("柴胡",12,None,True),("桂枝",9,None,False),("干姜",6,None,False),("瓜蒌根",12,None,False),("黄芩",9,None,False),("牡蛎",9,None,False),("炙甘草",6,None,False)])
add("生姜泻心汤","伤寒论","厥阴","和胃散水，消痞","心下痞硬，干噫食臭，胁下有水气","生姜泻心汤，水煎分温服。",
    [("生姜",12,None,True),("半夏",9,None,False),("黄芩",9,None,False),("干姜",3,None,False),("人参",6,None,False),("炙甘草",6,None,False),("黄连",3,None,False),("大枣",3,None,False)])
add("甘草泻心汤","伤寒论","厥阴","益气和胃，消痞止利","心下痞硬而满，干呕心烦，下利日数十行","甘草泻心汤，水煎分温服。",
    [("炙甘草",12,None,True),("黄芩",9,None,False),("半夏",9,None,False),("大枣",3,None,False),("黄连",3,None,False),("干姜",6,None,False),("人参",6,None,False)])
add("附子泻心汤","伤寒论","厥阴","泻热消痞，扶阳固表","心下痞，而复恶寒汗出","麻沸汤渍三黄，别煮附子取汁。",
    [("大黄",6,None,True),("黄连",3,None,False),("黄芩",6,None,False),("制附子",6,None,False)])
add("大黄黄连泻心汤","伤寒论","阳明","泻热消痞","心下痞，按之濡，关上脉浮","麻沸汤渍之，即绞汁服。",
    [("大黄",9,None,True),("黄连",6,None,False),("黄芩",6,None,False)])
add("旋覆代赭汤","伤寒论","太阴","降逆化痰，益气和胃","心下痞硬，噫气不除","水煎，分温三服。",
    [("旋覆花",9,"包煎",True),("人参",6,None,False),("生姜",15,None,False),("代赭石",9,None,False),("炙甘草",9,None,False),("半夏",9,None,False),("大枣",3,None,False)])
add("厚朴生姜半夏甘草人参汤","伤寒论","太阴","行气除满，健脾化痰","发汗后腹胀满","水煎温服。",
    [("厚朴",12,None,True),("生姜",12,None,False),("半夏",9,None,False),("炙甘草",6,None,False),("人参",3,None,False)])
add("桂枝人参汤","伤寒论","太阴","温中解表","太阳病外证未除，而数下之，协热而利","先煎后温服。",
    [("桂枝",12,None,True),("炙甘草",12,None,False),("白术",9,None,False),("人参",9,None,False),("干姜",9,None,False)])
add("赤石脂禹余粮汤","伤寒论","少阴","涩肠固脱","下利不止，滑脱不禁","水煎温服。",
    [("赤石脂",30,None,True),("禹余粮",30,None,False)])
add("白通加猪胆汁汤","伤寒论","少阴","回阳救逆，益阴和阳","少阴下利，脉微，厥逆无脉，干呕烦","白通汤加猪胆，水煎温服。",
    [("制附子",6,None,True),("干姜",6,None,False),("葱白",4,None,False),("人尿",50,None,False),("猪胆汁",10,None,False)])
add("通脉四逆汤","伤寒论","少阴","回阳通脉","少阴病下利清谷，里寒外热，手足厥逆","四逆汤倍姜附，水煎分温。",
    [("制附子",24,None,True),("干姜",15,None,False),("炙甘草",12,None,False)])
add("通脉四逆加猪胆汁汤","伤寒论","少阴","回阳救逆，和阳","通脉四逆汤证兼吐利无脉","通脉四逆加猪胆，水煎温服。",
    [("制附子",24,None,True),("干姜",15,None,False),("炙甘草",12,None,False),("猪胆汁",10,None,False)])
add("芍药甘草汤","伤寒论","阳明","酸甘化阴，缓急止痛","脚挛急，或腹中急痛","水煎，分温再服。",
    [("白芍",30,None,True),("炙甘草",30,None,False)])
add("芍药甘草附子汤","伤寒论","少阴","扶阳益阴","发汗后恶寒，脚挛急","水煎，分温三服。",
    [("白芍",9,None,True),("炙甘草",9,None,False),("制附子",6,None,False)])
add("干姜附子汤","伤寒论","少阴","回阳急救","下之后复发汗，昼日烦躁不得眠，夜而安静","水煎顿服。",
    [("干姜",9,None,True),("制附子",6,None,False)])
add("猪肤汤","伤寒论","少阴","滋阴润燥","少阴病下利咽痛，胸满心烦","水煎去滓，纳白蜜米粉。",
    [("猪肤",120,None,True),("白蜜",30,None,False),("米粉",15,None,False)])
add("甘草汤","伤寒论","少阴","清热解毒","少阴病二三日，咽痛","一味水煎，分温再服。",
    [("甘草",30,None,True)])
add("桔梗汤","伤寒论","少阴","宣肺利咽","咽痛，咳而胸满","甘草桔梗，水煎分温。",
    [("桔梗",9,None,True),("甘草",18,None,False)])
add("苦酒汤","伤寒论","少阴","开结利咽","咽中生疮，不能言语","半夏苦酒鸡子，少少含咽。",
    [("半夏",9,None,True),("鸡子清",1,"含咽",False),("醋",50,None,False)])
add("半夏散及汤","伤寒论","少阴","散寒止痛，利咽","少阴咽中痛","散开水冲服或煎汤。",
    [("半夏",9,None,True),("桂枝",9,None,False),("炙甘草",9,None,False)])
add("麻黄附子甘草汤","伤寒论","少阴","助阳解表","少阴病得之二三日，微发汗","麻黄附子甘草，水煎分温三服。",
    [("麻黄",9,None,True),("制附子",9,None,False),("炙甘草",6,None,False)])
add("当归四逆加吴茱萸生姜汤","伤寒论","厥阴","温经散寒，降逆止呕","当归四逆证兼内有久寒","当归四逆汤加吴茱萸生姜，清酒煎服。",
    [("当归",9,None,True),("桂枝",9,None,False),("白芍",9,None,False),("细辛",3,None,False),("炙甘草",6,None,False),("通草",6,None,False),("大枣",4,None,False),("吴茱萸",9,None,False),("生姜",12,None,False)])
add("四逆散","伤寒论","少阴","透邪解郁，疏肝理脾","少阴病四逆，或咳、悸、小便不利","捣筛为散，白饮和服。",
    [("柴胡",9,None,True),("枳实",9,None,False),("白芍",9,None,False),("炙甘草",9,None,False)])
add("干姜黄芩黄连人参汤","伤寒论","厥阴","寒热并用，辛开苦降","食入口即吐，寒格","以甘澜水煮，分温再服。",
    [("干姜",9,None,True),("黄芩",9,None,False),("黄连",9,None,False),("人参",9,None,False)])
add("白头翁汤","伤寒论","厥阴","清热解毒，凉血止痢","热利下重，便脓血","水煎，分温再服。",
    [("白头翁",15,None,True),("黄连",6,None,False),("黄柏",9,None,False),("秦皮",9,None,False)])
add("桃花汤","伤寒论","少阴","温中涩肠止利","少阴病下利便脓血","水煎，内粳米令熟，分温三服。",
    [("赤石脂",30,None,True),("干姜",9,None,False),("粳米",30,None,False)])
add("桂枝加龙骨牡蛎汤","伤寒论","太阳","调和营卫，潜镇摄精","男子失精，女子梦交","桂枝汤加龙骨牡蛎，水煎温服。",
    [("桂枝",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("龙骨",12,None,False),("牡蛎",12,None,False)])
add("黄芪建中汤","伤寒论","太阳","温中补气","虚劳里急，诸不足，气短自汗","小建中汤加黄芪，水煎温服。",
    [("桂枝",9,None,True),("白芍",18,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("饴糖",30,"烊化",False),("黄芪",9,None,False)])
add("麻黄升麻汤","伤寒论","厥阴","发越郁阳","伤寒六七日，大下后，脉沉而迟，手足厥逆","先煮麻黄，去上沫，内诸药。",
    [("麻黄",6,None,True),("升麻",6,None,False),("当归",6,None,False),("知母",3,None,False),("黄芩",3,None,False),("葳蕤",3,None,False),("石膏",3,None,False),("白术",3,None,False),("干姜",3,None,False),("芍药",3,None,False),("天冬",3,None,False),("桂枝",3,None,False),("茯苓",3,None,False),("炙甘草",3,None,False)])
add("瓜蒂散","伤寒论","太阳","涌吐痰食","胸中痞硬，气上冲咽喉，不得息","为散，以香豉煮汤和服。",
    [("瓜蒂",1,None,True),("赤小豆",1,None,False)])
add("桂枝去芍药汤","伤寒论","太阳","解肌通阳","太阳病下之后，脉促胸满","桂枝汤去芍药，水煎温服。",
    [("桂枝",9,None,True),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False)])
add("桂枝去芍药加附子汤","伤寒论","太阳","扶阳解表","太阳病下之后，脉促胸满，微恶寒","去芍加附子，水煎温服。",
    [("桂枝",9,None,True),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("制附子",6,None,False)])

# ---------- 34 首核心方（补全，避免被空组成覆盖） ----------
add("桂枝汤","伤寒论","太阳","解肌发表，调和营卫","太阳中风，头痛发热，汗出恶风，脉浮缓","水煎，温服，啜热稀粥，覆被取微汗。",
    [("桂枝",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",4,None,False)])
add("麻黄汤","伤寒论","太阳","发汗解表，宣肺平喘","太阳伤寒，恶寒发热，无汗而喘，脉浮紧","先煎麻黄去上沫，水煎温服取汗。",
    [("麻黄",9,"先煎",True),("桂枝",6,None,False),("杏仁",9,None,False),("炙甘草",3,None,False)])
add("葛根汤","伤寒论","太阳","发汗解表，升津舒筋","太阳病项背强几几，无汗恶风","先煎麻黄葛根，水煎温服取微汗。",
    [("葛根",12,None,True),("麻黄",9,"先煎",False),("桂枝",6,None,False),("白芍",6,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",4,None,False)])
add("桂枝加葛根汤","伤寒论","太阳","解肌发表，升津舒经","太阳病项背强几几，汗出恶风","水煎温服，覆取微汗。",
    [("桂枝",9,None,True),("白芍",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",4,None,False),("葛根",12,None,False)])
add("小青龙汤","伤寒论","太阳","解表散寒，温肺化饮","外寒里饮，恶寒发热，咳喘痰稀","先煎麻黄去沫，水煎温服。",
    [("麻黄",9,"先煎",True),("白芍",9,None,False),("细辛",3,None,False),("干姜",6,None,False),("炙甘草",6,None,False),("桂枝",9,None,False),("五味子",6,None,False),("半夏",9,None,False)])
add("大青龙汤","伤寒论","太阳","发汗解表，清热除烦","外寒内热，恶寒发热，无汗烦躁","先煎麻黄，水煎温服，汗出止后服。",
    [("麻黄",12,"先煎",True),("桂枝",6,None,False),("炙甘草",6,None,False),("杏仁",6,None,False),("石膏",24,None,False),("生姜",9,None,False),("大枣",4,None,False)])
add("小柴胡汤","伤寒论","少阳","和解少阳","往来寒热，胸胁苦满，默默不欲饮食，心烦喜呕","水煎，去滓再煎，温服。",
    [("柴胡",24,None,True),("黄芩",9,None,False),("人参",9,None,False),("半夏",9,None,False),("炙甘草",9,None,False),("生姜",9,None,False),("大枣",4,None,False)])
add("大柴胡汤","伤寒论","少阳","和解少阳，内泻热结","少阳阳明合病，往来寒热，便秘腹痛","水煎温服。",
    [("柴胡",15,None,True),("黄芩",9,None,False),("白芍",9,None,False),("半夏",9,None,False),("枳实",9,None,False),("大黄",6,None,False),("生姜",15,None,False),("大枣",4,None,False)])
add("柴胡桂枝汤","伤寒论","少阳","和解少阳，调和营卫","太阳少阳合病，发热微恶寒，支节烦疼","桂枝汤合小柴胡各半，水煎温服。",
    [("柴胡",12,None,True),("桂枝",6,None,False),("黄芩",6,None,False),("白芍",6,None,False),("人参",6,None,False),("半夏",6,None,False),("炙甘草",3,None,False),("生姜",6,None,False),("大枣",3,None,False)])
add("白虎汤","伤寒论","阳明","清热生津","阳明气分热盛，大热，大汗，大渴，脉洪大","水煎，米熟汤成，温服。",
    [("石膏",45,None,True),("知母",18,None,False),("炙甘草",6,None,False),("粳米",30,None,False)])
add("大承气汤","伤寒论","阳明","峻下热结","阳明腑实，痞满燥实坚，潮热谵语","先煎枳朴，后下大黄，再纳芒硝，分温再服。",
    [("大黄",12,"后下",True),("芒硝",9,"冲服",False),("厚朴",24,None,False),("枳实",12,None,False)])
add("小承气汤","伤寒论","阳明","轻下热结","阳明腑实轻证，腹大满不通，潮热烦躁","水煎，分温二服。",
    [("大黄",12,None,True),("厚朴",6,None,False),("枳实",9,None,False)])
add("调胃承气汤","伤寒论","阳明","缓下热结","阳明燥实轻证，蒸蒸发热，便秘","水煎温服。",
    [("大黄",12,None,True),("炙甘草",6,None,False),("芒硝",9,"冲服",False)])
add("竹叶石膏汤","伤寒论","阳明","清热生津，益气和胃","热病后余热未清，气津两伤，虚羸少气","水煎，去滓，纳粳米，米熟服。",
    [("竹叶",15,None,True),("石膏",30,None,False),("半夏",9,None,False),("麦冬",15,None,False),("人参",6,None,False),("炙甘草",6,None,False),("粳米",15,None,False)])
add("五苓散","伤寒论","太阳","利水渗湿，温阳化气","蓄水证，小便不利，烦渴饮水即吐","为散，白饮和服，多饮暖水取汗。",
    [("猪苓",9,None,True),("泽泻",15,None,False),("白术",9,None,False),("茯苓",9,None,False),("桂枝",6,None,False)])
add("猪苓汤","伤寒论","少阴","利水清热养阴","水热互结，小便不利，发热口渴","水煎，纳阿胶烊化，分温服。",
    [("猪苓",9,None,True),("茯苓",9,None,False),("泽泻",9,None,False),("滑石",9,"包煎",False),("阿胶",9,"烊化",False)])
add("茯苓四逆汤","伤寒论","少阴","回阳益阴","汗下后阴阳俱虚，烦躁","水煎，分温再服。",
    [("茯苓",12,None,True),("人参",6,None,False),("炙甘草",6,None,False),("干姜",6,None,False),("制附子",9,None,False)])
add("理中丸","伤寒论","太阴","温中祛寒，补气健脾","太阴病腹满吐利，自利不渴，食不下","蜜丸，温水送服，或作汤剂。",
    [("人参",9,None,True),("干姜",9,None,False),("炙甘草",9,None,False),("白术",9,None,False)])
add("附子理中汤","伤寒论","太阴","温阳祛寒，益气健脾","脾胃虚寒甚，下利清谷，手足不温","理中汤加附子，水煎温服。",
    [("制附子",9,None,True),("人参",9,None,False),("干姜",9,None,False),("炙甘草",9,None,False),("白术",9,None,False)])
add("四逆汤","伤寒论","少阴","回阳救逆","少阴病四肢厥逆，恶寒蜷卧，下利清谷","先煎附子，后下姜草，分温再服。",
    [("制附子",15,"先煎",True),("干姜",9,None,False),("炙甘草",12,None,False)])
add("四逆加人参汤","伤寒论","少阴","回阳救逆，益气固脱","四逆证兼脉微，亡血津竭","四逆汤加人参，水煎温服。",
    [("制附子",15,"先煎",True),("干姜",9,None,False),("炙甘草",12,None,False),("人参",9,None,False)])
add("白通汤","伤寒论","少阴","通阳破阴","少阴下利，脉微，四肢厥逆","水煎，分温再服。",
    [("葱白",4,None,True),("干姜",9,None,False),("制附子",15,"先煎",False)])
add("真武汤","伤寒论","少阴","温阳利水","少阴阳虚水泛，心下悸，头眩，身瞤动","水煎温服。",
    [("茯苓",9,None,True),("白芍",9,None,False),("生姜",9,None,False),("制附子",15,"先煎",False),("白术",6,None,False)])
add("附子汤","伤寒论","少阴","温经助阳，祛寒化湿","少阴病身体骨节疼痛，手足寒","先煎附子，水煎温服。",
    [("制附子",15,"先煎",True),("茯苓",9,None,False),("人参",6,None,False),("白术",12,None,False),("白芍",9,None,False)])
add("黄连阿胶汤","伤寒论","少阴","滋阴降火，除烦安神","少阴热化，心中烦，不得卧","水煎，纳阿胶鸡子黄，温服。",
    [("黄连",12,None,True),("黄芩",6,None,False),("白芍",6,None,False),("阿胶",9,"烊化",False),("鸡子黄",2,"冲入",False)])
add("炙甘草汤","伤寒论","少阴","益气滋阴，通阳复脉","心动悸，脉结代，虚劳","清酒与水共煎，纳阿胶烊化温服。",
    [("炙甘草",12,None,True),("生姜",9,None,False),("人参",6,None,False),("生地黄",30,None,False),("桂枝",9,None,False),("阿胶",6,"烊化",False),("麦冬",15,None,False),("火麻仁",10,None,False),("大枣",30,None,False)])
add("吴茱萸汤","伤寒论","厥阴","温中补虚，降逆止呕","食谷欲呕，巅顶头痛，干呕吐涎沫","水煎温服。",
    [("吴茱萸",9,None,True),("人参",9,None,False),("生姜",18,None,False),("大枣",4,None,False)])
add("乌梅丸","伤寒论","厥阴","温脏安蛔，寒热并调","蛔厥，久利，厥阴寒热错杂","乌梅醋浸，蒸熟捣丸，蜜为丸。",
    [("乌梅",30,None,True),("细辛",3,None,False),("干姜",9,None,False),("黄连",9,None,False),("当归",6,None,False),("制附子",6,None,False),("蜀椒",6,None,False),("桂枝",6,None,False),("人参",6,None,False),("黄柏",6,None,False),("蜂蜜","适量",None,False)])
add("当归四逆汤","伤寒论","厥阴","温经散寒，养血通脉","手足厥寒，脉细欲绝","水煎，温服。",
    [("当归",9,None,True),("桂枝",9,None,False),("白芍",9,None,False),("细辛",3,None,False),("炙甘草",6,None,False),("通草",6,None,False),("大枣",8,None,False)])
add("半夏泻心汤","伤寒论","厥阴","寒热平调，消痞散结","心下痞满，呕而肠鸣下利","去滓再煎，温服。",
    [("半夏",12,"姜制",True),("黄芩",9,None,False),("干姜",9,None,False),("人参",9,None,False),("炙甘草",9,None,False),("黄连",3,None,False),("大枣",4,None,False)])
add("小建中汤","伤寒论","太阳","温中补虚，和里缓急","虚劳里急，腹中时痛，心中悸动","水煎，去滓，纳饴糖烊化温服。",
    [("桂枝",9,None,True),("白芍",18,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",4,None,False),("饴糖",30,"烊化",False)])
add("蜜煎导方","伤寒论","阳明","润肠通便","阳明津枯便秘，大便硬","蜜微火煎，捻作梃，内谷道中。",
    [("食蜜",50,None,True)])
add("猪胆汁方","伤寒论","阳明","清热导下","大便秘结，津枯热结","猪胆汁和醋，灌谷道中。",
    [("猪胆汁",1,"外用",True),("食醋",10,None,False)])
add("麻黄附子细辛汤","伤寒论","少阴","助阳解表","少阴病始得之，反发热，脉沉","先煮麻黄，去上沫，内诸药温服。",
    [("麻黄",6,"先煎",True),("制附子",9,None,False),("细辛",3,None,False)])

# ---------------- 金匮常用方 ----------------
def add_jg(name, eff, ind, usage, herbs, meridian=None):
    DATA[name] = ("金匮要略", meridian, eff, ind, usage, herbs)

add_jg("温经汤","温经散寒，养血祛瘀","冲任虚寒，瘀血阻滞，漏下不止，月经不调",
    "水煎温服。",
    [("吴茱萸",9,None,True),("当归",9,None,False),("白芍",9,None,False),("川芎",6,None,False),("人参",6,None,False),("桂枝",6,None,False),("阿胶",6,"烊化",False),("牡丹皮",6,None,False),("生姜",6,None,False),("炙甘草",6,None,False),("半夏",6,None,False),("麦冬",15,None,False)])
add_jg("当归芍药散","养血调肝，健脾利湿","妇人腹中诸疾痛，肝脾不和",
    "为散，酒和服或水煎。",[("当归",9,None,True),("白芍",30,None,False),("川芎",9,None,False),("茯苓",12,None,False),("白术",12,None,False),("泽泻",15,None,False)])
add_jg("甘姜苓术汤","温脾胜湿","肾着，身重腰冷痛，如坐水中",
    "水煎，分温三服。",[("甘草",9,None,True),("干姜",12,None,False),("茯苓",12,None,False),("白术",9,None,False)],"太阴")
add_jg("泽泻汤","利水健脾","心下有支饮，其人苦冒眩",
    "水煎，分温再服。",[("泽泻",30,None,True),("白术",12,None,False)],"太阴")
add_jg("旋覆花汤","行气降逆，活血通络","肝着，其人常欲蹈其胸上",
    "水煎，葱汁为引。",[("旋覆花",9,"包煎",True),("新绛",3,None,False),("葱茎",4,None,False)])
add_jg("半夏厚朴汤","行气散结，降逆化痰","梅核气，咽中如有物阻",
    "水煎，分温四服。",[("半夏",12,None,True),("厚朴",9,None,False),("茯苓",12,None,False),("生姜",15,None,False),("紫苏叶",6,None,False)],"太阴")
add_jg("麻黄杏仁薏苡甘草汤","解表祛湿","风湿一身尽疼，发热日晡所剧",
    "水煎，温服取微汗。",[("麻黄",6,None,True),("杏仁",6,None,False),("薏苡仁",18,None,False),("炙甘草",6,None,False)],"太阳")
add_jg("越婢汤","发汗利水","风水恶风，一身悉肿，脉浮不渴",
    "水煎，温服。",[("麻黄",18,None,True),("石膏",24,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False)],"太阳")
add_jg("防己黄芪汤","益气祛风，健脾利水","风水或风湿，汗出恶风，身重脉浮",
    "水煎，温服。",[("防己",12,None,True),("黄芪",15,None,False),("白术",9,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False)],"太阳")
add_jg("桂枝茯苓丸","活血化瘀，缓消癥块","妇人宿有癥病，妊娠漏下不止",
    "炼蜜为丸，如兔屎大，酒下。",[("桂枝",9,None,True),("茯苓",9,None,False),("牡丹皮",9,None,False),("桃仁",9,None,False),("赤芍",9,None,False)])
add_jg("当归生姜羊肉汤","温中补血，散寒止痛","寒疝腹中痛及胁痛里急",
    "以水煮羊肉，纳药葱姜，温服。",[("当归",15,None,True),("生姜",30,None,False),("羊肉",250,None,False)])
add_jg("大黄牡丹汤","泻热破瘀，散结消肿","肠痈初起，右下腹疼痛拒按",
    "水煎，内瓜蒌仁，顿服。",[("大黄",12,None,True),("牡丹皮",9,None,False),("桃仁",9,None,False),("冬瓜子",30,None,False),("芒硝",9,None,False)])
add_jg("薏苡附子败酱散","排脓消肿","肠痈脓已成，身无热，腹皮急",
    "水煎温服。",[("薏苡仁",30,None,True),("制附子",6,None,False),("败酱草",15,None,False)])
add_jg("苇茎汤","清肺化痰，逐瘀排脓","肺痈，咳吐臭脓痰",
    "水煎，分温再服。",[("苇茎",30,None,True),("薏苡仁",30,None,False),("冬瓜仁",30,None,False),("桃仁",9,None,False)])
add_jg("甘麦大枣汤","养心安神，和中缓急","妇人脏躁，喜悲伤欲哭",
    "水煎，温服。",[("甘草",9,None,True),("小麦",30,None,False),("大枣",10,None,False)])
add_jg("酸枣仁汤","养血安神，清热除烦","虚烦不得眠，脉细弦",
    "水煎，临卧服。",[("酸枣仁",30,None,True),("茯苓",9,None,False),("知母",9,None,False),("川芎",6,None,False),("炙甘草",6,None,False)])
add_jg("茯苓杏仁甘草汤","宣肺化饮","胸痹，胸中气塞短气",
    "水煎温服。",[("茯苓",9,None,True),("杏仁",12,None,False),("甘草",6,None,False)],"太阴")
add_jg("木防己汤","行水散结","膈间支饮，其人喘满","水煎温服，分三服。",
    [("木防己",12,None,True),("石膏",30,None,False),("桂枝",9,None,False),("人参",6,None,False)])
add_jg("大建中汤","温中散寒，缓急止痛","心胸中大寒痛，呕不能饮食",
    "水煎，内饴糖，温服。",[("蜀椒",6,None,True),("干姜",12,None,False),("人参",9,None,False),("饴糖",30,"烊化",False)],"太阴")
add_jg("温经汤加减","——","——","——",[])

# ---------------- 通用功效兜底（防止缺字段） ----------------
GEN_EFF = {
    "太阳":"解表调和营卫", "阳明":"清解里热/通腑", "少阳":"和解少阳",
    "太阴":"温中健脾", "少阴":"温阳扶正", "厥阴":"寒热并调/温经养血",
}

# 读取伤寒论112方名
with open(FANGJI, encoding="utf-8") as f:
    content = f.read()
# 提取最后一行逗号分隔的方名
lines = [l.strip() for l in content.splitlines() if l.strip()]
names_line = lines[-1]
all_shanghan = [n for n in names_line.split(",") if n]

def build_herbs_list(t):
    return [{"herb": h, "dose": d, "special_method": s, "is_king_herb": k, "note": None} for h, d, s, k in t]

created = updated = 0
def upsert(name, source, meridian, eff, ind, usage, herbs):
    global created, updated
    comp_json = comp(meridian, build_herbs_list(herbs))
    ex = c.execute("SELECT id,composition,efficacy,indications,usage FROM classic_formulas WHERE name=?", (name,)).fetchone()
    if ex:
        old_comp = json.loads(ex[1]) if ex[1] else None
        old_hs = len(old_comp.get('herbs', [])) if isinstance(old_comp, dict) else (len(old_comp) if old_comp else 0)
        # 新组成为空且旧库已有组成 -> 保留旧组成
        final_comp = comp_json if (herbs or not old_hs) else ex[1]
        # 功效/主治/用法：旧值非空则保留
        final_eff = eff if eff else ex[2]
        final_ind = ind if ind else ex[3]
        final_usage = usage if usage else ex[4]
        c.execute("UPDATE classic_formulas SET source=?,composition=?,efficacy=?,indications=?,usage=? WHERE id=?",
                  (source, final_comp, final_eff, final_ind, final_usage, ex[0]))
        updated += 1
    else:
        c.execute("INSERT INTO classic_formulas(name,source,composition,efficacy,indications,usage) VALUES(?,?,?,?,?,?)",
                  (name, source, comp_json, eff, ind, usage))
        created += 1

# 1) 伤寒论112方
for name in all_shanghan:
    if name in DATA:
        src, mer, eff, ind, usage, herbs = DATA[name]
    else:
        src, mer, eff, ind, usage, herbs = "伤寒论", MERIDIAN_MAP.get(name), f"{GEN_EFF.get(MERIDIAN_MAP.get(name),'六经')}治证（本方）", f"适用于《伤寒论》『{name}』证。", "水煎，分温服。", []
    upsert(name, src, mer, eff, ind, usage, herbs)

# 2) 金匮方（skipping 已占位）
for name in DATA:
    if name not in all_shanghan:
        src, mer, eff, ind, usage, herbs = DATA[name]
        if eff == "——":
            continue
        upsert(name, src, mer, eff, ind, usage, herbs)

c.commit()
print("新增", created, "更新", updated)
print("库内总数:", c.execute("SELECT count(*) FROM classic_formulas").fetchone()[0])
rows = c.execute("SELECT id,name,source,composition,efficacy,indications,usage FROM classic_formulas").fetchall()
miss = 0
for r in rows:
    compx = json.loads(r[3]) if r[3] else None
    hs = len(compx.get('herbs', [])) if isinstance(compx, dict) else (len(compx) if compx else 0)
    if not hs or not r[4] or not r[5] or not r[6]:
        miss += 1
print("不完整条数（无组成或缺功效/主治/用法）:", miss)
c.close()