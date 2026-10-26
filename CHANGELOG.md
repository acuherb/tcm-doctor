# 开发日志 CHANGELOG

## 2026-10-26 — 处方双区块改造 + 针灸方库 MVP

本日完成处方「药方 + 针灸方」双区块并列改造，并补齐与经典方库对等的**针灸方库**（此前只有穴位字典，缺「把一组穴位按方名固化成方」的库）。

### 1. 处方双区块（药方 + 针灸方）并列
- 处方编辑器改为双区块：公共信息区（患者 / 就诊 ID）→ 🌿 中药方（方名 / 煎法 / 剂数 / 服法 / 药味明细）→ 🪡 针灸方（方案名 / 针法 / 操作频次 / 疗程天数 / 配穴明细）；移除旧「中药方 / 针灸方二选一」切换
- `Prescription` 新增 4 个针灸方顶层字段：`acupoint_formula_name`（独立方案名，不沿用中药方名）/ `acupoint_technique` / `treatment_frequency` / `treatment_days`（疗程为天数字段）
- 后端 `models/prescription.py` + `schemas/prescription.py` 新增字段；`main.py` 轻量迁移追加 4 列；`routers/prescription.py` 创建与编辑同步 4 字段
- 按内容自动判定 `prescription_type`（药方 / 针方 / 混合）；支持经 `?id=` 回显既有处方走 `PUT` 编辑
- 一张处方可只开药方、只开针方或两者兼有

### 2. 处方列表 / 详情 / 打印完善
- 列表表格新增「针灸方」列：方案名 ＋ 配穴绿色标签 ＋ 针法·频次·疗程天数一行元信息
- 详情弹窗新增「🪡 针灸方」信息块（按需展示方案名 / 针法 / 操作频次 / 疗程天数），再接配穴明细表
- 打印模板补充针灸方顶层字段；**修复布局**：剂数 / 煎法 / 服法归属中药方区块，置于针灸方之前（纯针灸方时不显示），底部仅保留医嘱 / 医师

### 3. 针灸方库（AcupointFormula）MVP
- 新增模型 [AcupointFormula](file:///home/debian/TCM/tcm-doctor/backend/app/models/acupuncture.py)（与经典方库 `ClassicFormula` 对等）：`name` / `source` / `efficacy` / `indications` / `usage` ＋ 默认 `technique` / `treatment_frequency` / `treatment_days` ＋ `composition{ acupoints[] }`
- 新路由 [acupoint_formula.py](file:///home/debian/TCM/tcm-doctor/backend/app/routers/acupoint_formula.py)：`GET /api/v1/acupoint-formulas`（搜索 / 出处筛选）、`POST`、`PUT/{id}`、`DELETE/{id}`、`GET/{id}` 详情、`GET/export`、`POST/import`（按方名 upsert）
- `Prescription` 加 `acupoint_formula_id` 外键关联（与 `classic_formula_id` 对称）；`main.py` 轻量迁移追加该列
- 种子数据 [acupoint_formulas.json](file:///home/debian/TCM/tcm-doctor/backend/app/data/acupoint_formulas.json)：内置安神定志 / 健脾和胃 / 腰痛 / 疏风解表 / 调经 / 醒脑开窍 6 首针方（来源标注「倪海厦·针灸」/「通用」）；`seed.py` 新增 `seed_acupoint_formulas` 增量灌库
- 前端新增 [AcupointFormulaLib.vue](file:///home/debian/TCM/tcm-doctor/frontend/src/views/acupoint/AcupointFormulaLib.vue)（卡片列表 / 详情 / 新增编辑 / 导入导出 JSON），侧边菜单「处方管理」下新增「针灸方库」入口
- 「引入到处方编辑器」经 `?acupoint_formula_id=` 一键预填针灸方名 / 针法 / 频次 / 疗程天数 ＋ 全部配穴

## 2026-10-25 — 倪海厦经方体系整体改造

本日将系统由「大学派 / 王琦九种体质」彻底切换为**倪海厦经方家体系**，并把「问诊 → 辨证 → 选方 → 开方 → 归档」打通为完整闭环。

### 1. 诊断体系替换
- 移除王琦九种体质百分比评分，改为**倪海厦问诊十问**：
  - 睡眠 / 胃口 / 大便 / 小便 / 口渴 / 寒热 / 汗 / 体力 / 性功能 / 女子月经
  - 每题预定义选项 + 自填项，单选支持**再次点击取消**
  - 按倪师原文判据做六经 / 寒热 / 虚实偏性推理（无百分比，命中点数组出偏性画像，如「少阴·里寒」）
- 后端推理引擎 [constitution_evaluator.py](file:///home/debian/TCM/tcm-doctor/backend/app/services/constitution_evaluator.py) 输出 `primary_type / scores / secondary_types / suggestion`

### 2. 就诊页一体化
- 取消独立「体质辨识」菜单，问诊十问整合进就诊页 [VisitRecord.vue](file:///home/debian/TCM/tcm-doctor/frontend/src/views/patient/VisitRecord.vue)
- 同一页面完成「四诊信息 ＋ 辨证论治 ＋ 问诊十问」，左侧两卡与右侧十问高度对齐
- 十问封装为可复用组件 [TenAspectsPanel.vue](file:///home/debian/TCM/tcm-doctor/frontend/src/components/TenAspectsPanel.vue)
- 新增 `inquiry_records` 表持久化每次十问的原始答案 / 自填备注 / 评估结果
- 患者详情页 [PatientDetail.vue](file:///home/debian/TCM/tcm-doctor/frontend/src/views/patient/PatientDetail.vue) 新增「问诊十问记录 / 处方记录」时间线，统一病例链

### 3. 辨证 → 选方 → 开方闭环
- 十问辨证结果区新增「可参考经方」推荐区块
- 后端新增六经推荐接口 `GET /prescriptions/classic-formulas/recommend?meridian=`
  （太阳→桂枝汤/麻黄汤/葛根汤…；少阳→小柴胡/大柴胡…；少阴→四逆/真武/附子…；厥阴→乌梅丸/当归四逆…）
- 点「选此方开方」→ 跳转处方编辑器，自动预填患者并导入该方完整组成（药味 / 剂量 / 煎法 / 甘药），形成闭环

### 4. 经典方剂库扩充（146 首，0 缺失）
- 自动读取 `nihaixia/references/audit/fangji_112.txt`，导入 **《伤寒论》112 方全集**并六经归档
- 补入**金匮要略常用方**（温经汤、当归芍药散、半夏厚朴汤、越婢汤、甘麦大枣汤等）
- 修复首轮导入误清空的核心方组成，补全 34 首关键方（桂枝汤/小柴胡/四逆/真武/乌梅丸/大承气等）完整药味与克重
- 方剂库页面支持 **新增 / 编辑 / 删除 / 导入 JSON / 导出 JSON**（导入按方名 upsert，可迁移备份）
- 种子脚本：[backend/_seed_jingfang.py](file:///home/debian/TCM/tcm-doctor/backend/_seed_jingfang.py)，可随时重放重建库

### 5. 问题修复
- 经典方库 500：`composition` 字段 schema 由 `list[dict]` 放宽为 `dict | list | None` 以兼容字典结构数据
- 问诊十问「选择后点评估无结果」：对接新记录写入并返回完整结果
- 就诊页左列过度拉伸、十问与四诊不对齐：调整间距与纵向拉伸

### 6. 针灸配穴体系
- 新增穴位库：`acupoints` 表，句柄合并**倪师穴位索引（50 穴带定位详情）＋ 针灸 164 项**，内置按名去重后 **170 穴**，按十四经 / 任督归类
- 种子脚本：[backend/seed_acupoints.py](file:///home/debian/TCM/tcm-doctor/backend/seed_acupoints.py)，可随时重放重建库，带定位/归经详情共 50 穴
- 新增穴位 rest 路由 `GET/POST/PUT/DELETE /acupoints`（含关键词搜索 `?q=` 与 `?meridian=` 筛选）
- 处方支撑针灸配穴：新增关联表 `acupoint_prescriptions`，每条处方可携带多个配穴（穴位 / 针法 / 留针 / 顺序 / 备注），与药味 `prescription_items` 平行
- 创建处方接口接受 `acupoints` 数组；处方详情 / 列表通过 `joinedload` 一并返回针灸配穴，供展示与打印
- 前端处方编辑器新增「针灸配穴」区块：可搜索 170 穴（支持手输新增）、选针法 / 留针 / 顺序 / 备注，并支持添加 / 删除配穴
- 处方详情弹窗与打印模板均支持针灸配穴表格展示

### 7. 针灸配穴体验优化
- **针灸 / 汤药解耦**：药味与针灸均改为非必选，只要二者至少填写一项即可保存（支持纯针灸、纯药方、针灸+汤药三种模式），并加模型校验提示
- **选穴精确定位**：新增「按归经筛选」快捷下拉，先按十四经/奇穴缩小范围再选；选项展示穴位名＋特定穴类型＋归经＋定位（两行式排版），便于对照取穴
- **时间概念落地**：「留针」输入框改用带「留针·分钟」单位的前缀输入框；处方详情弹窗与打印模板统一显示「xx 分钟」
- 穴位下拉关闭 teleport，保证两行式选项在 scoped 样式下正常渲染

### 遗留可选事项（未做，看需要）
- 经典方库添加「按六经筛选」快捷 Tab
- 校验各经方药味是否都已收录进授权药材库（脚本草稿 `backend/_check_herbs_coverage.py`）
- 统一部分以原方「两/枚」表达与克重换算的剂量口径