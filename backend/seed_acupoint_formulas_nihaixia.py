"""导入《倪海厦·人纪-1-针灸 / 病症针灸速查》到针灸方库 (acupoint_formulas)

数据源: /home/debian/倪海厦/人纪-1-针灸/病症针灸速查/215条针灸经验穴位和31条透针透穴.md
入库到: tcm-doctor/backend/tcm_doctor.db 的 acupoint_formulas 表

资料结构:
  - 开头零散 @病症：穴位 速查卡片 (1-43 行附近)
  - ## 215条针灸经验: 11 个系统分类(#### 01心·心血管 ...), 每条 `1. 病症：穴位`
  - ## 31条透针透穴: 每条 `1. 透穴名` + `治症：` + `来源：`

映射:
  - name     = 病症名 / 透穴名
  - source   = 倪海厦·针灸
  - composition.acupoints = 解析出的穴位名(去"穴"后缀, 与 acupoints.name 一致)
  - indications = 病症名 / 透穴治症
  - notes    = 【分类】... + 特殊技法(透刺/放血/梅花灸) + 透穴来源配穴 + 无法识别的残留词
  - efficacy/频次/天数 等不编造, 留空

识别策略: 内置标准经穴+常见奇穴白名单做判定; "X透Y" 拆两穴并标透刺; 去括号保留说明;
  粘连词(合谷止痛/开四关)用最长子串匹配拆出穴位; 纯非穴位词进 notes; 解析不出任何穴位则跳过该条。

用法:
  cd tcm-doctor/backend && python3 seed_acupoint_formulas_nihaixia.py            # dry-run 预览
  cd tcm-doctor/backend && python3 seed_acupoint_formulas_nihaixia.py --apply    # 落库(upsert, 幂等)
"""
import os
import re
import sys
import json
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/home/debian/倪海厦/人纪-1-针灸/病症针灸速查/215条针灸经验穴位和31条透针透穴.md"
DB = os.path.join(HERE, "tcm_doctor.db")

# ---------------------------------------------------------------------------
# 穴位识别白名单 (仅用于解析识别, 不入库)
# ---------------------------------------------------------------------------
STANDARD = {
    # 任脉
    "会阴","曲骨","中极","关元","石门","气海","阴交","神阙","水分","下脘","建里","中脘","上脘","巨阙","鸠尾","中庭","膻中","玉堂","紫宫","华盖","璇玑","天突","廉泉","承浆",
    # 督脉
    "长强","腰俞","腰阳关","命门","悬枢","脊中","中枢","筋缩","至阳","灵台","神道","身柱","陶道","大椎","哑门","风府","脑户","强间","后顶","百会","前顶","囟会","上星","神庭","素髎","水沟","兑端","龈交",
    # 手太阴肺经
    "中府","云门","天府","侠白","尺泽","孔最","列缺","经渠","太渊","鱼际","少商",
    # 手阳明大肠经
    "商阳","二间","三间","合谷","阳溪","偏历","温溜","下廉","上廉","手三里","曲池","肘髎","手五里","臂臑","肩髃","巨骨","天鼎","扶突","禾髎","迎香",
    # 足阳明胃经
    "承泣","四白","巨髎","地仓","大迎","颊车","下关","头维","人迎","水突","气舍","缺盆","气户","库房","屋翳","膺窗","乳中","乳根","不容","承满","梁门","关门","太乙","滑肉门","天枢","外陵","大巨","水道","归来","气冲","髀关","伏兔","阴市","梁丘","犊鼻","足三里","上巨虚","条口","下巨虚","丰隆","解溪","冲阳","陷谷","内庭","厉兑",
    # 足太阴脾经
    "隐白","大都","太白","公孙","商丘","三阴交","漏谷","地机","阴陵泉","血海","箕门","冲门","府舍","腹结","大横","腹哀","食窦","天溪","胸乡","周荣","大包",
    # 手少阴心经
    "极泉","青灵","少海","灵道","通里","阴郄","神门","少府","少冲",
    # 手太阳小肠经
    "少泽","前谷","后溪","腕骨","阳谷","养老","支正","小海","肩贞","臑俞","天宗","秉风","曲垣","肩外俞","肩中俞","天窗","天容","颧髎","听宫",
    # 足太阳膀胱经
    "睛明","攒竹","眉冲","曲差","五处","承光","通天","络却","玉枕","天柱","大杼","风门","肺俞","厥阴俞","心俞","督俞","膈俞","肝俞","胆俞","脾俞","胃俞","三焦俞","肾俞","气海俞","大肠俞","关元俞","小肠俞","膀胱俞","中膂俞","白环俞","上髎","次髎","中髎","下髎","会阳","承扶","殷门","浮郄","委阳","委中","附分","魄户","膏肓","神堂","譩譆","膈关","魂门","阳纲","意舍","胃仓","肓门","志室","胞肓","秩边","合阳","承筋","承山","飞扬","跗阳","昆仑","仆参","申脉","金门","京骨","束骨","通谷","至阴",
    # 足少阴肾经
    "涌泉","然谷","太溪","大钟","水泉","照海","复溜","交信","筑宾","阴谷","横骨","大赫","气穴","四满","中注","肓俞","商曲","石关","阴都","腹通谷","幽门","步廊","神封","灵墟","神藏","彧中","俞府",
    # 手厥阴心包经
    "天池","天泉","曲泽","郄门","间使","内关","大陵","劳宫","中冲",
    # 手少阳三焦经
    "关冲","液门","中渚","阳池","外关","支沟","会宗","三阳络","四渎","天井","清冷渊","消泺","臑会","肩髎","天髎","天牖","翳风","瘈脉","颅息","角孙","耳门","耳和髎","丝竹空",
    # 足少阳胆经
    "瞳子髎","听会","上关","颔厌","悬颅","悬厘","曲鬓","率谷","天冲","浮白","头窍阴","完骨","本神","阳白","头临泣","目窗","正营","承灵","脑空","风池","肩井","渊液","辄筋","日月","京门","带脉","五枢","维道","居髎","环跳","风市","中渎","膝阳关","阳陵泉","阳交","外丘","光明","阳辅","悬钟","丘墟","足临泣","地五会","侠溪","足窍阴",
    # 足厥阴肝经
    "大敦","行间","太冲","中封","蠡沟","中都","膝关","曲泉","阴包","足五里","阴廉","急脉","章门","期门",
}
EXTRA = {
    # 常用奇穴 / 经验穴 / 别名
    "天应","阿是","十宣","四关","人中","胆石点","消积","痞根","定喘","安眠","华佗夹脊","八风","八邪","鹤顶","膝眼","阑尾","百虫窝","肘尖","中泉","二白","腰痛点","落枕","太阳","鱼腰","球后","翳明","金津","玉液","聚泉","海泉","颈百劳","子宫","提托","十七椎","腰奇","三毛","肠关","肝关","心关","肺关","肾关","外劳宫","中魁","大骨空","小骨空","印堂","胆囊","血压点","结核点","牵正","颊里","耳尖","耳背","大抒",
}
ALL = STANDARD | EXTRA


def is_point(x: str) -> bool:
    return x in ALL


def longest_match(base: str):
    """在 base 中找白名单里最长的子串穴位名"""
    best = None
    for h in ALL:
        if h in base and (best is None or len(h) > len(best)):
            best = h
    return best


# 无意义残留词(来自粘连/虚词), 不进 notes
_NOISE = {"等", "及", "开", "注意", "治法", "治疗", "处方"}


def add_extra(extra: list, x: str):
    x = x.strip()
    if len(x) <= 1 or x in _NOISE:
        return
    if x not in extra:
        extra.append(x)


def to_comp(pts: list):
    """把穴位名列表转成与项目约定一致的对象数组格式
    (原'通用'方、前端都用 {acupoint_name, technique, retention, sequence, note})"""
    return {"acupoints": [
        {"acupoint_name": p, "technique": None, "retention": None,
         "sequence": i + 1, "note": None}
        for i, p in enumerate(pts)
    ]}


def parse_points(text: str):
    """返回 (穴位列表, 非穴位残留词列表)"""
    extra = []
    points = []
    # 1) 透刺: X透Y -> 拆两穴, 并把原文替换成 "X Y" 以免残留
    for a, b in re.findall(r"([\u4e00-\u9fff]{1,5})透([\u4e00-\u9fff]{1,5})", text):
        if is_point(a):
            points.append(a)
        if is_point(b):
            points.append(b)
        text = text.replace(f"{a}透{b}", f"{a} {b}")
    # 2) 括号内容保留为文本(说明/配穴/放血等)
    text = re.sub(r"[（(]([^）)]*)[)）]", lambda m: " " + m.group(1) + " ", text)
    # 3) 按分隔符切分
    tokens = re.split(r"[、，,\s；;：:与及]+", text)
    for tok in tokens:
        tok = tok.strip()
        if not tok or tok in {"等", "及"}:
            continue
        base = tok[:-1] if tok.endswith("穴") else tok
        base = base.strip()
        if not base:
            continue
        if is_point(base):
            points.append(base)
        else:
            hit = longest_match(base)
            if hit:
                points.append(hit)
                rest = base.replace(hit, "", 1).strip()
                if rest:
                    add_extra(extra, rest)
            else:
                add_extra(extra, base)
    seen = set()
    uniq = []
    for p in points:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq, extra


def parse_md(text: str):
    lines = text.splitlines()
    formulas = []

    # 定位三个区块
    i_b = next((i for i, l in enumerate(lines) if l.strip().startswith("## 215条针灸经验")), None)
    i_c = next((i for i, l in enumerate(lines) if l.strip().startswith("## 31条透针透穴")), None)
    if i_b is None:
        i_b = 0
    if i_c is None:
        i_c = len(lines)
    head = lines[:i_b]
    body = lines[i_b:i_c]
    tail = lines[i_c:]

    def split_name_rest(s):
        if "：" in s:
            n, _, r = s.partition("：")
        elif ":" in s:
            n, _, r = s.partition(":")
        else:
            return None, None
        return n.strip().strip("（）()"), r.strip()

    # ---- 区块A: 开头零散卡片 ----
    for line in head:
        s = line.strip()
        if not s:
            continue
        s2 = re.sub(r"^[＠@]\s*", "", s)
        name, rest = split_name_rest(s2)
        if not name or not rest:
            continue
        pts, extra = parse_points(rest)
        if not pts:
            continue
        notes = "【分类】病症速查(零散)"
        if extra:
            notes += "；备注：" + "、".join(extra)
        formulas.append({
            "name": name, "source": "倪海厦·针灸", "indications": name,
            "composition": to_comp(pts), "notes": notes,
        })

    # ---- 区块B: 215条经验 ----
    cur_cat = ""
    for line in body:
        s = line.strip()
        if s.startswith("#### "):
            cur_cat = s[5:].strip()
            continue
        if s.startswith("## "):
            continue
        m = re.match(r"^\d+[.、]\s*(.+)$", s)
        if not m:
            continue
        entry = m.group(1).strip()
        if entry.startswith("【医案】") or entry.startswith("医案"):
            continue
        name, rest = split_name_rest(entry)
        if not name:
            continue
        if not rest:
            continue
        pts, extra = parse_points(rest)
        if not pts:
            continue
        notes = f"【分类】{cur_cat}" if cur_cat else ""
        if extra:
            notes += ("；" if notes else "") + "备注：" + "、".join(extra)
        formulas.append({
            "name": name, "source": "倪海厦·针灸", "indications": name,
            "composition": to_comp(pts), "notes": notes,
        })

    # ---- 区块C: 31条透穴 ----
    pending = None
    for line in tail:
        s = line.strip()
        m = re.match(r"^\d+[.、]\s*(.+)$", s)
        if m:
            name = m.group(1).strip()
            pts, extra = parse_points(name)
            pending = {
                "name": name, "source": "倪海厦·针灸", "indications": "",
                "composition": to_comp(pts), "notes": "【分类】透针透穴",
                "_z": "", "_l": "", "_e": extra,
            }
            formulas.append(pending)
        elif s.startswith("治症：") or s.startswith("治症:"):
            if pending is not None:
                pending["_z"] = s.split("：", 1)[-1].split(":", 1)[-1].strip()
        elif s.startswith("来源：") or s.startswith("来源:"):
            if pending is not None:
                pending["_l"] = s.split("：", 1)[-1].split(":", 1)[-1].strip()
        # 其它行(医案/临证心悟/空白)忽略
    for f in formulas:
        if "_z" in f:
            f["indications"] = f.get("_z") or f["name"]
            notes = f["notes"]
            if f.get("_l"):
                notes += "；来源：" + f["_l"]
            if "透" in f["name"]:
                notes += "；透刺：" + f["name"]
            if f.get("_e"):
                notes += "；备注：" + "、".join(f["_e"])
            f["notes"] = notes
            del f["_z"], f["_l"], f["_e"]

    return formulas


def upsert(formulas, apply: bool):
    conn = sqlite3.connect(DB)
    created = updated = skipped = 0
    for f in formulas:
        name = f["name"]
        row = conn.execute("SELECT id FROM acupoint_formulas WHERE name=?", (name,)).fetchone()
        comp = json.dumps(f["composition"], ensure_ascii=False)
        if row:
            if apply:
                conn.execute(
                    "UPDATE acupoint_formulas SET source=?, indications=?, composition=?, notes=? WHERE id=?",
                    (f["source"], f["indications"], comp, f["notes"], row[0]),
                )
            updated += 1
        else:
            if apply:
                conn.execute(
                    "INSERT INTO acupoint_formulas (name, aliases, source, efficacy, indications, usage, technique, treatment_frequency, treatment_days, composition, notes, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (name, json.dumps([], ensure_ascii=False), f["source"], None, f["indications"],
                     None, None, None, None, comp, f["notes"], datetime.now().isoformat(sep=" ")),
                )
            created += 1
    if apply:
        conn.commit()
    conn.close()
    return created, updated


def main():
    apply = "--apply" in sys.argv
    with open(SRC, encoding="utf-8") as fh:
        text = fh.read()
    formulas = parse_md(text)

    print(f"解析出方剂条数: {len(formulas)}")
    # 统计分类
    cats = {}
    for f in formulas:
        m = re.search(r"【分类】(.*?)(；|$)", f["notes"])
        c = m.group(1) if m else "(无)"
        cats[c] = cats.get(c, 0) + 1
    print("按分类:")
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")

    print("\n=== 样例(前 8 条) ===")
    for f in formulas[:8]:
        print(f"  · {f['name']}  ->  {f['composition']['acupoints']}")
        if f["notes"]:
            print(f"      备注: {f['notes']}")

    if apply:
        created, updated = upsert(formulas, True)
        total = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM acupoint_formulas").fetchone()[0]
        print(f"\n[APPLY] 新增={created} 更新={updated}  库内 acupoint_formulas 总数={total}")
    else:
        print("\n[dry-run] 未写入数据库。加 --apply 落库(upsert, 幂等可重放)。")


if __name__ == "__main__":
    main()
