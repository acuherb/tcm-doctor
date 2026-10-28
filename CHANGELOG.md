# 开发日志 CHANGELOG

## 2026-10-28 — 登录页现代化改版

- [Login.vue](file:///home/debian/tcm-doctor/frontend/src/views/auth/Login.vue) 由旧单卡片升级为单栏现代居中式：
  - 深褐渐变全屏背景 + 暖金装饰圆环 + ❋ 水印，主题色沿用全站 `--tcm-primary` / `--tcm-accent`
  - 顶部圆角渐变 Logo 徽标、主标语「传承岐黄智慧 · 以数字化服务每一位患者」
  - 大号圆角输入框、全宽主色登录按钮、「或」分隔 + 游客登录
  - 卡片 `width: 100%` + `justify-content: center`，修复根容器 `el-container` 横向 flex 使卡片在窄屏/宽屏均居中全屏
  - 响应式：手机端自动收窄不溢出，桌面/移动均友好

## 2026-10-28 — 全员移动端适配 + 药材字典补全 + 写接口权限加固

### 1. 移动端适配（手机浏览友好化）
沿用「桌面表格 / 窄屏卡片」双态切换模式（`isMobile` + `resize` 监听，<768px 判窄屏，桌面端原样保留）：

- **列表类页面**（窄屏自动切卡片视图，含编辑/删除等行内操作）：
  - 药材字典 [HerbList.vue](file:///home/debian/tcm-doctor/frontend/src/views/herb/HerbList.vue)：正名 / 异名 / 分类 / 性味 / 归经 / 剂量 / 毒性 / 功效
  - 库存管理 [InventoryManage.vue](file:///home/debian/tcm-doctor/frontend/src/views/herb/InventoryManage.vue)：突出库存量 / 最低阈值 / 有效期（低库存标红、临期标黄）
  - 患者列表 [PatientList.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/PatientList.vue)、就诊记录、处方列表 [PrescriptionList.vue](file:///home/debian/tcm-doctor/frontend/src/views/prescription/PrescriptionList.vue)（含药味标签 + 核价/审核/发药/打印）
  - 针灸穴位 [AcupointList.vue](file:///home/debian/tcm-doctor/frontend/src/views/acupoint/AcupointList.vue)、医籍文库 [BookLibrary.vue](file:///home/debian/tcm-doctor/frontend/src/views/knowledge/BookLibrary.vue)（含内容预览 3 行截断）、数据字典 [DictionaryManage.vue](file:///home/debian/tcm-doctor/frontend/src/views/dictionary/DictionaryManage.vue)（按证型/舌象/脉象动态显示对应字段）
  - 经典方库 / 针灸方库卡片网格手机单列、编辑表单控件纵向堆叠不再溢出
- **布局类页面**（`el-col` 加响应式栅格 / 抽屉化）：
  - 工作台 [Dashboard.vue](file:///home/debian/tcm-doctor/frontend/src/views/dashboard/Dashboard.vue)：统计卡两列、图表/卡片纵向堆叠
  - 统计报表 [Statistics.vue](file:///home/debian/tcm-doctor/frontend/src/views/dashboard/Statistics.vue)：时间筛选可换行、处方饼图窄屏纵向堆叠
  - 系统设置 [Settings.vue](file:///home/debian/tcm-doctor/frontend/src/views/settings/Settings.vue)：四卡纵向堆叠
  - 智能问诊 [DiagnosisChat.vue](file:///home/debian/tcm-doctor/frontend/src/views/diagnosis/DiagnosisChat.vue)：窄屏会话列表抽屉化（汉堡按钮 + 遮罩），聊天主区全宽，四诊分析表单窄屏纵向排列
- **全局兜底**：`styles/tcm-theme.scss` 追加窄屏媒体查询，所有 `el-dialog` / `el-message-box` / `el-drawer` 手机端自动接近全宽；导航侧边栏窄屏抽屉化（[MainLayout.vue](file:///home/debian/tcm-doctor/frontend/src/layouts/MainLayout.vue)）

### 2. 药材字典补全（经方引用全收录）
- `herbs_extended.json` 由 261 味正名 + 487 异名，经方覆盖率校验 0 风险（A 类同名异写 / B 类写法归一 / C 类完全未收录均清零）
- `seed.py` 改为按名称幂等插入，已有药材同步异名，后端重启自动补齐

### 3. 关键写接口显式权限校验（安全加固）
- 为 prescription / herb / diagnosis / dictionary 等 7 个路由、36 个关键写接口统一显式添加 `Depends(get_current_user)`，不再仅依赖全局中间件兜底

### 4. Docker 构建提速
- Dockerfile 调整层顺序：先 `COPY requirements.txt` 再 `pip install` 后 `COPY backend/ ./`，依赖层可命中缓存，打包从 ~12 分钟降至 ~1.5 秒（依赖未变时）

## 2026-10-26 — 就诊信息聚合 + 导出权限收紧

### 1. 患者详情「就诊信息聚合」（彻底聚合方案）
- 根因：`InquiryRecord`（问诊十问）此前只有 `patient_id`、无 `visit_id`，导致十问无法精确归属到某次就诊，前端只能把「就诊 / 十问 / 处方」拆成三条独立时间线
- 后端：`inquiry_records` 表新增可空 `visit_id`（关联 `visits.id`，向后兼容旧记录）；`main.py` 轻量迁移为既有库补列；`ConstitutionSubmit` 接收 `visit_id`、`InquiryRecordOut` 返回 `visit_id`；`/constitution` 路由写入绑定就诊
- 前端 `PatientDetail.vue` 改为**以就诊时间线为主轴**：每条就诊卡片内联展示该次的「问诊十问 + 处方」（处方本就有 `visit_id`，自然归位）；未关联就诊的历史十问单独置于底部「未关联就诊」区块
- `TenAspectsPanel.vue` 新增 `visitId` prop，提交十问时带上它；从就诊上下文「选此方开方」也带上 `visit_id`，使处方自动归属该次就诊
- `VisitRecord.vue`（新增就诊页）：保存就诊后拿到 `visit_id` 并绑定右侧十问面板，去掉强制确认弹窗，改为「已保存」提示 + 「去开药 / 返回详情」入口；一次就诊的四诊、十问、处方可在同一流程归档到一起

### 2. 游客登录恢复 + 导出权限收紧
- `allow_guest_login` 默认恢复为 `True`（游客可登录浏览）
- 前端 6 处导出入口（医籍文库 / 数据库备份 / 经典方库 / 针灸方库 / 穴位 / 药材）加 `v-if="editable"`，游客（非编辑者）界面上完全看不到导出按钮
- 后端 `/backup/export` 维持仅 admin（游客即便绕过前端直接调接口也返回 403），形成双保险，防止患者隐私（PII）泄露

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