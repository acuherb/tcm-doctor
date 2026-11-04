import sqlite3, json, os
DB = os.path.join(os.path.dirname(__file__), 'tcm_doctor.db')
c = sqlite3.connect(DB)
data=[
("葛根汤","太阳","伤寒论","解肌发表，升津舒筋","太阳病项背强几几，无汗恶风；下利","水煎温服，取微汗。",
 [("葛根",12,None,True),("麻黄",9,None,False),("桂枝",6,None,False),("白芍",6,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False)]),
("桂枝加葛根汤","太阳","伤寒论","解肌发表，升津舒经","太阳病项背强几几，反汗出恶风","水煎，温覆取微汗。",
 [("桂枝",9,None,True),("白芍",9,None,False),("葛根",12,None,False),("生姜",9,None,False),("炙甘草",6,None,False),("大枣",3,None,False)]),
("小青龙汤","太阳","伤寒论","解表散寒，温肺化饮","外寒内饮，咳喘痰稀，恶寒发热无汗","水煎，分温三服。",
 [("麻黄",9,None,True),("白芍",9,None,False),("细辛",3,None,False),("干姜",9,None,False),("炙甘草",9,None,False),("桂枝",9,None,False),("五味子",9,None,False),("半夏",9,None,False)]),
("大青龙汤","太阳","伤寒论","发汗解表，清热除烦","外寒里热，发热恶寒身痛，烦躁无汗","水煎温服，取微似汗，汗出停服。",
 [("麻黄",18,None,True),("桂枝",6,None,False),("炙甘草",6,None,False),("杏仁",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("石膏",18,None,False)]),
("小承气汤","阳明","伤寒论","轻下热结","阳明腑实轻证，潮热大便硬，腹大满不通","水煎，分温二服。",
 [("大黄",12,None,True),("厚朴",6,None,False),("枳实",9,None,False)]),
("调胃承气汤","阳明","伤寒论","缓下热结","阳明燥热内结，纯实无满，胃气不和","水煎，少少温服。",
 [("大黄",12,None,True),("炙甘草",6,None,False),("芒硝",9,None,False)]),
("竹叶石膏汤","阳明","伤寒论","清热生津，益气和胃","伤寒解后，虚羸少气，气逆欲吐","水煎，温服。",
 [("竹叶",15,None,True),("石膏",30,None,False),("半夏",9,None,False),("麦冬",15,None,False),("人参",6,None,False),("炙甘草",6,None,False),("粳米",9,None,False)]),
("大柴胡汤","少阳","伤寒论","和解少阳，内泻热结","少阳阳明合病，往来寒热，胸胁苦满，心下急痛","水煎，温服，日三服。",
 [("柴胡",12,None,True),("黄芩",9,None,False),("白芍",9,None,False),("半夏",9,None,False),("枳实",9,None,False),("大黄",6,None,False),("生姜",9,None,False),("大枣",3,None,False)]),
("柴胡桂枝汤","少阳","伤寒论","和解营卫，宣通枢机","太阳少阳并病，发热微恶寒，支节烦疼","水煎，温服。",
 [("桂枝",6,None,True),("白芍",6,None,False),("黄芩",6,None,False),("人参",6,None,False),("炙甘草",6,None,False),("半夏",6,None,False),("生姜",6,None,False),("大枣",3,None,False),("柴胡",12,None,False)]),
("理中汤","太阴","伤寒论","温中祛寒，补气健脾","太阴脾虚寒，腹痛下利，畏寒喜温","水煎温服，日三四服。",
 [("人参",9,None,True),("白术",9,None,False),("干姜",9,None,False),("炙甘草",9,None,False)]),
("附子理中汤","太阴","伤寒论","温中回阳","脾肾阳虚，脘腹冷痛，下利清谷","水煎温服。",
 [("人参",9,None,True),("白术",9,None,False),("干姜",9,None,False),("炙甘草",9,None,False),("制附子",6,None,False)]),
("四逆汤","少阴","伤寒论","回阳救逆","少阴亡阳，四肢厥逆，下利清谷，脉微欲绝","水煎，分温再服。",
 [("制附子",15,None,True),("干姜",9,None,False),("炙甘草",9,None,False)]),
("真武汤","少阴","伤寒论","温阳利水","阳虚水泛，小便不利，四肢沉重，腹痛下利","水煎，分温三服。",
 [("制附子",9,None,True),("茯苓",9,None,False),("白芍",9,None,False),("白术",9,None,False),("生姜",9,None,False)]),
("白通汤","少阴","伤寒论","回阳通脉","少阴下利，四肢厥逆，面赤","水煎，分温再服。",
 [("制附子",6,None,True),("干姜",6,None,False),("葱白",4,None,False)]),
("附子汤","少阴","伤寒论","温肾助阳，祛寒除湿","少阴病口中和，背恶寒，身体骨节痛","水煎，分温三服。",
 [("制附子",15,None,True),("茯苓",9,None,False),("人参",6,None,False),("白术",12,None,False),("白芍",9,None,False)]),
("四逆加人参汤","少阴","伤寒论","回阳救逆，益气生津","亡阳兼亡津，四肢厥逆，脉微","水煎，分温再服。",
 [("制附子",15,None,True),("干姜",9,None,False),("炙甘草",9,None,False),("人参",6,None,False)]),
("乌梅丸","厥阴","伤寒论","温脏安蛔，清上温下","蛔厥，久利，寒热错杂","为丸或水煎温服。",
 [("乌梅",30,None,True),("细辛",3,None,False),("干姜",6,None,False),("黄连",9,None,False),("当归",6,None,False),("制附子",6,None,False),("蜀椒",3,None,False),("桂枝",6,None,False),("人参",6,None,False),("黄柏",6,None,False)]),
("当归四逆汤","厥阴","伤寒论","温经散寒，养血通脉","手足厥寒，脉细欲绝，血虚寒凝","水煎，分温三服。",
 [("当归",9,None,True),("桂枝",9,None,False),("白芍",9,None,False),("细辛",3,None,False),("炙甘草",6,None,False),("通草",6,None,False),("大枣",4,None,False)]),
("吴茱萸汤","厥阴","伤寒论","温中补虚，降逆止呕","厥阴头痛，干呕吐涎沫，食谷欲呕","水煎温服。",
 [("吴茱萸",9,None,True),("人参",9,None,False),("生姜",12,None,False),("大枣",3,None,False)]),
("半夏泻心汤","厥阴","伤寒论","寒热平调，消痞散结","寒热错杂之痞证，心下痞满，呕吐下利","水煎，分温三服。",
 [("半夏",9,None,True),("黄芩",9,None,False),("干姜",9,None,False),("人参",9,None,False),("炙甘草",9,None,False),("黄连",3,None,False),("大枣",3,None,False)]),
("小建中汤","太阳","伤寒论","温中补虚，和里缓急","虚劳里急，腹中痛，手足烦热","水煎烊饴糖，温服。",
 [("桂枝",9,None,True),("白芍",18,None,False),("炙甘草",6,None,False),("生姜",9,None,False),("大枣",3,None,False),("饴糖",30,"烊化",False)]),
("炙甘草汤","少阴","伤寒论","滋阴养血，益气复脉","脉结代，心动悸，气短","水煎，清酒为引温服。",
 [("炙甘草",12,None,True),("人参",6,None,False),("干地黄",30,None,False),("阿胶",6,"烊化",False),("麦冬",9,None,False),("麻仁",9,None,False),("桂枝",9,None,False),("生姜",9,None,False),("大枣",4,None,False)]),
("五苓散","太阳","伤寒论","利水渗湿，温阳化气","膀胱蓄水，小便不利，烦渴欲饮","研末，白饮和服。",
 [("猪苓",9,None,True),("泽泻",15,None,False),("白术",9,None,False),("茯苓",9,None,False),("桂枝",6,None,False)]),
("猪苓汤","太阳","伤寒论","利水清热养阴","水热互结，小便不利，身热口渴","水煎，温服。",
 [("猪苓",9,None,True),("茯苓",9,None,False),("泽泻",9,None,False),("阿胶",6,"烊化",False),("滑石",9,"包煎",False)]),
("黄连阿胶汤","少阴","伤寒论","滋阴降火，除烦安神","少阴热化，心中烦，不得卧","水煎，纳胶烊化，蛋黄冲服。",
 [("黄连",6,None,True),("黄芩",6,None,False),("白芍",6,None,False),("阿胶",9,"烊化",False),("鸡子黄",2,"冲服",False)]),
("肾气丸","少阴","金匮要略","补肾助阳，化气行水","肾气不足，腰膝酸软，小便不利或反多","为丸，酒下；或水煎。",
 [("干地黄",24,None,True),("山药",12,None,False),("山茱萸",12,None,False),("泽泻",9,None,False),("茯苓",9,None,False),("牡丹皮",9,None,False),("桂枝",3,None,False),("制附子",3,None,False)]),
]
n=0
for name,mer,src,eff,ind,usage,herbs in data:
    comp={"herbs":[{"herb":h,"dose":d,"special_method":s,"is_king_herb":k,"note":None} for h,d,s,k in herbs],"meridian":mer}
    ex=c.execute("SELECT id FROM classic_formulas WHERE name=?",(name,)).fetchone()
    if ex:
        c.execute("UPDATE classic_formulas SET source=?,composition=?,efficacy=?,indications=?,usage=? WHERE id=?",
                  (src,json.dumps(comp,ensure_ascii=False),eff,ind,usage,ex[0]))
    else:
        c.execute("INSERT INTO classic_formulas(name,source,composition,efficacy,indications,usage) VALUES(?,?,?,?,?,?)",
                  (name,src,json.dumps(comp,ensure_ascii=False),eff,ind,usage))
    n+=1
c.commit()
print("已写入/更新",n,"首经方")
print("库内总数:", c.execute("SELECT count(*) FROM classic_formulas").fetchone()[0])
c.close()