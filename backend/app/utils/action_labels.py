"""操作日志动作名统一解析。

新增挂号收费模块后，日志里出现过「新增registration/详情/call」「撤销就诊状态」
与自动日志并存等难以阅读的写法。这里把命名收敛成一套中文动作字典：

- ACTION_ROUTES：方法 + 路径模板 → 完整业务动作（挂号、叫号、收款、退费等）
- ACTION_MAP：路径前缀 → 业务名词，与请求方法拼成「新增患者 / 查看处方」
- SEGMENT_CN：路径段兜底翻译，保证任何接口都不会出现裸英文动作名

写入侧统一由 resolve_action() 生成完整中文动作；读取侧由 display_action()
把历史落库的路径 / 半英文 / 纯名词 action 规范化，让列表、CSV、筛选口径一致。
"""
import re

METHOD_VERB = {"GET": "查看", "POST": "新增", "PUT": "修改", "PATCH": "修改", "DELETE": "删除"}

# 同一路径不同方法、或同一方法不同子路径语义差别很大时，用精确模板指定完整动作。
# 路径中的数字段会被 normalize_path() 归一成 {id}。
ACTION_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/registration"): "挂号登记",
    ("GET", "/api/v1/registration/queue"): "查看挂号队列",
    ("GET", "/api/v1/registration/options"): "查看挂号选项",
    ("GET", "/api/v1/registration/{id}"): "查看挂号详情",
    ("PATCH", "/api/v1/registration/{id}"): "更新挂号状态",
    ("POST", "/api/v1/registration/{id}/call"): "叫号接诊",
    ("POST", "/api/v1/registration/{id}/complete"): "完成就诊",
    ("POST", "/api/v1/registration/{id}/revert"): "撤销就诊状态",
    ("POST", "/api/v1/billing/charges"): "开具收费单",
    ("GET", "/api/v1/billing/charges"): "查看收费单",
    ("GET", "/api/v1/billing/charges/stats/summary"): "查看收费汇总",
    ("GET", "/api/v1/billing/charges/{id}"): "查看收费单详情",
    ("POST", "/api/v1/billing/charges/{id}/pay"): "收款",
    ("POST", "/api/v1/billing/charges/{id}/refund"): "退费",
    ("POST", "/api/v1/billing/charges/{id}/cancel"): "作废收费单",
}

# 业务域 → 中文名词；命中时取最长前缀，带 ID 的子路径继续翻译额外段。
ACTION_MAP: dict[str, str] = {
    "/api/v1/auth/password": "密码",
    "/api/v1/auth/users": "账号",
    "/api/v1/auth/me": "当前账号",
    "/api/v1/auth/permissions": "权限目录",
    "/api/v1/stock/batches/in": "入库",
    "/api/v1/stock/batches/out": "出库",
    "/api/v1/stock/batches/writeoff": "报损核销",
    "/api/v1/stock/adjust/bulk": "批量盘点校准",
    "/api/v1/stock/purchases": "采购入库",
    "/api/v1/stock/items": "物品",
    "/api/v1/stock/batches": "批次",
    "/api/v1/stock/transactions": "出入库流水",
    "/api/v1/stock/alerts": "库存预警",
    "/api/v1/stock/overview": "库存总览",
    "/api/v1/stock/options": "库存选项",
    "/api/v1/stock/suppliers": "供应商",
    "/api/v1/stock/reports": "进销存报表",
    "/api/v1/prescriptions/classic-formulas": "中药方库",
    "/api/v1/prescriptions": "处方",
    "/api/v1/patients": "患者",
    "/api/v1/visits": "就诊记录",
    "/api/v1/herbs": "药材字典",
    "/api/v1/acupoints": "针灸穴位",
    "/api/v1/acupoint-formulas": "针灸方库",
    "/api/v1/dictionaries": "数据字典",
    "/api/v1/suppliers": "供应商",
    "/api/v1/config": "系统配置",
    "/api/v1/backup/export": "数据备份",
    "/api/v1/backup/import": "数据恢复",
    "/api/v1/backup/reset": "数据清空",
    "/api/v1/backup/auto/config": "自动备份配置",
    "/api/v1/backup/auto/run": "自动备份",
    "/api/v1/backup/auto/download": "备份快照",
    "/api/v1/templates/bundle/install": "基础数据包",
    "/api/v1/registration": "挂号",
    "/api/v1/billing/charges": "收费单",
    "/api/v1/billing": "收费",
    "/api/v1/stats/dashboard": "工作台统计",
    "/api/v1/stats": "统计报表",
    "/api/v1/system/logs/export": "操作日志导出",
    "/api/v1/system/logs/clean": "操作日志清理",
    "/api/v1/system/logs": "操作日志",
    "/api/v1/diagnosis": "智能问诊",
    "/api/v1/book-library": "医籍文库",
    "/api/v1/knowledge": "知识检索",
    "/api/v1/followup-reminders": "随访提醒",
}

# 路径段 → 中文；覆盖 routers/ 下实际出现的全部静态段，兜底时不再残留英文。
SEGMENT_CN: dict[str, str] = {
    "abc": "分类", "acupoint-formulas": "针灸方", "acupoints": "穴位", "adjust": "盘点校准",
    "alerts": "预警", "analyze": "辨证分析", "auth": "账号", "auto": "自动备份", "backup": "备份",
    "batch": "批次", "batches": "批次", "billing": "收费", "bulk": "批量", "bundle": "基础数据包",
    "bundles": "基础数据包", "call": "叫号", "cancel": "作废", "charges": "收费单", "chat": "对话",
    "classic-formulas": "经典方", "clean": "清理", "complete": "完成", "config": "配置",
    "constitution": "体质辨识", "conversations": "会话", "dashboard": "工作台",
    "diagnosis": "问诊", "dictionaries": "字典", "dispense": "发药", "download": "下载",
    "duplicates": "重复项", "entries": "条目", "export": "导出",
    "followup-reminders": "随访提醒", "followups": "随访", "guest": "游客", "herbs": "药材",
    "history": "历史", "import": "导入", "in": "入库", "inquiries": "问诊", "install": "安装",
    "items": "物品", "knowledge": "知识", "login": "登录", "logout": "登出", "logs": "日志",
    "lookup": "查询", "me": "当前账号", "medical-record": "完整病历", "messages": "消息",
    "meta": "元数据", "options": "选项", "out": "出库", "overview": "总览", "password": "密码",
    "patients": "患者", "pay": "收款", "permissions": "权限", "prescriptions": "处方",
    "preview": "预览", "profit": "利润", "purchases": "采购单", "queue": "队列",
    "rebuild-index": "重建索引", "recommend": "推荐方", "refund": "退费", "registration": "挂号",
    "report": "报表", "reset": "重置", "revert": "撤销", "review": "审核", "run": "执行",
    "search": "搜索", "sign": "签名", "sources": "医籍", "stats": "统计", "status": "状态",
    "stock": "库存", "stream": "流式输出", "summary": "汇总", "supplier-price": "供应商价格",
    "suppliers": "供应商", "system": "系统", "tags": "标签", "templates": "模板",
    "transactions": "流水", "turnover": "周转", "upload-image": "上传图片", "users": "账号",
    "verify": "签名校验", "visits": "就诊", "void": "作废", "writeoff": "报损",
    "formulas": "处方", "check": "盘点", "settings": "设置", "csv": "CSV",
    "{id}": "详情",
}

# 以这些词开头的 action 本身已是完整动作，不再叠加「新增/查看」等动词。
_FULL_ACTION_PREFIXES = (
    "查看", "新增", "修改", "删除", "登录", "登出", "游客", "导出", "导入", "安装",
    "立即", "下载", "撤销", "创建", "清理", "恢复", "重置", "开具", "收款", "退费",
    "作废", "叫号", "完成", "重建", "挂号", "取消", "接诊", "审核", "发药", "校验",
    "更新", "同步", "上传", "预览", "设置",
)


def normalize_path(path: str) -> str:
    """把 /registration/12/call 归一成 /registration/{id}/call，便于模板匹配。"""
    return re.sub(r"/\d+(?=/|$)", "/{id}", path or "")


def _is_cn(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _join_segments(cn: list[str]) -> str:
    """中文段直接相连，未收录的英文段之间保留 /，避免拼成难以辨认的长串。"""
    out = cn[0]
    for prev, cur in zip(cn, cn[1:]):
        out += cur if (_is_cn(prev) and _is_cn(cur)) else f"/{cur}"
    return out


def resolve_action(method: str, path: str) -> str:
    """把请求解析成完整、人类可读的中文动作名（写入侧统一入口）。"""
    verb = METHOD_VERB.get((method or "").upper(), method or "")
    norm = normalize_path(path)
    exact = ACTION_ROUTES.get(((method or "").upper(), norm))
    if exact:
        return exact

    # 前缀匹配取最长，避免 /stock/items 抢走 /stock/items/{id}/xxx 的具体语义
    best = None
    for key in ACTION_MAP:
        if (path or "").startswith(key + "/") and (best is None or len(key) > len(best)):
            best = key
    if best:
        extra = [s for s in (path or "")[len(best):].strip("/").split("/") if s]
        extra_cn = [SEGMENT_CN.get(normalize_path("/" + p)[1:], "") for p in extra]
        extra_cn = [c for c in extra_cn if c and c != "详情"]
        base = ACTION_MAP[best]
        return f"{verb}{base}" + (f"·{'·'.join(extra_cn)}" if extra_cn else "")

    parts = [normalize_path("/" + p)[1:] for p in (path or "").split("/") if p not in ("", "api", "v1")]
    cn = [SEGMENT_CN.get(p, p) for p in parts]
    cn = [c for c in cn if c and c != "详情"]
    if not cn:
        return f"{verb}详情" if verb else "详情"
    return f"{verb}{_join_segments(cn)}"


def display_action(action: str | None, method: str | None = None,
                   endpoint: str | None = None) -> str:
    """读取侧规范化：历史日志里存过路径、半英文动作或纯名词，这里统一转成可读中文。

    新写入的 action 已是完整中文动作，直接原样返回，保证新旧数据在同一列里口径一致。
    """
    verb = METHOD_VERB.get((method or "").upper(), "")
    if not action or not action.strip():
        if endpoint:
            return resolve_action(method or "GET", endpoint)
        return "未知操作"
    a = action.strip()

    # 先处理历史遗留：action 里夹着英文字段或是整条接口路径。
    # 必须放在「完整动作前缀」判断之前，否则「新增registration/详情/call」会被当成完整动作放过。
    if re.search(r"[A-Za-z]", a) or a.startswith("/"):
        if endpoint:
            return resolve_action(method or "GET", endpoint)
        if a.startswith("/"):
            return resolve_action(method or "GET", a)
        # 无 endpoint 可回溯时，至少把已知的英文段换成中文
        out = a
        for en, cn in sorted(SEGMENT_CN.items(), key=lambda kv: -len(kv[0])):
            if not en.isascii() or len(en) < 3:
                continue
            out = re.sub(rf"(?<![A-Za-z-]){re.escape(en)}(?![A-Za-z-])", cn, out)
        return out

    # 显式审计 / 新版中间件写入的完整中文动作
    if a.startswith(_FULL_ACTION_PREFIXES):
        return a
    # 旧版中间件只落业务名词（如「患者」），补上请求方法对应的动词
    if verb:
        return f"{verb}{a}"
    return a
