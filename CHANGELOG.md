# 开发日志 CHANGELOG

## 2026-10-31 — 药材库重构：多维标签化（按《本经》三品 + 倪师思路）

### 背景
原 `Herb` 的 `category`/`nature`/`flavor`/`meridian_tropism` 都是单值（味与归经挤在一根字符串里），一味药只能挂一个分类，药材多了无法按维度检索。改为**多维属性标签**：三品 / 四气 / 五味 / 归经 / 升降浮沉 / 通用标签（功效分类·主治证型·经方常用…），契合《本经》"药对证、不对病"思想；单一 `category` 树下线，并入 `tags`。

### 1. 后端地基（ddddbc7）
- `models/herb.py`：`Herb` 新增 `grade`(三品) / `flavors`(五味) / `meridians`(归经) / `directions`(升降浮沉) / `tags`(通用标签) 多维标签列。
- `constants/herb_tags.py`：受控词表（三品/四气/五味/归经/升降浮沉）+ `sanitize_herb_tags` 写入清洗；`GET /herbs/tags/meta` 返回维度词表与标签建议。
- `scripts/migrate_herb_tags.py`：幂等迁移，新增列并从旧 `flavor`/`meridian_tropism`/`category` 回填（已对 261 味执行）。
- 安全校验改为**仅超剂量 / 毒性 / 孕妇禁忌**（《本经》三品标注），移除十八反·十九畏死数据/组件。

### 2. 多维筛选（0fa9147）
- `GET /herbs` 新增 `grade/nature/flavors/meridians/directions/tags/pregnancy_contraindicated` 参数；多值维度命中任一（集合交集）。

### 3. 前端（本次）
- [HerbList.vue](file:///home/debian/tcm-doctor/frontend/src/views/herb/HerbList.vue)：筛选区/编辑弹窗/表格/移动端卡片全面改为多维标签（多选器驱动于 `/herbs/tags/meta`）；旧的"单一分类下拉 + 味/归经自由文本框"下线，表格新增三品徽标与五味/归经/升降浮沉/标签标签列。

### 4. 数据字典接管标签词表（本次）
- 受控维度候选项（三品/四气/五味/归经/升降浮沉）由**数据字典**托管：`DictionaryTerm(term_type='herb_tag', category=维度中文名)` 存储，**不再写死在 `constants/herb_tags.py`**；`GET /herbs/tags/meta` 改读 DB（字典为空回退常量），写入校验 `sanitize_herb_tags(allowed)` 以字典为权威——在「字典管理」页即可增删候选项，无需改代码。
- [seed_dictionaries.py](file:///home/debian/tcm-doctor/backend/seed_dictionaries.py)：把 5 个维度的 35 个候选项作为 `herb_tag` 词条种子（被 `seed_all()` 调用，全新库自动带）；`routers/dictionaries.py` 的 `term_type` 白名单加入 `herb_tag`。
- [DictionaryManage.vue](file:///home/debian/tcm-doctor/frontend/src/views/dictionary/DictionaryManage.vue)：新增「药材标签」页签，按维度（三品/四气/五味/归经/升降浮沉）归类管理词条。
- **功效分类概念彻底移除**：搜索栏与编辑弹窗的"功效分类/标签"框下线；`tags` 仅作为**自由标注**（主治/经方/产地/炮制），`/herbs/tags/meta` 不再返回 `tag_suggestions`；迁移写入的 261 味旧 `category` 保留为普通自由标签不强制。

### 5. 本草经式表头（本次）
- 用户（翻《神农本草经》）重新定义药材字典表头为传统本草经式：**正名 | 异名 | 性味(性·味·毒性) | 主治 | 禁忌 | 剂量 | 状态 | 操作**。
- 列表「性/味/毒性」三列合并为一列「性味」（展示如 `温 · 辛甘 · 有小毒`，毒性仅在非"无毒"时出现）；`功效` 列改名 `主治`；新增 `禁忌` 自由文本列。移动端卡片同步。
- 按用户决定，**表格移除三品/归经/升降浮沉独立列**（性/味之外的维度仍可在编辑弹窗的"其它标签（可选）"分隔区填写，数据不丢）。
- 后端 `Herb` 模型 + `HerbCreate/HerbUpdate/HerbResponse` 新增 `contraindication`(禁忌) 文本字段；[migrate_herb_tags.py](file:///home/debian/tcm-doctor/backend/scripts/migrate_herb_tags.py) 幂等 ALTER 新增 `herbs.contraindication` 列（老库已执行，`create_all` 覆盖全新库）。
- 编辑弹窗重排：四气+五味+毒性(性味)、主治、禁忌 前置；三品/归经/升降浮沉/通用标签 归入"其它标签（可选）"分隔区。

### 6. 三品/归经/升降浮沉 全量移除 + 表头严格对齐（本次）
- 用户最终决定：**三品 / 归经 / 升降浮沉 一处都不要**。已从表格、搜索框筛选、编辑弹窗、数据字典（维度与词条）**全量移除**。
- 表头严格对齐用户给的本草经式清单，仅保留 **正名 | 异名 | 性味 | 主治 | 禁忌 | 剂量 | 状态 | 操作**；连之前保留的「通用标签」列也一并去掉（不在用户清单内）。
- 后端 [constants/herb_tags.py](file:///home/debian/tcm-doctor/backend/app/constants/herb_tags.py)：`HERB_TAG_DIMENSIONS` 仅留 **四气(nature) / 五味(flavors)**，`_CONTROLLED` 同步收敛；`/herbs/tags/meta` 现只返回这两维。
- 数据字典：删除 19 条 `herb_tag` 孤儿词条（三品 3 + 归经 12 + 升降浮沉 4）；[DictionaryManage.vue](file:///home/debian/tcm-doctor/frontend/src/views/dictionary/DictionaryManage.vue) 药材标签维度下拉仅剩 四气/五味。
- 搜索框现仅剩：关键词、四气、五味、仅看孕妇禁忌。`HerbList.vue` 清理掉 `gradeTag`/`toxicityTag` 死函数与对应筛选 ref。
- 说明：`herbs` 表的 `grade/meridians/directions/tags` 列仍保留（数据不丢、向后兼容），仅不再出现在 UI；如需彻底废弃可后续 DROP。

### 7. 编辑弹窗补上「状态」开关（本次）
- 表格一直有「状态」（启用/停用），但编辑弹窗漏了。现已在编辑框加入 `状态` 开关（启用/停用），与表格一致；新增药材默认启用。
- 后端 `HerbCreate` 补全 `is_active`（默认 `True`），`HerbUpdate` 本已支持；`submitForm` 正常回写 `is_active`。

## 2026-10-30 — AI 推荐方结构化带入开方（主方/副方 + 加减勾选 + 字典校验）

### 背景
此前 AI 把主方、副方、加减全揉成一段自由文本，前端正则硬抠导致串味（如「仁子丸」、把 15g/后下 混进药名、副方药味并到主方）。本次改为 **AI 输出强制结构化 JSON + 前端勾选式带入**。

### 1. 后端：结构化 JSON 输出与解析
- [ai_diagnosis_service.py](file:///home/debian/tcm-doctor/backend/app/services/ai_diagnosis_service.py) 分析 prompt 末端 JSON 指令改为要求 `formulas` 数组，元素含 `name / role(主方·副方) / preparation / herbs[{name,dose,method}] / modifications[{label, add:[{name,dose,method}], remove:[]}]`；并要求药名纯中文、剂量进 `dose`、煎法进 `method`、严禁多方针塞同一对象。
- 新增 `_extract_json_block` / `_clean_herb_name` / `_split_herbs`，重写 `_parse_formulas`：解析新 schema，并兼容旧 `recommended_formulas`(composition 文本) / 旧 bullet 文本兜底。

### 2. 前端：结构化带入开方弹窗
- 新增 [AiFormulaImportDialog.vue](file:///home/debian/tcm-doctor/frontend/src/components/AiFormulaImportDialog.vue)：展示主方/副方 + 基础组成 + 加减项（checkbox），勾选后**合并**（add 并入、remove 移除对应药味），并对照药材字典（`herbs` 表）校验——字典无此药则**标红警告但仍可带入**（由医生核对）。
- [PrescriptionEditor.vue](file:///home/debian/tcm-doctor/frontend/src/views/prescription/PrescriptionEditor.vue)：`/prescriptions/new?ai_import=<结构化方剂>` 打开带入弹窗；确认后生成处方（药名纯中文、剂量单独、特殊煎法写入 `special_method`、`preparation_method` 写入剂型）；主方/副方各自独立成方。保留旧 `ai_formula` 自由文本兜底。
- [VisitCard.vue](file:///home/debian/tcm-doctor/frontend/src/components/VisitCard.vue) / [VisitRecord.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/VisitRecord.vue)：解析与渲染结构化方剂（role 标签、组成、加减），「去开药」改传 `ai_import`；诊断库展示用 `stripJsonBlock` 去除 JSON 代码块；`saveAiIntoRecord` 以规范 Markdown（【推荐方剂】）存库，可再次解析回结构化。

### 3. 修复：带入弹窗只显示方名、药味丢失（URL 超长截断）
- 根因：结构化方剂（主方+副方，各含药味与多条长加减方案）作为 JSON 直接塞进 URL query，体积过大超出 URL/请求行长度限制，服务端截断 JSON 致 `herbs` 被切掉（弹窗只剩方名）。
- 修复：`goPrescribeWithFormula` 改为把结构化方剂写入 `sessionStorage`、仅传一个短 key（[VisitCard.vue](file:///home/debian/tcm-doctor/frontend/src/components/VisitCard.vue) / [VisitRecord.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/VisitRecord.vue)）；[PrescriptionEditor.vue](file:///home/debian/tcm-doctor/frontend/src/views/prescription/PrescriptionEditor.vue) 按 key 从 `sessionStorage` 取回（读取后删除），并保留 `ai_import` / `ai_formula` 旧 query 形式兜底。

### 4. 修复：历史存档 AI 方剂带入后处方列表空白（老格式 composition 未解析）
- 根因：[VisitCard.vue](file:///home/debian/tcm-doctor/frontend/src/components/VisitCard.vue) 的 `jsonObjToFormula` 只读取新格式 `herbs` 数组；而**此前已存档**的诊断库文本里 `recommended_formulas` 是 `{name, composition(药味字符串), modification(加减文本)}`，无 `herbs` 数组 → 解析出方名但 `herbs` 为空，诊断库与带入开方都看不到药味。
- 修复：`jsonObjToFormula` 增加兜底——`herbs` 缺失时由 `composition` 字符串经 `splitHerbs` 拆出药名/剂量/煎法；`modifications` 缺失时由 `modification` 文本按 `；` 拆为加减项（纯文本标注）。已用新旧两种格式单测验证均正确解析出药味。

## 2026-10-30 — AI 辨证纳入性别/年龄/身高/体重，剂量个体化

### 1. 患者体征信息进入辨证 prompt
- [DiagnosisAnalyzeRequest](file:///home/debian/tcm-doctor/backend/app/schemas/diagnosis.py) 新增 `patient_age` / `patient_height_cm` / `patient_weight_kg`
- [ai_diagnosis_service.py](file:///home/debian/tcm-doctor/backend/app/services/ai_diagnosis_service.py) `analyze` / `analyze_stream` 的 `patient_info` 现拼接 性别 / 年龄 / 身高 / 体重，并在身高体重齐全时自动计算 BMI
- 路由 `/diagnosis/analyze`、`/analyze/stream` 透传上述字段
- 前端 [VisitRecord.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/VisitRecord.vue) 加载患者信息时存入 `patient`，AI 辨证请求携带真实 性别 / 出生日期(推导年龄) / 身高 / 体重（顺带修复此前 `patient_gender` 被硬编码为空、性别也未真正传入的问题）
- 「核对本次辨证信息」预览现在也会列出患者基本信息（性别 / 年龄 / 身高 / 体重 / BMI），并把患者体征纳入缓存指纹——体征变化时重新辨证而非复用旧结果
- 修复嵌入详情页抽屉（embedded）时 `patient` 未注入、预览与请求仍显示「未填写」的问题：[VisitRecord.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/VisitRecord.vue) 新增 `patient` prop，由 [PatientDetail.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/PatientDetail.vue) 直接传入已加载的患者对象，未传时回退 API 拉取

### 2. 剂量个体化规则（系统提示第 10 条）
- 推荐经方剂量须结合患者体重 / 年龄 / 性别调整：以标准成人约 60kg 为基准按比例增减；儿童 / 老人 / 久病体弱者减量；女性经期 / 孕期 / 产期注意禁忌；未知体重年龄则按常规成人量并注明需结合调整；严禁对所有人均给同一固定剂量

## 2026-10-30 — AI 辨证经方约束 + 推荐方解析清洗（修 bug）

### 1. AI 辨证严格按倪海厦经方体系
- `TCM_SYSTEM_PROMPT` 第 3 条强化为「只用《伤寒论》《金匮要略》经方、方证对应」，明确**严禁温病/时方**（杏苏散、止嗽散、桑菊饮、银翘散、荆防败毒散、参苏饮、二陈汤、三子养亲汤等），并给出常见证型的对应经方示例（如太阳表证兼太阴痰湿咳喘→小青龙汤、太阳中风咳→桂枝加厚朴杏子汤、痰气互结→半夏厚朴汤、寒饮咳逆→苓甘五味姜辛汤/射干麻黄汤、太少两感→麻黄附子细辛汤、阳虚水泛→真武汤）
- 分析 prompt 末尾 JSON 输出要求追加约束：推荐方剂必须为经方、每个元素只一组 name/composition/modification/indication 键、**严禁重复键名或把多个方子塞进一个对象的字符串里**（之前模型把主方+备选方塞进同一对象导致解析串味）

### 2. 推荐方解析/导入清洗（修「英文乱码当成一味药」）
- 后端 `ai_diagnosis_service._clean_herb_string`：去除 JSON 键名（composition/modification/name…）、引号、括号与英文，仅保留含中文的「药名+剂量」片段，应用于 `recommended_formulas` 的 name/composition/modification/indication
- 前端 [VisitCard.vue](file:///home/debian/tcm-doctor/frontend/src/components/VisitCard.vue) 新增 `cleanComposition`，并在 `parseAiFormulas` 三个分支（JSON / 主方兜底 /【推荐方剂】）对组成、加减、方名统一清洗，详情与「带入开方」预览不再出现英文键名
- 前端 [PrescriptionEditor.vue](file:///home/debian/tcm-doctor/frontend/src/views/prescription/PrescriptionEditor.vue) `applyAiFormula` 带入开方时仅保留含中文的药名 token，杜绝 `composition:`/`modification:` 等英文被当成一味药导入

## 2026-10-30 — 患者模块决策辅助升级 + 随访提醒

### 1. 患者列表多维筛选 + 聚合信号（不动 schema）
- 后端 `list_patients` 新增筛选参数 `constitution_type`（体质）/ `tag`（标签）/ `has_allergy`（有无过敏）/ `improvement`（最近改善）/ `sort_by & order`（按最近就诊排序）；返回追加聚合字段 `last_visit_date` / `days_since_visit` / `last_improvement` / `active_status`（在治 / 停诊 / 未复诊 / 新诊），其它接口返回为 `null`，无副作用
- 前端 [PatientList.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/PatientList.vue) 顶部筛选栏（搜索 + 体质 / 标签 / 过敏 / 最近改善下拉 + 排序 + 重置）；表格新增「最近就诊 / 距今天数（超 30 天标红）/ 最近改善 / 状态（彩色）/ 风险（过敏🔴·不遵医嘱⚠️）」列；窄屏卡片同样补充最近就诊与状态 / 风险信号

### 2. 患者详情「健康速览」卡 + 病情跟踪关联开方对比
- 概览页顶部新增 🩺 健康速览卡：体质大卡 + BMI / 身型 + 过敏史告警（红 / 绿）+ 标签色块，一眼抓住关键风险
- 病情跟踪每张随访卡片关联展示其对应就诊的处方（方名 / 疗程 / 剂数 / 味数），形成「上次开药方 → 本次反馈」并排对比，便于判断原方案是否有效

### 3. 随访提醒（诊断 / 处方用药后自动生成，工作台待办提醒）
- 新增 `followup_reminders` 表与路由 `/api/v1/followup-reminders`（列表 / 创建（手动）/ 标记完成·取消·改期 / 删除），由 `Base.metadata.create_all` 启动时自动建表，无需手写迁移；`FollowUpReminder` 已注册进 `app/models/__init__` 以确保建表与关系解析
- 开方时（填写疗程天数 `treatment_days` 或表单「建议复诊日期」）自动生成待回访提醒：应回访日期 = 就诊日 + 疗程天数（或医生指定日期），备注标注来源处方
- 工作台 [Dashboard.vue](file:///home/debian/tcm-doctor/frontend/src/views/dashboard/Dashboard.vue) 待办新增「📞 待回访 N 人」，列出逾期 / 到期患者（姓名 / 日期 / 备注，逾期标红），点击直达患者详情
- `/stats/dashboard` 新增返回 `pending_followups`（逾期 + 今日应回访计数）与 `followup_reminders` 列表
- 患者详情「病情跟踪」tab 新增「⏰ 随访提醒」卡片：列出该患者全部提醒（状态 / 逾期高亮），可手动添加（日期 + 备注）/ 完成 / 取消 / 删除

### 4. 设计决策（未落地代码，仅记录）
- 症状矩阵 / 趋势：**症状不做字典、也不硬编码清单**——临床上症状词汇近乎无限且一次多症，随访表单改为「自由录入多行症状 + 严重度 0–3」；严重度与改善程度（明显好转 / 好转 / 稳定 / 反复 / 加重）保持系统固化，不开放自定义，以免破坏跨患者 / 跨时间可比性与现有决策逻辑

### 5. 问诊十问展示与二次编辑回填修正（修 bug）
- 原「问诊十问详情」只展示辨证结论（偏性画像 / 判据解析 / 方域提示），**看不到当时选了哪些原始选项**；现新增「原始问诊十问」区块：逐问展示所选选项标签 + 自填内容，并就地补充该选项对应的判据解析结果（`《问xx》…` 按题匹配），做到「每一问出选项、再补充该选项有可能的结果」
- 抽公共题库 [tenAspectsQuestions.ts](file:///home/debian/tcm-doctor/frontend/src/utils/tenAspectsQuestions.ts)，供十问面板与详情展示共用，避免题干 / 选项重复维护
- [TenAspectsPanel.vue](file:///home/debian/tcm-doctor/frontend/src/components/TenAspectsPanel.vue) 新增 `initial` 属性（回填 answers / notes / result）：编辑**已有就诊**的十问时，自动恢复上一次所选选项与辨证结论，不必从头重选
- 后端 `get_inquiries` 增加 `visit_id` 过滤，供编辑页按就诊精确取回该次十问记录用于回填
- [VisitRecord.vue](file:///home/debian/tcm-doctor/frontend/src/views/patient/VisitRecord.vue) 编辑既有就诊时拉取该 visit 的十问记录传入面板

## 2026-10-30 — 图片手势缩放 + 移动端/开发服务器网络适配

### 1. 图片预览改用手势缩放组件
- 新增 [PinchImage.vue](file:///home/debian/tcm-doctor/frontend/src/components/PinchImage.vue) 与 [image.ts](file:///home/debian/tcm-doctor/frontend/src/utils/image.ts)，支持触屏双指缩放 / 拖拽查看大图，替代原 `el-image` 预览
- 覆盖就诊卡片（舌苔 / 面色 / 化验单）[VisitCard.vue](file:///home/debian/tcm-doctor/frontend/src/components/VisitCard.vue)、问诊对话 [DiagnosisChat.vue](file:///home/debian/tcm-doctor/frontend/src/views/diagnosis/DiagnosisChat.vue)、患者列表图片等处的图片预览

### 2. 开发服务器网络可访问 + 移动端导航微调
- [vite.config.ts](file:///home/debian/tcm-doctor/frontend/vite.config.ts) `server.host = true`；[package.json](file:///home/debian/tcm-doctor/package.json) `dev:backend` 加 `--host 0.0.0.0`，便于手机 / 局域网真机调试
- [MainLayout.vue](file:///home/debian/tcm-doctor/frontend/src/layouts/MainLayout.vue) 移动端隐藏「首页」面包屑、header 左区 `min-width:0` 防溢出

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

### 8. 导入/导出接口全量加鉴权（游客不可访问）
- 梳理后端全部 `import/export` 路由：发现 5 个 GET 导出接口此前**未鉴权**（药材 / 腧穴 / 经典方 / 针灸方 / 知识库），游客可直接导出全量数据（含药材性味、经典方等）。
- 已为这 5 个导出接口统一加 `Depends(get_current_user)`，与对应导入接口一致：**登录用户（任意角色）可导出，游客返回 401**。
- 导入接口（药材/腧穴/经典方/针灸方/知识库/数据备份）此前已带 `get_current_user`，且写操作受 `require_admin_for_writes` 中间件再卡 admin；数据备份的导入/导出本就仅管理员。故「导入导出一律不放游客」已闭合。
- 验证：`py_compile` 通过；TestClient 确认 5 个导出游客均 401、登录后 200，幂等导入仍正常。