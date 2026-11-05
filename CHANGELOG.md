# 开发日志 CHANGELOG

## 2026-11-05 — B「完整病历导出 + 自动备份」/ E「基础数据包开箱」落地

### 决定
按评估清单先修 B 与 E：让「留存」这件事从「只能靠手动导出整库」变成「按患者带走 + 自动留快照」，
并让新装/克隆后的空框架能**一键装好参考知识库**，不再逐类上传 JSON。

### B1 / B2 按患者导出完整病历
- 新增 `backend/app/medical_record.py`：聚合患者基本信息、体质辨识、全部就诊（四诊 / 舌脉 / 中医病名证型治法 / AI 辅助辨证）、
  处方及药味·配穴·针剂明细、十问、疗效随访、复诊提醒；默认不含 base64 图片，`include_images=true` 时可带上。
- 新增 `GET /patients/{id}/medical-record?format=json|html&include_images=...`：需 `patient:read`，写审计日志；
  JSON 为结构化存档，HTML 为自包含 A4 打印页（可另存 PDF），全文转义防注入，含体质评分、照片、复诊提醒及
  「未关联到本患者就诊」的处方，避免历史脏数据被静默漏掉。
- **修复**：中文患者名放进 `Content-Disposition` 会触发 `UnicodeEncodeError`（HTTP 头仅支持 latin-1），
  改为 ASCII `filename` 兜底 + RFC 5987 `filename*`。
- `PatientDetail.vue` 页头新增「导出完整病历」：弹窗选格式与是否含照片，JSON 下载、HTML 打开打印窗口。

### B3 自动备份
- 新增 `backend/app/auto_backup.py`：用 `sqlite3.Connection.backup()` 做在线快照（含 WAL），先写临时文件再原子改名并校验 SQLite magic；
  守护线程启动时先留一份、之后按间隔执行，按保留份数清理（至少保留 1 份）。
- `.env` 可配 `BACKUP_AUTO_ENABLED / BACKUP_INTERVAL_HOURS / BACKUP_KEEP / BACKUP_DIR`（默认开启、24 小时、保留 7 份、
  落在数据库同目录 `backups/`）；界面改动另存 `backups/auto_backup.json`，改完立即重启调度线程。
- 新增 `GET /backup/auto/status`、`PUT /backup/auto/config`、`POST /backup/auto/run`、`GET /backup/auto/download/{name}`；
  下载文件名走严格白名单正则，杜绝路径穿越；`main.py` lifespan 启停调度线程。
- `Settings.vue` 新增「自动备份」卡片：开关 / 间隔 / 保留份数、立即备份、快照清单与下载。

### E1 基础数据包一键导入
- 新增 `backend/app/template_bundle.py`：manifest 驱动（`schema_version`、分层 `depends_on` 拓扑排序、自动补齐依赖层）、
  逐文件 `sha256` 与 `count` 校验、zip 条目路径穿越与解压体积限制、类型必须落在 `TEMPLATE_TYPES` 白名单；
  预检与正式安装共用同一份 plan，预检为 `dry_run` 不落库，正式安装复用幂等 upsert。
- 新增 `GET /templates/bundles`（可用包 + 内容库是否为空）、`POST /templates/bundle/preview`、`POST /templates/bundle/install`；
  可用 `TCM_BASE_PACKAGE` 指向随安装包分发的数据包，也支持上传 `.zip`。
- **修复两个既有缺陷**：`/templates` 未登记 `DOMAIN_PERMS` 导致模板接口对所有人 fail-closed 403；
  `templates.router` 从未 `include_router` 导致整套模板导入/导出接口 404。现登记为 `("*", "system:write")` 并注册路由。

### E2 空框架引导
- 新增 `frontend/src/components/BasePackageInstaller.vue`：选包 / 上传、分层勾选、预检结果逐文件回显、确认后安装。
- `Dashboard.vue` 在内容库为空时显示首次引导（可用 `localStorage` 关闭），`Settings.vue` 数据管理卡片加入口。
- `templates/README.md` 同步去掉「分层 bundle 规划中」的过期说明。

### 验证
- 后端 `pytest -q` **49 passed**（新增 `test_medical_record` / `test_auto_backup` / `test_template_bundle` 共 15 项）。
- 前端 `vue-tsc --noEmit` 与 `npm run build` 退出码 0（仅有 `@vueuse/core` 的第三方 `INVALID_ANNOTATION` 提示）。
- 用真实 `templates/releases/tcm-base-core.zip` 实跑：5 个文件 sha256 全通过、2217 条、顺序 `core → formulas → books`；
  只选 `formulas` 时自动补 `core`。

## 2026-11-05（续）— AI 辨证读既往疗效 / 复诊对比

### 决定
评估中 P0 项：原 AI 辨证只把**当次**四诊拼进 prompt，完全忽略既往就诊、随访疗效与复诊对比。
本次让 AI 在辨证时能看到该患者既往病历摘要，复诊时对比证型/舌脉变化、沿用有效思路、规避无效方案。

### 改动
- `backend/app/medical_record.py` 新增 `summarize_prior_history(record, max_visits=10, max_followups=8)`：
  从 `build_record` 结果提炼「既往病史与疗效回顾」文本（不含图片、限条数，控制 token），逐诊列出主诉/病名证型治法/处方与药味、AI 辨证摘要，并附疗效随访（改善程度+反馈）。
- `backend/app/services/ai_diagnosis_service.py`：
  - `analyze` / `analyze_stream` 新增 `patient_id` 参数；`DiagnosisAnalyzeRequest` 增加 `patient_id` 字段。
  - 复用 `build_record` 生成既往摘要，注入到四诊辨证 user_message 末尾，并附「复诊参考要求」（对比证型/舌脉/疗效趋势、沿用有效思路、规避既往无效/不适方案）。
  - 对话式 `chat` / `chat_stream` 也把既往摘要作为系统上下文注入（已有 `patient_id`）。
  - 无 API Key 的本地规则辨证分支同样罗列既往病史（明确标注未据此动态调整），保证未配置 Key 时功能也可见。
  - 新增 `_prior_history_block` 共享方法，失败非关键忽略。
- `backend/app/routers/diagnosis.py`：`/diagnosis/analyze` 与 `/analyze/stream` 透传 `patient_id`。
- `frontend/src/views/patient/VisitRecord.vue`：辨证请求 payload 带上 `patient_id`，触发既往注入。

### 验证
- 后端新增 `tests/test_ai_prior_history.py`（4 项，含摘要内容、空记录、注入与无 patient_id 不注入），全量 `pytest` **53 passed**。
- 前端 `vue-tsc --noEmit` 与 `npm run build` 退出码 0。

## 2026-11-05（续二）— 索引与健壮性（高频查询索引 + 乐观锁）

### 动机
`migrations.py` 没有 `CREATE INDEX`，存量库不会自动补索引；数据量增长后就诊/处方/随访按患者查询会变慢。
此外缺乐观锁，并发编辑同一患者/就诊/处方可能静默覆盖彼此的改动。

### 改动
- **模型层索引**（`__table_args__`）：新库由 `create_all` 直接落地
  - `visits(patient_id, visit_date)`、`prescriptions(patient_id, visit_id)`、`followups(patient_id, visit_id)`、
    `inquiry_records(patient_id, visit_id)`、`conversations(patient_id, last_message_at)`、`patients(deleted_at)`。
- **迁移 0018**：存量库用 `CREATE INDEX IF NOT EXISTS` 幂等补齐上述索引；
  并为 `patients/visits/prescriptions/followups` 加 `version` 列（`INTEGER NOT NULL DEFAULT 1`）。
- **乐观锁**：对 `Patient/Visit/Prescription/FollowUp` 启用 SQLAlchemy 原生 `version_id_col`；
  并发提交时版本不符自动抛 `StaleDataError`。
  - 关键护栏：`_sync_model_columns` 跳过 `version` 列（否则会被建成可空列，导致所有 `UPDATE` 因 `version = NULL` 判定失效）。
  - `main.py` 新增全局 `StaleDataError → 409` 处理器，返回「该记录已被他人修改，请刷新后重试」。
- **前端** `utils/api.ts`：拦截器对 409 给出明确 warning 提示，便于用户感知并发冲突。

### 验证
- 新增 `tests/test_indexes_optimistic.py`（4 项）：索引存在、version 列存在、正常更新版本自增、双会话并发冲突抛 `StaleDataError`。
- 后端全量 `pytest` **57 passed**；前端 `vue-tsc 0`、`npm run build 0`。

## 2026-11-05（续三）— 处方防篡改 / 电子签名

### 动机
处方是医疗留存的核心凭据，原系统对处方内容无任何防篡改与签名留痕，存在被事后改动而难以追责的隐患。

### 改动
- **内容哈希基线**：`Prescription` 新增 `content_hash` 列；开方/编辑时由 `compute_prescription_hash()` 对临床内容
  （药味/剂量/配穴/针剂/方名/治法/剂数/医嘱等，且**不含 status/时间戳**）做 SHA-256 规范化哈希；
  存量处方由迁移 `0019` 回填基线，使其后续被改动即可检出。
- **电子签名**：新增 `signed_by / signed_by_id / signed_at / signature` 列。
  `POST /prescriptions/{id}/sign` 由当前登录医师签名，令牌 = `SHA256(content_hash | 签名人 | 时间 | signing_secret)`
  （密钥可由环境变量 `TCM_SIGNING_SECRET` 覆盖），将签名与签署时刻的真实内容绑定，杜绝伪造或挪用到其它处方。
- **篡改/失效判定**（模型派生属性，实时计算）：
  - `tampered`：基线存在但当前重算不一致 → 内容被改动（含外部直接改库）。
  - `signature_valid`：令牌与其签署时基线一致；若签名后内容被改，令牌失效需重签。
  - 编辑处方会使既有签名失效（清空签名，须重新签署）。
- **校验端点** `GET /prescriptions/{id}/verify` 返回 `tampered/signed/signature_valid` 及基线与实时哈希。
- **前端** `PrescriptionEditor.vue`：编辑态页头新增完整性徽标（已签名·内容完整 / 签名失效·需重签 / 未签名 / ⚠内容已被篡改）
  与「电子签名」按钮；签名或保存后实时刷新状态。`Prescription` 类型补充相应字段。

### 验证
- 新增 `tests/test_prescription_integrity.py`（5 项）：哈希稳定性、签名置位与有效、编辑后签名失效、外部篡改检出、已取消拒绝签名。
- 后端全量 `pytest` **60 passed**；前端 `vue-tsc 0`、`npm run build 0`。

## 2026-11-05（续四）— 备份加密（P1）+ 检索索引（P2）

### 动机
自动/手动备份、导出均为**明文 SQLite**（含患者隐私），离线拷贝或备份介质丢失即泄露；患者按姓名/电话检索无索引。

### 改动
- **可选备份加密** `app/services/backup_crypto.py`：设置 `TCM_BACKUP_PASSPHRASE` 后用 Fernet 加密。
  - 密钥由口令 SHA-256 确定性派生；密文文件带 `TCMENC1\n` 魔数头，**旧明文备份仍可恢复（向后兼容）**，未设口令则不加密（避免遗忘口令导致不可恢复）。
  - `auto_backup.create_backup` 写快照时按需加密；`routers/backup.py` 导出时加密、导入时解密（解密失败给出明确提示：需配置相同口令）。
  - `/backup/auto/status` 新增 `encryption_enabled` 与 `encryption_note`，便于管理员确认加密状态。
  - `requirements.txt` 固定 `cryptography==43.0.0`。
- **检索索引**：`patients(name)`、`patients(phone)` 模型 `__table_args__` + 迁移 `0020`（`CREATE INDEX IF NOT EXISTS`）补齐，加速患者检索/去重。

### 验证
- 新增 `tests/test_backup_crypto.py`（6 项）：加解密往返、明文兼容、无口令时不加密、无口令解密报错、自动备份加密可恢复、无口令自动备份为明文。
- 后端全量 `pytest` **66 passed**；前端无需改动（加密经环境变量配置）。

## 2026-11-05（续五）— 业务闭环补全：发药逐项核对（P1）

### 动机
原「发药」仅弹一次确认即扣库存、改状态，无逐项核对环节，存在错发/漏发风险；而库存扣减依赖处方明细，前端却未呈现核对清单。

### 改动
- `frontend/src/views/prescription/PrescriptionList.vue`：将「发药」从单次 `ElMessageBox.confirm` 升级为**逐项核对对话框**。
  - 列出处方全部明细（药味 / 配穴 / 针剂），逐项 `el-checkbox` 勾选；提供「全部核对」一键勾选。
  - 确认按钮在未全部核对时禁用，并显示 `已核对 n/总数`；确认后才调用 `PUT /prescriptions/{id}/dispense`（后端既有扣库存逻辑不变）。
- 后端无需改动（发药校验/扣库存已由 `dispense` 端点保证）。

### 验证
- 前端 `vue-tsc 0`、`npm run build 0`。后端既有 `pytest` 全量通过（发药相关测试覆盖扣库存/冲红）。

## 2026-11-05（续六）— 收费单闭环（P1 业务闭环：收费）

### 动机
原系统「开方 → 发药」之间缺收费环节：有处方总价却无收费单、无收款留痕、无收据，钱与账都不闭环。
本次按「先做收费单」落地：**开方后生成收费单 → 收款记录 → 打印收据**，与发药/库存解耦（库存仍由发药扣减，收费只管钱）。

### 后端
- **新模型** `Charge`（`app/models/billing.py`）：单号、关联处方/患者/就诊、金额快照（应收/减免/应付/实收）、
  收款方式、状态（待收费/已收费/已退费）、收银员与收款/退费时间、退费原因；含状态/时间/患者索引。
  新表由启动 `create_all` 自动建，无需改表迁移。
- **接口** `app/routers/billing.py`（`/api/v1/billing`，含对应 schema）：
  - `POST /charges` 开单（可「开单即收」）；同一处方已有待收费单时返回原单，避免重复开单；减免不得超过原价、实收不得小于应付。
  - `GET /charges` 列表（状态/患者/处方/日期筛选 + 分页）、`GET /charges/{id}` 详情（含处方明细快照，供收据）。
  - `POST /charges/{id}/pay` 收款、`POST /charges/{id}/refund` 退费、`GET /charges/stats/summary` 金额汇总。
- **权限**：新增 `billing:read/billing:write` 权限点、角色默认集（医生/药房）、`/billing` 路由域；
  迁移 `0022` 为存量账号补齐 billing 并把空权限集按角色默认集显式化（解决前端 `auth.can` 只看显式数组导致「后端放行前端看不到入口」）。
- **清空数据**：`reset_data` 删除顺序加入 `Charge`（收费单引用处方/就诊/患者，须先清，避免外键冲突）。

### 前端
- 新组件 `ReceiptDialog.vue`（收据：单号/患者/项目明细/应收-减免-实收/找零/收款方式/收银员，打印时仅保留收据区）、
  `ChargeDialog.vue`（处方列表一键开单+收款，成功后弹收据）。
- `PrescriptionList.vue`：操作列/移动卡片增加「收费」按钮（`billing:write` 才显示）。
- 新页面 `views/billing/BillingView.vue`：金额汇总卡、状态/患者/日期筛选、分页列表、收款、退费、收据打印；
  路由 `/billing` 与「处方管理 → 收费管理」菜单接入（按 `billing:read` 显隐）。
- `store/auth.ts` 域映射、`types/index.ts` 新增 `Charge/ChargeStats`。

### 验证
- 新增 `tests/test_billing.py`（6 项：待收费→收款、开单即收、少收拒绝、退费、重复开单、列表与汇总）
  与 `tests/test_billing_permission_migration.py`（1 项：权限补齐/幂等）。
- 后端全量 `pytest` **73 passed**；前端 `vue-tsc 0`、`npm run build 0`。

## 2026-11-05（续七）— 挂号台：挂号 → 就诊 → 开方 → 收费 闭环

### 动机
此前流程直接「患者 → 开方」，缺前台挂号（排队号/挂号费/就诊状态）环节；收费与就诊未串联。
本次补齐**挂号（分诊登记）**，使「挂号 → 就诊 → 开方 → 收费」形成完整业务闭环。

### 后端
- **Visit 模型**新增挂号字段：`queue_no`(当日排队号)、`registration_fee`(挂号费)、`registered_at`(挂号时间)、
  `registrar_id`(挂号员)、`department`(科室/接诊医师)、`status`(待诊/已接诊/已完成/已取消)；并加索引。
- **Charge 模型**：`prescription_id` 改为**可空**并新增 `kind`(prescription/registration)，支持「挂号费」等非处方收费。
- **路由** `app/routers/registration.py`（`/api/v1/registration`，域登记 `patient:read`/`patient:write`）：
  - `POST /` 挂号登记：选择/新建患者 → 创建就诊(待诊)+排队号 → 记录挂号费（可开单即收，生成 `kind=registration` 收费单）。
  - `GET /queue` 今日挂号队列（状态筛选）、`GET /{id}` 详情(含收费单)、`PATCH /{id}` 改状态/科室、`POST /{id}/call`(接诊)、`POST /{id}/complete`(完成)。
  - 共享 `app/services/billing_service.create_charge`：处方收费与非处方收费（挂号费）共用，统一金额量化/减免校验/重复开单复用/开单即收。
- **权限**：`DOMAIN_PERMS` 登记 `/registration`；`billing` 域与 `billing:read/write` 权限点（前序已加）。
- **迁移 0023**：存量库 `charges.prescription_id` 为 NOT NULL，SQLite 不支持改可空，故重建表（保留数据与索引/唯一约束）；新库由 `create_all` 直接建为可空。

### 前端
- **挂号台** `views/registration/RegistrationView.vue`：左侧挂号登记（患者检索/新建、科室、挂号费、收款方式/实收），
  右侧今日队列（排队号/患者/挂号费/收费状态/就诊状态 + 接诊/完成/收挂号费/退号），「接诊」跳转 `/prescriptions/new?visit_id=&patient_id=` 闭合链路。
- **收费管理** `BillingView.vue`：增加「类型」列(处方/挂号费)与类型筛选；列表接口支持 `kind` 参数。
- 路由 `/registration` + 菜单「病号管理 → 挂号台」（`patient:write` 显隐）；`types/index.ts` 新增挂号相关类型与 Visit 挂号字段。

### 验证
- 新增 `tests/test_registration.py`（6 项：新建患者+挂号费即收、选择患者免挂号费、队列与状态流转、挂号费入收费单可退费、只读账号 403、迁移 0023 可空化）。
- 后端全量 `pytest` **79 passed**；前端 `vue-tsc 0`、`npm run build 0`。

## 2026-11-04 — 作废入口收敛到详情弹窗，避免列表误点

### 决定
列表操作列里「作废」与「审核 / 发药」紧挨，容易误点；且作废会影响库存与账目（已发药处方作废会退回库存并生成冲红流水），不宜作为列表高频操作。用户要求：**作废入口只保留在处方详情弹窗**。

### 改动（`PrescriptionList.vue`）
- 移除表格操作列的「作废」按钮、移动端卡片的「作废」按钮。
- **保留详情弹窗 footer 的「作废处方」**（`已取消` 状态与游客只读时隐藏），且仍带 `ElMessageBox` 二次确认；已发药处方的确认文案明确提示「退回库存并生成冲红记录」。
- 后端 `POST /prescriptions/{id}/void` 接口及冲红逻辑不变，仅调整前端入口位置。

### 验证
- 前端 `vue-tsc --noEmit` 退出码 0、`npm run build` 退出码 0、lint 0 错误；后端 `pytest -q` 34 passed（本次仅前端改动）。

## 2026-11-04 — 搜索改动回退：除 300ms 防抖外，全部恢复原状

### 决定
用户实测评估后认为「边输边出结果」等搜索改造收益不足、且担心抖动与资源占用，决定**不做**主列表即时搜索，也不做「今日就诊患者提示 / 名字提示只给 2~3 条」两个方案。要求：**除防抖优化外，搜索相关改动全部恢复到 `9d22153` 之前的状态**。

### 已撤销（相对 `9d22153`）
- 后端 `routers/patient.py`：`list_patients` 的 SQL 分页快路径、`_enrich_patient` / `_load_related` 辅助与 500 分块，恢复为原来的全量聚合 + Python 切片分页；删除 `tests/test_patient_list_fastpath.py`。
- 前端 `utils/search.ts`：移除 `createRequestGuard`（竞态守卫）、`getAllHerbs` 共享药材缓存、`invalidateHerbCache`，仅保留 `debounce`。
- `HerbSelector.vue` / `PrescriptionEditor.loadHerbList()`：恢复各自 `api.get('/herbs')`；`HerbList.vue` 移除缓存失效调用。
- `KnowledgeSearch.vue`：移除知识检索的竞态守卫，恢复原 `doSearch`。
- 处方列表/编辑器：患者远程搜索的竞态守卫移除，`page_size`（100 / 50）与搜索口径、结果条数**一律保持原样**。

### 仅保留
- `frontend/src/utils/search.ts` 的 `debounce()`；处方列表、处方编辑器两个患者下拉的 `:remote-method` 改指向 300ms 防抖包装（`debouncedSearchPatients`）。**只减少逐键请求，不改变任何搜索行为、口径或结果数量**。

### 未受影响（其它修复完好）
作废/冲红入口、患者删除守卫、患者软删除、编辑处方就诊归属校验、`#患者id` 标注、M1 Cookie 登录、审计修复等全部保留。

### 验证
- 后端 `pytest -q` 34 passed；前端 `vue-tsc --noEmit` 与 `npm run build` 退出码 0。

> 下一条 `9d22153` 的「第一批优化」记录仅作历史留存，其中大部分改动已按本条回退。

## 2026-11-04 — 搜索性能专项：全项目盘点 + 第一批优化（防抖/竞态/共享缓存/SQL 真分页）

### 盘点结论（前后端全量调研，只读）
**后端**（SQLite + SQLAlchemy 2.0）：
- 所有模糊搜索都是 `LIKE '%q%'`（`contains`/`ilike`），**前置通配必然全表扫描**；全库 **0 处 FTS5 / 全文索引 / trigram**，`migrations.py` 也没有任何建索引机制（`Base.metadata.create_all()` 对存量库不生效）。被搜索的热门列（patients.name/phone、herbs.name/aliases/efficacy、stock_items.name/spec、knowledge_entries.title/content、operation_logs 文本列）**全部无索引**——且 `%q%` 即使加 B-tree 索引也用不上。
- 最重的三处：`patient.py:list_patients`（整表 patients + 全量 visits/followups 进内存做聚合/筛选/排序，Python 切片「假分页」）、`herb.py:list_herbs`（整表 + Python 子串/异名过滤）、`ai_diagnosis_service._retrieve_context` / `_check_safety_in_reply`（每次 AI 请求全表知识库 `contains`；每次 AI 回复全表 Herb 做 Python 子串比对）。
- 其余内存过滤：`stock.py` overview / suppliers、`system_log.export_logs`（无 limit）、`knowledge.export`；`stats.py` 首页低库存存在逐物品 `sum()` 的 N+1。
- 语义检索默认关闭（`ENABLE_SEMANTIC_SEARCH=false` 三处配置）；开启时 Chroma 走 HNSW 没问题，但 `knowledge.search` 与 RAG **不判断开关、无条件叠加**一次 SQL 全表扫描。
- 正面范式（保留）：`stock.list_items/list_transactions`（ilike 下推 + 真分页 + `_item_agg` group by）、`knowledge.list_entries`（count + substr 预览 + offset/limit）、`prescription.list_prescriptions`（joinedload + `in_()` 批量补名）、报表 SQL 聚合。

**前端**：
- 防抖**仅 1 处**（BookLibrary 300ms），**0 处**请求竞态保护（无 AbortController / 无请求序号），**0 处**搜索结果缓存；3 个逐键 `remote-method`（处方列表患者筛选、开处方患者选择、HerbSelector 本地过滤）慢响应会直接覆盖新结果。
- **最典型浪费**：处方编辑器每味药渲染一个 `HerbSelector`，每个实例 `onMounted` 各拉一次全量 `/herbs` → N 味药 = N 个并发请求；编辑器自身 `loadHerbList()` 又拉第 N+1 份。
- 大量页面无分页全量拉取后前端 `slice` 假分页（Overview / SupplierManage / Check / Reports / PatientDetail 一次并发 6 个无分页接口）；`Overview` 后端已收 `search` 却又在前端再 filter 一遍。

### 本轮实施（第一批：不改变任何业务语义，纯性能）
- 新增 `frontend/src/utils/search.ts`（模块级单例）：
  - `debounce()` 防抖、`createRequestGuard()` 请求序号守卫（只采信最后一次响应，比 AbortController 更稳妥：不产生取消请求的错误提示）。
  - `getAllHerbs()` 全量药材共享缓存（in-flight Promise 并发去重）+ `invalidateHerbCache()`。
- **三处搜索接入**：`PrescriptionList.vue` / `PrescriptionEditor.vue` 的患者远程搜索改为 300ms 防抖 + 竞态守卫；`KnowledgeSearch.vue` 的知识检索加竞态守卫（语义检索慢，结果易乱序）。
- **消除 N 个并发全量请求**：`HerbSelector.vue` 与 `PrescriptionEditor.loadHerbList()` 共用 `getAllHerbs()`；`HerbList.vue` 在新增/编辑/删除/导入药材后调用 `invalidateHerbCache()` 保证新鲜度。
- **后端 `list_patients` 快路径**：默认/仅搜索/体质/过敏筛选时，把 `count()` 与 `offset/limit` 下推 SQL，只给当前页患者补就诊/随访派生字段；`tag` / `improvement` / `sort_by=last_visit_date` 这类依赖聚合结果的筛选仍走原全量路径，**语义完全一致**。抽出 `_enrich_patient` / `_load_related` 复用，关联查询按 500 分块规避 SQLite `IN` 参数上限。
  - 效果：患者列表从 O(全部患者 + 全部就诊 + 全部随访) 降为 O(1 次 count + 一页患者 + 一页关联)；开处方从 N 次 `/herbs` 降为 1 次。

### 验证
- 新增 `tests/test_patient_list_fastpath.py`：真分页、派生字段（在治/停诊/新诊）、全量路径（标签/改善/最近就诊排序）与快路径覆盖一致性、软删除过滤。
- 后端 `pytest -q` **37 passed**；前端 `vue-tsc --noEmit` 退出码 0、`npm run build` 退出码 0；改动文件 lint 0 错误。

### 待拍板（第二批，涉及语义/架构，本轮未动）
1. **SQLite FTS5 全文索引**（收益最大）：覆盖知识库长文本、操作日志、患者/药材/物品；中文需选 tokenizer（trigram）并建触发器同步；同时要新增「存量库建索引」的迁移机制，否则老库吃不到。
2. 把 `herb.list_herbs`、`stock.overview/suppliers` 的「整表 + Python 过滤」下推 SQL；`export_logs` / `export_knowledge` 强制 limit。
3. AI 侧收敛：`enable_semantic_search=true` 时跳过几乎不可能命中的整段主诉 SQL `contains`；安全校验由「全表 Herb 子串比对」改为「从回复抽候选药名 → 一次 `in_()` 查询」。
4. 前端假分页/全量拉取改造（Overview / SupplierManage / Check / Reports / PatientDetail），按 `ItemManage.vue` 已有范式改后端检索 + tab 懒加载。
5. `stats.py` 首页 N+1 改一次 `GROUP BY`（非搜索，但属同一批性能债）。

## 2026-11-04 — 前端「作废」入口 + 修复「改患者名致处方归属错乱」数据一致性 bug

### 1 · 前端接入作废/冲红（承接上一轮 `POST /prescriptions/{id}/void`）
- `PrescriptionList.vue`：表格操作列、移动端卡片、详情弹窗 footer 三处新增「作废」按钮（`已取消` 状态不显示，游客只读隐藏）；`已发药` 作废的确认文案明确提示「退回库存并生成冲红记录」；成功后关闭详情弹窗并刷新列表。
- 列表/卡片/详情的患者名后追加 `#患者id` 小标注，区分同名患者（如两个「张三」）——这正是用户实测中「分不清是 1 号还是 2 号张三」的直接可见性改进。

### 2 · 修复「编辑处方时改患者名 → 处方归属错乱」的真实 bug
用户实测：删 1 号张三（归档）后，编辑其处方把患者名改成 2 号张三也能保存，但 2 号张三的就诊记录为空、列表归属混乱。

- **根因**：`PrescriptionEditor.vue` 里 `patient_id`（患者下拉）与 `visit_id`（自由数字输入框）**相互独立**。把处方改挂到 2 号患者时 `visit_id` 仍指向 1 号患者的就诊 → 处方 `patient_id=2` / `visit_id=1`，列表按 `patient_id` 实时算的 `patient_name` 显示成 2 号，而就诊记录按各自 `visit` 关联，2 号自然查不到（`Prescription` 模型本身无 `patient_name` 字段，`list_prescriptions` 按 `patient_id` 关联患者算出）。
- **后端防线**（`routers/prescription.py` `create_prescription` / `update_prescription`）：新增校验「`visit_id` 对应的就诊必须属于 `patient_id` 对应的患者」，否则返回 `400 就诊记录不属于该患者`。任何绕过前端的调用也无法制造错挂。
- **前端联动**（`PrescriptionEditor.vue`）：
  - `visit_id` 由自由数字输入改为「所选患者的就诊记录」下拉（按 `patient_id` 加载 `/patients/{id}/visits`）；切换患者自动清空就诊并重拉，编辑态回显、辨证页带参进入均预加载。
  - **编辑态锁定患者与就诊**（`:disabled="!!prescriptionId"`）：已开处方不再允许改挂到别的患者——医疗记录的归属应在开方时确定，事后换患者会破坏就诊/库存/审计链路。
  - 提交新增「请选择就诊记录」必填校验，`visit_id` 默认值由 `1` 改为 `null`（避免默认挂到 1 号就诊）。
- 说明：用户问「改名把处方挪到新患者」是否算 bug——**改显示名本不该重挂处方**（数据完整性正确），但旧编辑器允许「换 `patient_id` 却不换 `visit_id`」确实会产生脏数据，故按上述方式修复；跨患者重挂处方仍不支持，也不建议。

### 验证
- 新增 `tests/test_prescription_integrity.py`：`create`/`update` 两条路径均验证「就诊不属于该患者 → 400」。
- 后端 `pytest -q` 全量 **34 passed**；前端 `npm run build` 退出码 **0**（`vue-tsc` 亦通过）；改动文件 lint 0 错误。

## 2026-11-04 — 患者删除守卫：有就诊/处方记录的患者禁止删除（杜绝误删医疗记录）

接上一轮软删除（B）后，用户实测发现：已发药处方不会因删患者而丢失（软删除不物理删处方，处方仍正确归属原患者），但**期望“已审核/已发药的患者根本不该点删除就删掉”**。在软删除基础上新增一道硬守卫：

### 改动（`routers/patient.py` `delete_patient`）
- 若患者存在**任意就诊记录（Visit）或任意处方（Prescription，含已开/已审核/已发药）**，直接返回 `400 不可删除，医疗记录须保留`，拒绝删除。
- 仅“零就诊、零处方”的患者才允许归档（标记 `deleted_at`）。
- 仍有 `delete_prescription` 负责未发药处方（已开/已审核）的删除；已发药处方须经 `POST /prescriptions/{id}/void` 作废冲红，二者互不冲突。

### 关于“改名把处方挪到新患者”的说明
处方真正绑定的是 `patient_id`（外键），前端处方表单上改“患者名字”只是改显示字段，并不会把处方重新挂到另一个患者——这反而是数据完整性正确的表现（处方归原患者，即便原患者已归档仍可见）。如需真正把一个处方改挂到别的患者，属跨患者重挂、易破坏就诊/库存归属，当前不支持，也不建议。

### 验证
- 重写 `tests/test_patient_soft_delete.py`：`test_delete_patient_with_records_is_blocked`（有记录→400、记录保留）、`test_delete_patient_without_records_is_archived`（零记录→归档、列表过滤、404、include_deleted 找回）。
- `pytest -q` 全量 32 passed。

## 2026-11-04 — 患者软删除 + 作废处方/冲红（保医疗记录、堵库存孤儿、可退货回补）

### 背景（用户提问）
用户发现三个隐患：① 删除患者会把其全部处方（含已发药）一并物理删除，丢失医疗记录；② 删患者/处方会留下指向已删处方的库存流水孤儿引用；③ 已发药处方无法作废/冲红，患者取药后反悔无处理路径。

### 改动
- **B · 患者软删除**（`patient.py` / `models/patient.py`）：`Patient` 新增 `deleted_at` 列（由 `_sync_model_columns` 自动建列，无需手写迁移）。`delete_patient` 改为仅标记 `deleted_at`，**不再物理删除患者及其处方/就诊/随访/问诊/会话等任何子记录**；`list_patients` 默认过滤已归档患者（新增 `include_deleted` 开关），`get_patient` / `update_patient` 对软删除患者返回 404。→ 有就诊/开方记录的患者不再被随意物理删除，也根除“删患者→已发药处方被删→出库流水 `reference_id` 变孤儿”的连锁问题（即 C）。
- **A · 作废处方/冲红**（`routers/prescription.py` 新增 `POST /{id}/void`）：`已开`/`已审核` 处方作废仅置为 `已取消`（未扣库存，无副作用）；`已发药` 处方作废置 `已取消`，并（默认 `return_stock=true`）按发药时的`出库`流水把库存退回对应批次、生成 `冲红` 流水。幂等：已取消再调直接返回。
- **C · 报表净额抵消**（`routers/stock.py` 的 `report_summary` / `report_profit` / `report_turnover`）：新增 `冲红` 交易类型在采购成本/COGS/收入聚合中的净额抵消，避免作废扭曲账目；`delete_prescription` 对（仅未发药状态的）处方关联库存流水做防御性 `reference_id` 置空。
- **测试隔离修复**（`tests/conftest.py`）：`admin_token` 由 session 级改为 function 级——`backup.reset_data` 会清空全部 `AuthToken` 却不删用户，原共享令牌在 reset 后失效，导致其后测试 401；改为每测试重新登录后解耦。

### 验证
- 新增 `tests/test_void.py`（已发药作废回补库存+生成冲红流水、不退货仅改状态、未发药仅改状态）与 `tests/test_patient_soft_delete.py`（归档标记、记录保留、列表过滤、404、include_deleted 找回）。
- `pytest -q` 全量 31 passed。

## 2026-11-04 — M1 修复：登录下发 httpOnly 会话 Cookie（方案 B），刷新不再掉登录

### 背景（审计 M1）
`frontend/src/store/auth.ts` 注释声称「后端 httpOnly Cookie 作防御纵深 / 用 Cookie 静默恢复会话」，但后端从未下发任何 Cookie；令牌仅存内存，`restore()` 在刷新后既无内存令牌也无 Cookie → `/auth/me` 401 → 登出。注释纯属误导。

### 改动（采用方案 B：真正下发 httpOnly Cookie）
- `routers/auth.py`：
  - 新增常量 `AUTH_COOKIE_NAME="tcm_session"` 与辅助 `_extract_token(request)`（Authorization 头 **或** 同名 httpOnly Cookie 二选一）、`_set_auth_cookie(...)`（`httponly=True, samesite="lax", path="/", max_age=30d`，HTTPS 时自动 `secure`）。
  - `login` / `guest_login` 成功后调用 `_set_auth_cookie` 下发会话 Cookie。
  - `get_current_user` 改为从请求（头/Cookie）提取令牌，不再仅依赖 `HTTPBearer`。
  - `logout` 清除该 Cookie；`change_password` 改用请求提取令牌。
  - 移除已无用的 `fastapi.security.HTTPBearer / HTTPAuthorizationCredentials` 依赖。
- `main.py`：中间件 `_extract_token` 增加 Cookie 回退；导入 `AUTH_COOKIE_NAME`。刷新后仅靠 Cookie 即可通过鉴权中间件与 `get_current_user`。
- `frontend/src/store/auth.ts`：
  - 修正第 37 / 75 行误导性注释，如实描述「内存令牌 + httpOnly Cookie 双轨」。
  - `isLoggedIn` 由「内存令牌」改为「已校验的用户快照（`user`）」——`user` 在刷新后从 localStorage 重载，`restore()` 会用 Cookie 调 `/auth/me` 校验，无效则清空，避免 UI 误判。
  - `restore()` 第二分支（无内存令牌、靠 Cookie）失败时，显式清空残留本地用户快照。
- `frontend/src/utils/api.ts`：注释同步更正。

### 部署注意（同源要求）
Cookie 为同站（SameSite=Lax）机制，要生效需前端与 API **同站**：
- 开发（vite proxy `/api` → :8765）、生产（后端 `StaticFiles` 托管 SPA，同源）均天然满足。
- **Electron 必须从后端 HTTP 源（http://127.0.0.1:8765）加载页面**，而非 `file://`；否则 file://→http 属跨站，Lax Cookie 不会被携带，刷新登录仍会失效（此时应走同源托管，或另行评估 localStorage 持久化方案）。

### 验证
- 新增 `tests/test_auth.py::test_login_issues_http_cookie_and_cookie_auth_works`：登录后 `client.cookies` 含 `tcm_session`；不带 Authorization 头仅凭 Cookie 访问 `/auth/me` 返回 200；登出后 Cookie 清除。
- 后端 `pytest -q` 27 passed；前端 `vue-tsc --noEmit` 退出码 0。

## 2026-11-04 — 安全/正确性审计修复（审核人归属 · FIFO 排序 · 删处方孤儿 · 日期边界）

依据一份代码审计清单逐条核对后修复以下**确认属实**的问题（已排除误报项，见下）：

### M2 · 处方审核人硬编码为 id=1（审计归属错误）— 真实
- `routers/prescription.py` `review_prescription` 原签名 `reviewer_id: int = 1`，前端调用不传该参数 → 所有处方审核人恒记为 id=1。改为 `prescription.reviewed_by = current_user.id`，真实记录审核者。

### M3 · FIFO 发药无真实排序 + 近效期口径不一致 — 真实
- 补差批次循环与旧 FIFO 路径的 `StockBatch` 查询均无 `ORDER BY`，SQLite 下 `with_for_update()` 是 no-op，扣减顺序不确定。两处均补 `.order_by(func.coalesce(expiry_date,"9999-12-31"), id)`，按效期升序优先消耗近效期批次。
- 旧 FIFO 路径原只取 `status == "正常"`，与补差路径的 `in_(["正常","近效期"])` 口径分裂；统一为都含「近效期」。

### M4 · 删处方残留随访孤儿提醒 — 真实
- `delete_prescription` 原只删处方本身，未清 `followup_reminders`（删患者路径 `patient.py:180` 已处理，处方路径漏了）→ 工作台"待回访"出现指向已删处方的死链。现删除前级联清理 `source_type="prescription" & source_id=处方id` 的提醒。新增 `tests/test_prescription_delete.py` 回归。

### L2 · 报表日期范围边界漏微秒 — 真实（低）
- `stock.py`(4 处) 与 `system_log.py` 的 `end + " 23:59:59"` 会漏掉当日带微秒(`".xxxxxx"`)的记录。改为 `23:59:59.999999`。

### L3 · `models/__init__.__all__` 漏列处方明细模型 — 真实（低）
- `AcupointPrescription` / `PrescriptionInjection` 既不在 `__all__` 也未在 `__init__` 导入，仅靠 router 直接 import 建表（脆弱写法）。现已显式导入并加入 `__all__`。

### 已核为误报 / 暂不改的项
- **L1 中间件不校验 is_active**：误报。`auth.py:104` `get_current_user` 已 `if not user.is_active` 拦截，覆盖全 API。
- **L5 并发仅靠进程内锁**：属实但属部署架构层；单 worker 诊所场景可接受，多 worker 才需分布式锁。
- **L6 AI JSON 启发式截取**：`ai_diagnosis_service.py:431` 已优先匹配 ```json 围栏，find/rfind 仅兜底，风险低。
- **S2 `TemplateIO.vue` 死代码 / S3 AI 密钥明文 .env**：可选清理项，当前场景可接受。
- **M1 刷新掉登录 + 虚假 Cookie 注释**：真实，但涉及安全取舍（localStorage 持久化 vs 真正 httpOnly Cookie），待用户拍板后再改。

### 验证
- `pytest -q` 全量 26 passed（含新增 M4 测试）。

## 2026-11-04 — 修复 CI 测试依赖外部种子数据导致失败

### 问题
GitHub Actions 跑 `pytest` 报 3 个失败：`test_herbs.py` 的两条五味筛选用例（`桂枝` 不在结果集、单选 `甘` 返回 0 条）与 `test_reset.py` 的腧穴保留断言（查得 0 个穴位）。本地能过、CI 失败。

### 根因
`tests/conftest.py` 固定使用**全新临时 SQLite**（不污染开发库）；而这两个测试误以为被测库里已有种子数据——`桂枝` 来自 `app/data/herbs.json`、腧穴来自 `app/data/acupoints.json`，二者均被 `.gitignore` 忽略，**CI 干净克隆里根本不存在**。本地因为开发机有这些文件才侥幸通过。

### 改动
- `tests/test_herbs.py`：改为**自给自足**，新增 autouse fixture 在临时库里造 `桂枝(flavors=[辛,甘])` / `甘草(flavors=[甘])` 两条样本，不再依赖外部种子；五味筛选的 AND / 全选空集 / 单选语义断言保持不变。
- `tests/test_reset.py`：reset 前先造一条 `测试穴_RESET` 腧穴，把「腧穴为框架基础须保留」的断言改为校验**本测试写入的腧穴在 reset 后仍在**（而非假设全局有腧穴），在纯框架（克隆 0 穴位）与维护者镜像（含穴位）两种环境都能成立。

### 验证
- `pytest tests/test_herbs.py tests/test_reset.py` 4 passed；完整套件 `pytest -q` 25 passed。

## 2026-11-04 — 模板同步 / 发布包脚本 + examples 回归最小示例（纯框架）

### 背景
此前把用户整理的 5 类导出内容（药材 262 / 穴位 364 / 中药方库 38 / 针灸方库 261 / 文库 1292，共 2217 条）直接提交进 `templates/examples/`，使仓库偏离「纯框架」。为回归「源码不含临床数据」的初衷，把 examples 还原为最小示例，完整内容只通过 Release 资产分发。

### 改动
- 新增 `scripts/sync_templates.py`：把应用导出的扁平 list（带 `id` / `created_at`）归一化为规范的 `{type,version,items}` 示例模板，剥离 `id` / `created_at` / `vector_id`，校验自然键，落盘到 `templates/examples/`。
- 新增 `scripts/build_release.py`：按 README 规划的分层布局（`core` / `formulas` / `books` + `manifest.json`）构建 GitHub Release 资产 `tcm-base-core.zip`（含 sha256 / 各层计数 / 依赖）。后改为从维护者本地「模板 /」原始导出读取并归一化打包，与最小示例解耦——即使 examples 最小，zip 仍含全量。
- `templates/examples/*.example.json` 还原为最小示例（`102a246` 的原始版本，每种 1–2 条）；完整内容不再进 git。`tcm-base-core.zip` 为发布资产，已在 `.gitignore` 忽略 `templates/releases/`。

### 验证
- `sync_templates.py` 通过；`build_release.py` 生成 292K 的 `tcm-base-core.zip`（core 626 / formulas 299 / books 1292 条）。
- `vue-tsc` 类型检查与既有 pytest 全绿。

## 2026-11-04 — 清空数据（reset）改为只重建框架基础，内容库清空后不回填

### 背景
`/backup/reset` 此前调用整库 `seed_all()` 重灌，会把已清空的内容库又填回内置默认，与「纯框架 + 用户自带内容」定位冲突。同时发现 `backup.py` 从未导入 `has_perm`，reset 接口一直 `NameError` 返回 500，从未真正可用。

### 改动
- `backend/app/routers/backup.py`：reset 删除列表不变（Herb / KnowledgeEntry / ClassicFormula 仍清空），但重置后**不再整库 `seed_all()` 重灌**，只重建框架基础——默认账号 + 游客 + 数据字典 + 腧穴；药材 / 医籍文库 / 中药方库清空后保持为空，由用户按自有模板自行导入。
- 补上缺失的 `from app.permissions import has_perm` 导入，修复 reset 接口一直 500 的 bug。
- 首次安装仍由 `main.py` 启动 `seed_all()` 提供内置默认；只有手动「清空数据」才归零。
- 新增 `tests/test_reset.py` 回归测试：内容库清空后为空且不回填、账号 / 字典 / 腧穴保留（测后还原内置数据以免污染同会话其他测试）。

### 验证
- 全量 pytest 25 passed。

## 2026-11-03~04 — 导出文件名统一为中文名 + 日期 + 时间

### 改动
- 新增 `frontend/src/utils/datetime.ts` 的 `fileTimestamp()`，生成本地时间、文件名安全的 `YYYY-MM-DD_HH-MM-SS`（短横线替代冒号，兼容 Windows）。
- 五种数据导出统一为「中文名_日期_时间.json」：中药材 / 针灸穴位 / 中药方库 / 针灸方库 / 医籍文库（`TemplateIO.vue` 为未被引用的死代码，其英文 `tcm_template_{type}` 不影响真实下载，未改）。
- `vue-tsc` 类型检查通过。

## 2026-11-01 — 字典释义改用提示圆点 + 五味筛选改 AND + 字典配色统一

### 背景
1. 数据字典释义（`description`）此前在各下拉里以 12px 灰色小字内联展示，占用行宽，小屏浏览时选项拥挤；且是否展示取决于词条当时有无填释义，规则随机。
2. 药材字典「五味」多选筛选实际是「命中任一」(OR)，选齐五味仍能查出结果，与药理常识相悖。
3. 穴位属性（`acupoint_tag`）四维度未预置配色，手动调的色部分为高饱和荧光色；患者标签（`tag`）同样存在极端亮度（纯白 `#ffffff`、近黑 `#060606`）问题。

### 改动

**① 释义展示：常驻小字 → 小圆点 + 悬浮提示**
- 全局新增 `.opt-hint-dot` 样式（5px 圆点，悬停放大并转主色，`cursor:help`），定义于 `styles/tcm-theme.scss`，三个页面共用。
- `HerbList.vue`（四气/五味 2 处）、`AcupointList.vue`（5 处）、`VisitRecord.vue`（舌质/舌苔/脉象/证型 4 处）统一改为「名称 + 小圆点」，`el-tooltip` 展示完整释义。
- 平时选项只占单行，小屏不再拥挤；释义按需悬停可查，长文本自动换行。
- 清理 `VisitRecord.vue` 中废弃的 `.term-desc` 样式，`term-opt` 由竖排改回横排居中。

**② 修复：VisitRecord 下拉只显示色圈、无文字**
- 改造时把块级 `div.term-opt` 与 inline 色点混排，`el-option` 高度按单行计算，导致名称被裁掉。
- 修复：色点收进 `term-opt` 内部，整项作为横向 flex 容器（`display:flex; align-items:center; gap:4px`），4 处统一结构。

**③ 药材五味多选筛选改为 AND 语义**
- `routers/herb.py`：由集合交集 `set(h.flavors) & set(flavors)`（命中任一）改为子集判断 `set(flavors).issubset(set(h.flavors or []))`（须全部具备）。
- 单味筛选行为不变；选齐五味不再返回结果。
- 新增 `tests/test_herbs.py` 3 个回归用例：多味 AND（桂枝含、甘草不含）、全选五味为空集、单味正常。测试由 8 项增至 11 项。

**④ 穴位/药材/患者标签字典配色接入与统一**
- 前端 `AcupointList.vue`：新增 `tagColor` / `readableInk` / `tagStyle` 工具函数，按字典 `color` 着色并按底色亮度自动选黑/白字；表格「来源/归经/部位/类型」四列及移动端卡片「来源」徽标全部接入字典色，无色回退灰。
- 后端 `seed_dictionaries.py`：
  - 新增 `ACUPOINT_TAG_COLOR`（53 条）：来源按三体系各色；归经按十二正经五行归色（金=银白/火=红/木=青绿/土=黄/水=黑蓝/相火=紫）；部位按人体上阳→下阴渐变，董氏部位按编号灰系递进；类型五输穴按井→荥→输→经→合水文流向，余者功能色。
  - 新增 `PATIENT_TAG_COLOR`（6 条）：按风险严重度递进（高危红/深红 → 中危橙 → 关注蓝 → 群体紫/青）。
  - 回填逻辑由「仅补 `color IS NULL`」改为「按推荐表统一覆盖」，herb_tag / tag / tongue / pulse / syndrome / acupoint_tag 六类全部对齐推荐配色；清除荧光色与极端亮度。
- 覆盖前已备份原手调色至 `backend/acupoint_tag_colors_backup.json`（52 条）。

### 全局配色规范（备忘）
| 字典类型 | 条数 | 配色依据 |
|---|---|---|
| acupoint_tag | 53 | 五行归色 / 空间渐变 / 水文流向 / 三体系 |
| herb_tag | 11 | 五味 + 四气（寒热温凉平）|
| pulse | 33 | 脉类寒热虚实（浮表=青蓝…紧寒=深蓝）|
| syndrome | 17 | 六经五色（太阳黑蓝/阳明白/少阳红/太阴黄/少阴紫/厥阴青）|
| tongue | 25 | 舌色关键词（绛紫青红淡白黄灰黑…）|
| tag | 6 | 风险严重度递进 |

统一约束：低饱和、避免荧光色与纯白/纯黑；前端按亮度自动切换前景字色保证可读。

### 注意
- 回填为**强制覆盖**模式：日后在字典页手动改色，重跑 `seed_dictionaries.py` 会被重置为推荐值。日常不重跑无影响。

### 验证
- 后端 pytest `11 passed`（含新增 3 个五味用例）。
- 前端 `vue-tsc --noEmit` 无类型错误，`vite build` 构建成功。
- 全量配色检查：145 条词条全部有颜色，无非法 HEX，无极端亮度残留。

## 2026-11-01 — 库存管理重构：中药/耗材统一为物品-批次-流水模型

### 背景
原库存体系深度绑定中药（`herb_inventory` / `inventory_transactions` 以 `herb_id` 外键直指 `herbs` 表，单位写死"g/元每g"），无法容纳一次性针灸针、艾柱等耗材（计量单位是 盒/支/根/贴），也缺少"入了多少、出了多少、剩余多少"的完整流水视图。

### 重构方案
新增统一的「物品-批次-流水」三件套，将库存从"中药"抽象为"物品"：

- **`StockItem`**（物品主数据）：`item_type`(中药/针灸针/艾灸耗材/外治耗材/其他)、`name`、`spec`(规格)、`unit`(计量单位 g/盒/支/根/贴/包)、`sell_price`；中药通过可选 `herb_id` 关联 `herbs` 表，兼容原处方计价/发药逻辑。
- **`StockBatch`**（批次库存）：`item_id`、`batch_no`、`quantity`、`unit_price`、`purchase_date`、`expiry_date`、`supplier`、`min_stock`、`location`、`status`。中药用 g 计，耗材用 盒/支 计，全靠 `StockItem.unit` 跟随。
- **`StockTransaction`**（出入库流水）：`item_id`、`batch_id`、类型(入库/出库/损耗/盘点)、`quantity`、`before`、`after`、关联来源(处方/就诊)、操作人、备注、时间。完整留痕，支持"入/出/余"查询。
- 迁移 `m0006`：新建三表；原 `herb_inventory` 保留兼容，中药侧通过 `herb_id` 关联平稳过渡。

### 涉及改动
- 后端：新建 `models/stock.py`、`routers/stock.py`、`schemas/stock.py`；`dispense` / `_compute_total_price` / `stats.dashboard` 预警口径 / `backup.py` 接线到新模型。
- 路由：`/stock/*`（`overview` 总览、`items` 物品、`batches` 批次、`transactions` 流水、`check` 盘点、`alerts` 预警）。
- 前端：
  - 菜单重构：原【药品管理】改名【诊疗管理】（药材字典/针灸穴位，移出库存项）；新增【库存管理】主菜单（库存总览/物品管理/出入库流水/库房盘点）。
  - 新建 `views/inventory/` 下 4 个页面：Overview、ItemManage、Transactions、Check。
  - 处方编辑器 `PrescriptionEditor.vue` 改调 `/stock/batches`，余量单位动态取 `unit`。
  - 仪表盘 `Dashboard.vue` 预警接口改 `/stock/alerts`，跳转路由指向库存总览。
  - 删除过期页面 `views/herb/InventoryManage.vue`（引用已删除的旧接口）。

### 修复的 Bug
- `StockBatchOut` 继承自基类但基类无 `batch_id` 字段，出库端点多处引用 `data.batch_id` 导致 500 → 补充 `batch_id` 字段。
- 临时调试脚本未带 `Content-Type: application/json`，导致 FastAPI 将原始 bytes 交给校验器、序列化校验错误时二次 500。属脚本问题非 API bug。

### 验证
- 后端 pytest 全绿（`8 passed`），含迁移、发药、库存各端点。
- 前端 `vue-tsc` 无类型错误，`vite build` 构建成功。
- 库存全量验证脚本：迁移、物品、批次、总览、预警、出入库、盘点、流水全部通过。

## 2026-11-01 — 库存预警改为按药材总库存（多批次不再误报）

### 问题
预警是按**单个批次**判断 `quantity < min_stock`，且 `min_stock` 是批次级字段。第一次入石膏100g 设预警200g，再入第二批500g 后，第一批仍 100<200 持续告警，无视其它批次总量，与实际库存脱节。

### 修复
- `Herb` 模型新增药材级 `min_stock`（最低库存预警阈值）；`herbs` 表迁移加列；附幂等脚本 `migrate_herb_min_stock.py`。
- `HerbUpdate`/`HerbResponse` 暴露 `min_stock`；`update_herb` 经通用 `setattr` 自动写入（已验证）。
- `inventory_alerts` 与 `inventory/summary`：改为按药材维度聚合（该药材所有正常/近效期批次总库存 vs 药材级 `min_stock`，历史数据回退各批次 `min_stock` 最大值）。
- 前端 `InventoryManage.vue`：加载时并行拉取 `/herbs/inventory/summary`；列表/卡片的"最低库存"列与预警高亮改为药材级（基于总库存）；"设置预警"对话框改为设置**药材**阈值（去掉批次级存放位置项）。

### 验证
- 同一药材两批次 A=100g/B=500g，药材级 min_stock=1000 → 总600<1000 告警；降到200 → 总600>200 不再告警（用户场景）。测试数据已清理。

## 2026-11-01 — 修复前端预估金额未尊重所选批次售价（取价 bug）

### 现象
同一药材多次入库（如石膏 0.5/0.8/2 元）后开方选了 0.5 批次，后端 total_price 正确（0.5×剂量×剂数），但前端实时预估金额却按药材参考价（被最后一次入库=2 元覆盖）计算，与后端对不上。

### 根因
`PrescriptionEditor.vue` `herbUnitPrice` 为 `herb?.price ?? item.price`：当 `herb.price` 存在时优先用参考价，忽略了所选批次的 `item.price`。

### 修复
改为 `item.price ?? herb?.price`：所选批次售价优先，未选批次再回退药材参考价，与后端取价口径一致。

## 2026-11-01 — 入库批号留空默认当天日期 + 发药跨批次拆单补差

### A. 入库批号默认入库日期
- `routers/herb.py` `inventory_in`：入库时若 `batch_number` 为空，自动填当天日期（`YYYYMMDD`），便于按日追溯；仍支持手填自定义好记名称。

### B. 发药跨批次拆单补差
- `routers/prescription.py` `dispense_prescription`：处方项所选批次余量不足以覆盖本次用量（剂量×剂数）时，先出所选批次全部，差额自动从同药材其它可用批次（正常/近效期）按 FIFO 补；仍不足才报错。所选批次充足时仍走单一批次（与之前一致）。
- 出库流水分别记录所选批次与补差批次（`处方#x发药(批次#y)` / `处方#x发药补差(批次#z)`），保证账目可追溯，不会静默混扣。

### 验证
- 入库不填批号 → `batch_number=20261101`（当天）。
- 建两批次 A(10g/1元) B(100g/2元)，开方选 A、剂量5×剂数3=15g（超出 A）；发药后 A=0、B=95，出库流水两条（A出10、B补5）；测试数据已清理还原。

## 2026-11-01 — 开方药材行显示批次余量/需量提示（不足红字）

### 背景
按批次取价后，医生选了某批次但余量不足以覆盖本次用量（剂量×剂数）时，此前要等到发药才报错，开方无感知。

### 改动
- `PrescriptionEditor.vue`：药材行选批次后实时显示「需Xg/余Yg」，余量不足红字提示，便于及时改选批次或调整剂量。

## 2026-11-01 — 开方支持按批次取价与按批次出货

### 背景
入库时填的售价落在 `HerbInventory.sale_price`（批次级）。此前开方计价只取"药材参考价 herb.price"或"第一个正常批次售价"，同一药材多次入库售价不同时取价不准；发药是 FIFO 全局扣，不认批次。

### 改动
- `PrescriptionItem` 模型新增 `inventory_id`（关联库存批次，可选）与 `price`（记账单价）；数据库已迁移加列（`migrate_prescription_item_batch.py` 幂等脚本）。
- `PrescriptionItemCreate/Response` 增加 `inventory_id`/`price` 字段。
- 前端 `PrescriptionEditor`：选药材后自动选第一个可用批次并用其售价取价；药材行新增「批次」下拉可手动改选（显示批号/余量/售价）；提交与编辑回显均带 `inventory_id`/`price`。
- 后端 `prescription.py`：计价 `_compute_total_price` 优先使用处方项记录的单价（批次售价）；发药 `dispense` 有 `inventory_id` 时按所选批次出货（不足报错），无则 FIFO 回退（兼容旧处方）。

### 验证
- 端到端：开方选批次(售价9.9/g) → total_price=售价×剂量×剂数 正确；审核→发药后该批次库存精确减少(剂量×剂数)，出库流水 note 标记批次号；测试数据已清理还原。

## 2026-11-01 — 修复库存出库"没反应"：补全前端错误处理与校验提示

### 现象
库存管理点"出库"操作后无任何反馈（无成功/失败提示，列表也不刷新）。

### 根因
- `submitStockOut`、`loadInventory` 的 `catch {}` 为空：出库请求异常，或数量未填被前端拦截时全部静默吞掉，表现为"没反应"。
- 出库数量校验提示不醒目，易被忽略。

### 修复
- `InventoryManage.vue` `submitStockOut`：补全 `catch` 显式 `ElMessage.error` 失败原因；数量校验提示改为"请输入大于 0 的出库量"；仅提交 `herb_id/quantity/note` 必要字段。
- `loadInventory`：补全 `catch` 错误提示，加载失败可见。
- 后端 `POST /herbs/inventory/out` 经实测正常（200，库存正确扣减），"没反应"为纯前端吞错所致。

### 附：入库售价与处方计价（用户问）
入库填的售价会同步写入药材参考单价 `herb.price`；开处方选该药材时单价自动预填 `herb.price`（`PrescriptionEditor` 取 `herb?.price ?? item.price`），可在处方内再改。即入库把售价填对，开方计价即自动带价。

## 2026-11-01 — 库存管理入库记录支持编辑纠错（录入字段不再锁死）

### 问题
入库(`inventory_in`)创建库存批次记录后，前端仅提供"设置预警/仓位"两入口，且 `InventoryUpdate` 只允许改 `min_stock/location/status`——数量、进价、售价、批号、购入日期、有效期、供应商这些录入字段入库后完全无法修改，输错无抢救方案。

### 修复
- `schemas/herb.py` `InventoryUpdate`：放开可编辑字段（quantity/unit_price/sale_price/batch_number/purchase_date/expiry_date/supplier + 原 min_stock/location/status）。
- `routers/herb.py` `update_inventory`：售价改动同步药材参考单价 `herb.price`（与入库逻辑一致）；数量被调整时记一条 `调整` 流水(`inventory_transactions`)，纠错可追溯。
- `frontend/views/herb/InventoryManage.vue`：库存列表/移动端卡片新增"编辑"按钮，弹出对话框可改全部录入字段；复用 `PUT /herbs/inventory/{id}`。

### 验证
- 临时 token 调 PUT 将数量 100→110 成功，自动生成 `调整` 流水 1 条，还原数据无残留。

## 2026-11-01 — 修复工作台待办显示已删除患者的回访提醒（bug）

### 根因
- 删除患者时 `delete_patient` 未级联清理 `followup_reminders`（复诊回访提醒）表，且 `Patient` 模型未声明其与 `FollowUpReminder` 的 relationship，导致患者删除后留下孤儿提醒。
- 工作台 `stats/dashboard` 与 `followup-reminders` 列表查询均未排除已删患者：孤儿提醒仍计入"待回访 N 位"并展示，`patient_name` 为 None、`patient_id` 指向已删患者，点进去 404。

### 修复
- `patient.py` `delete_patient`：新增 4.6 步显式 `DELETE FROM followup_reminders WHERE patient_id=...`，根因上不再产生孤儿。
- `stats.py` `dashboard_stats` 与 `followup_reminders.py` `list_reminders`：查完后用 `patient_id ∈ 现有患者集合` 过滤，防御性排除孤儿（历史数据存在也不展示/不计数）。
- 一次性清理历史孤儿数据：删除 1 条已删患者的回访提醒（即本次反馈的"待回访 1 位 / 已逾期 2026-10-15 复诊"）。

## 2026-11-01 — 穴位库「归经 / 部位」拆分布局 + 补全部位数据 + 按部位筛选

### 改动
- 前端 `AcupointList.vue`：把原合成的「分部」(`归经 · 部位` 组合) 下拉拆成「归经」「部位」两个独立筛选下拉；表格与移动端卡片由单列「分部」拆成「归经」「部位」两列，更直观。
- 新增 `backend/seed_acupoint_regions.py`：用保守规则(定位文本关键词 + 具体穴名映射) 补全 `acupoints.region`(部位)。受控词项：头面 / 上肢 / 下肢 / 前胸 / 后背 / 腰骶。

### 数据
- `acupoints` 表 175 条原本仅 3 条有 `region`；本次补全 172 条，全部 175 条带部位（下肢 46 / 上肢 45 / 头面 30 / 后背 25 / 前胸 23 / 腰骶 6）。命中才填、不确定留空（本批 0 留空），不编造；少数归类不准的可在编辑页手动改。

### 验证
- 后端 `/acupoints?region=下肢` 返回 46 条；按部位筛选/搜索可用。

## 2026-11-01 — 导入倪海厦人纪针灸《病症针灸速查》到针灸方库

### 背景
用户整理了倪海厦人纪-1-针灸的 `215条针灸经验穴位和31条透针透穴.md`（病症→配穴经验 + 透刺法）。项目已有 `AcupointFormula` 模型与 `POST /acupoint-formulas/import` 批量 upsert 接口，但缺一份针对该资料的解析导入脚本（既有 `seed_nihaixia.py` 是导入医籍文库的，与针灸方库无关）。

### 改动
- 新增 [backend/seed_acupoint_formulas_nihaixia.py](file:///home/debian/tcm-doctor/backend/seed_acupoint_formulas_nihaixia.py)：解析上述 md → `acupoint_formulas` 记录，按 `name` upsert（幂等可重放）。
  - 覆盖三块：开头零散 `@病症：穴位` 速查卡片 + `## 215条针灸经验`（11 个系统分类）+ `## 31条透针透穴`。
  - 字段映射：`name=病症/透穴名`、`source=倪海厦·针灸`、`composition.acupoints=对象数组[{acupoint_name, technique, retention, sequence, note}]`（与原有"通用"方格式一致，前端按 acupoint_name 渲染）、`indications=病症或治症`、`notes=【分类】…+透刺/放血/梅花灸等技法说明+透穴来源配穴`。
  - 识别：内置标准经穴+常见奇穴白名单；`X透Y` 拆两穴并标透刺；去括号保留说明；粘连词（合谷止痛/开四关）最长子串匹配拆穴；非穴位词进 notes；解析不出任何穴位的行（纯功法/医案/病机）自动跳过；不编造 efficacy/频次/天数（留空）。
  - 默认 dry-run 预览，加 `--apply` 落库。
  - 修正：首版曾误将 `composition.acupoints` 存为字符串数组（["合谷",...]），与项目约定及前端渲染（按 `acupoint_name` 取值）不符，导致针灸方列表/详情页"配穴"显示为空；已改为对象数组格式并幂等重跑覆盖全部 259 条倪海厦方。

### 数据
- 解析并导入 **259 条**（新增 255 / 更新 4），运行库 `acupoint_formulas` 现共 **261 条**（倪海厦·针灸 258 + 原有通用 3）。系统分类分布：头面·五官 44、伤痛外科·运动 43、透针透穴 31、妇科·儿科 24、病症速查(零散) 18、其他问题 18、脾胃消化 17、神志·失眠·神经 16、肾·膀胱·泌尿生殖 13、皮肤·表皮 13、肺·呼吸 9、心·心血管 7、肝胆·少阳·厥阴 6。

## 2026-11-01 — 字典词项释义带入下拉选择提示（acupoint / herb 通用）

### 背景
数据字典 `DictionaryTerm` 每条词项都带「释义」(description) 与「色标」(color)，但此前 `/acupoints/tags/meta` 与 `/herbs/tags/meta` 只把维度词项返回成纯字符串数组，前端下拉选择时只看得到名字，释义等于白填、失去意义。现把释义与色标一并带到选择时的提醒里。

### 改动
- 后端 [app/routers/acupuncture.py](file:///home/debian/tcm-doctor/backend/app/routers/acupuncture.py)、[app/routers/herb.py](file:///home/debian/tcm-doctor/backend/app/routers/herb.py) 的 `tags/meta`：每个维度 `options` 由字符串数组升级为对象 `{ value, label, description, color }`，下发释义与色标（字典为空回退常量词表时释义留空）。
- 前端 [AcupointList.vue](file:///home/debian/tcm-doctor/frontend/src/views/acupoint/AcupointList.vue)：来源筛选 + 编辑弹窗的来源/归经/部位/类型 四个字典驱动下拉，每个选项显示「色点 + 名称 + 释义（灰色小字）」；`dimOptions` 返回类型改为 `TagOption[]`。
- 前端 [HerbList.vue](file:///home/debian/tcm-doctor/frontend/src/views/herb/HerbList.vue)：四气/五味 筛选与编辑下拉同样显示释义（颜色点沿用原有 `xwColor`）；`dimOptions` 返回类型改为 `any[]`。
- 测试 [tests/test_acupoints.py](file:///home/debian/tcm-doctor/backend/tests/test_acupoints.py)：meta 断言改为按对象结构校验（`value/label/description/color` 齐备，并按 `value` 判定维度包含关系）。

### 数据
- 运行库 `acupoint_tag` 字典此前偏旧，缺 `来源` 维度的「倪海厦·针灸 / 通用」两条；已重跑幂等种子补全（现 来源 4 / 归经 16 / 部位 18 / 类型 16，共 54 条，全部带释义）。

## 2026-10-31 — 针灸穴位字典化重构（复用 herb_tag 受控词表模式，支持三体系混排）

### 背景
原 `Acupoint` 只有 `meridian/point_type` 两个维度，无法表达「针灸大成 / 董氏奇穴 / 倪海厦·针灸」多体系混排，也无法按「来源 / 部位」检索。改为复用已建好的 herb_tag 字典驱动模式：维度（来源 / 归经 / 部位 / 类型）由数据字典 `DictionaryTerm(term_type='acupoint_tag', category=维度中文名)` 托管，未来新增任何针灸流派只需在字典里加词项、在穴位编辑里选填，无需改代码。

### 1. 后端
- [constants/acupoint_tags.py](file:///home/debian/tcm-doctor/backend/app/constants/acupoint_tags.py)：4 维度（来源 / 归经 / 部位 / 类型）默认受控词表 + `ACUPOINT_TAG_DIMENSION_BY_LABEL` 映射（字典为空时回退）。
- [seed_dictionaries.py](file:///home/debian/tcm-doctor/backend/seed_dictionaries.py)：新增 54 条 `acupoint_tag` 词条种子（来源 4 / 归经 16 / 部位 18 / 类型 16，无预设色），被 `seed_all()` 调用，全新库自动带；词条可在「字典管理」页增删。
- [schemas/dictionaries.py](file:///home/debian/tcm-doctor/backend/app/schemas/dictionaries.py) + [routers/dictionaries.py](file:///home/debian/tcm-doctor/backend/app/routers/dictionaries.py)：`term_type` 白名单放开 `acupoint_tag`。
- [migrations.py](file:///home/debian/tcm-doctor/backend/app/migrations.py)：新增 `m0005`，幂等 ALTER `acupoints` 加 `source`(VARCHAR100) / `region`(VARCHAR50) / `indications`(TEXT) / `needling_method`(TEXT) 四列。
- [models/acupuncture.py](file:///home/debian/tcm-doctor/backend/app/models/acupuncture.py) + [schemas/acupuncture.py](file:///home/debian/tcm-doctor/backend/app/schemas/acupuncture.py)：`Acupoint` 模型与 `AcupointCreate/Update/Response` 增加上述四字段。
- [routers/acupuncture.py](file:///home/debian/tcm-doctor/backend/app/routers/acupuncture.py)：`GET /acupoints` 新增 `source/region/point_type` 筛选参数；新增 `GET /acupoints/tags/meta` 聚合 4 维度词表（字典优先、回退常量），供前端下拉与筛选项驱动。

### 2. 前端
- [AcupointList.vue](file:///home/debian/tcm-doctor/frontend/src/views/acupoint/AcupointList.vue)：桌面 7 列表格（穴名 / 来源 / 分部(归经·部位) / 类型 / 定位 / 功效 / 操作）+ 来源 / 分部筛选；编辑弹窗 4 个字典驱动下拉（来源 / 归经 / 部位 / 类型，filterable allow-create）+ 定位 / 功效 / 主治 / 刺法 / 备注；移动端卡片同步。
- [DictionaryManage.vue](file:///home/debian/tcm-doctor/frontend/src/views/dictionary/DictionaryManage.vue)：新增「穴位属性」页签，按 来源 / 归经 / 部位 / 类型 维度归类管理词条。

### 3. 数据说明（按用户澄清）
- 原有 48 条穴位数据**原样保留**，新字段（来源 / 部位 / 主治 / 刺法）**留空**，后续在界面里补充即可，不预置编造值。
- 董氏奇穴 / 倪海厦·针灸 等示例流派**未预置数据**；其维度词项已进数据字典（来源含「董氏奇穴 / 倪海厦·针灸」），需要时直接在字典管理加词项、在穴位编辑选填即可。

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

### 9. 药材性味收敛至《神农本草经》标准
- 四气收敛为 `寒 / 微寒 / 平 / 微温 / 温`（凉并入平）；五味收敛为 `酸 / 苦 / 甘 / 辛 / 咸 / 淡`（去涩）。
- 受控词表常量 `HERB_TAG_DIMENSIONS` 同步更新；数据字典 `herb_tag` 删除 5 条越界词条（凉/大寒/大热/热/涩），现 11 条（四气 5 + 五味 6）。
- 药材主数据同步收敛：nature 降级（凉→平、大寒→寒、大热/热→温）共 18 行；flavors 去涩 15 行（剔除「涩」字、保留搭配主味，无一味变空）。
- 校验：所有药材 `nature/flavors` 均落在新词表内（越界为空）；`/herbs/tags/meta` 返回新 5/6 选项。

### 10. 药材性味字典列表排序
- 字典管理页「药材性味」列表原按中文名 Unicode 码位排序，四气五味混排显乱、无规律。
- 改为先按维度分组（四气→五味）、组内按本草经梯度排序（四气：寒→微寒→平→微温→温；五味：酸→苦→甘→辛→咸→淡）。

### 11. 药材列表手机端与导入提示
- 手机端编辑对话框「孕妇禁忌 / 状态」回到同一行（`:xs="12"`）。
- 手机端卡片补充「储存 / 孕妇 / 状态」信息。
- 导入 JSON 请求加 `{ silent: true }`，失败时报错提示不再重复弹出。

### 12. 修复 Docker 启动失败（旧库缺 herbs 新列）
- 症状：容器复用卷内旧 schema 的 `tcm_doctor.db` 时，`create_all` 不会为已存在表 ALTER 加列，启动 `seed_herbs` 报 `no such column: herbs.flavors` 而退出。
- 修复：`_run_light_migrations()` 的 `herbs` 迁移段补上 `aliases` / `flavors`（JSON 列，按存在性判断幂等 ALTER），旧库可平滑升级；其余表的新增列此前已覆盖。
- 验证：模拟缺 `flavors` 的旧 herbs 表，迁移后 ORM 查询 `Herb` 不再报错。

### 13. 安全加固（P0）：只读接口鉴权 + 关闭游客 + 强制改密 + 修复发药并发超卖
- **只读接口统一鉴权**：原全局中间件 `require_admin_for_writes` 仅拦截写操作，导致患者档案/处方/统计等 GET 接口对游客匿名开放（患者隐私泄露风险）。改为 `/api/v1` 下除 `/api/v1/auth` 外所有请求都必须携带有效 token，写操作额外要求管理员。
- **关闭游客登录**：`config.allow_guest_login` 默认改为 `False`，`docker-compose.yml` 显式设为 `false`；中间件在游客关闭后拒绝任何遗留 guest 令牌。前端登录页移除"游客登录"按钮及相关死代码。
- **强制改密**：用户 `must_change_password=True` 时（seed 创建的默认 admin 即为此状态），除改密/登出/当前用户外一律返回 403，倒逼首次登录即设置强口令；生产环境不再以 `admin/admin123` 裸奔。
- **修复发药并发双扣库存**：`dispense_prescription` 原在锁外校验 `status`，两并发"已审核"请求会先后通过检查、串行进锁后各扣一次 → 超卖。改为锁内重新查询处方最新状态（带行锁）再扣减。
- 验证：TestClient 端到端 8 项断言全过（匿名 401、游客 403、强制改密 403、改密后 200、普通用户读 200 / 写 403）。

### 14. 迁移规范化（P1-4）：版本表追踪替代散落 ALTER
- 新增 `app/migrations.py`：轻量版本化迁移运行器，每条迁移带版本号并记录到 `schema_migrations` 表，启动幂等追踪、缺失自动补齐。
- 将原 `main.py` 中 179 行散落硬编码 `ALTER`（按表逐列判断）移植为 `0001`(补列) / `0002`(注入默认患者标签) / `0003`(剂量超限提醒去重) 三条版本化迁移；`main.py` 启动改为调用 `run_migrations()`，删除旧函数。
- 新增表/列只需追加一条 `@migration` 即可，不再手动维护散落代码；具备版本回放与可重放能力（解决原方案无版本、无回滚、维护成本高的问题）。
- 验证：TestClient 全量启动正常；模拟旧库缺 `flavors/aliases/price` 清空版本表后重跑迁移，三列被正确补齐；重复运行版本号稳定为 3（幂等）。

### 15. 自动化测试与 CI（P1-5）
- 新增 `backend/tests/` 测试套件（pytest）：`test_auth`（匿名读 401 / 游客禁用 403 / 强制改密拦截与放行 / 普通用户读放行写拒绝）、`test_dispense`（发药扣减 剂量×剂数、重复发药 400 且库存不双扣，对应 P0-2）、`test_migrations`（版本化迁移旧库缺列补齐 + 幂等）。
- 新增 `backend/pytest.ini`（`pythonpath=.`，测试库使用临时 SQLite，不污染开发库）。
- 新增 `.github/workflows/ci.yml`：push/PR 触发，后端跑 `pytest`、前端跑 `npm ci && npm run build`。
- `requirements.txt`：移除未使用的 `alembic`（自研版本化迁移已替代），新增 `pytest`。
- 验证：`pytest -q` 全量 6 项通过。

### 16. 类型与错误统一（P2-6）
- **前端构建启用类型检查**：`frontend/package.json` 的 `build` 由 `vite build` 改为 `vue-tsc --noEmit && vite build`（已确认 `vue-tsc` 0 错误，构建零风险）；`Dockerfile` 前端阶段同步改用 `npm run build`，不再跳过 tsc。CI 的 `npm run build` 现会真正拦住类型回归。
- **收敛 AI 服务静默 except**：`app/services/ai_diagnosis_service.py` 新增模块级 `logger`；原 13 处裸 `except Exception: pass` / 静默 `return []` 改为 `logger.debug/warning` 记录异常（BMI 计算、RAG 关键词/向量检索、配穴 JSON 解析、候选 JSON 块解析等），失败不再无声吞掉，便于线上排查。
- **统一错误响应**：`app/main.py` 注册统一异常处理器——`HTTPException` 与 `RequestValidationError` 均返回 `{"detail": ...}`（与原鉴权中间件形状一致），并新增兜底 `Exception` 处理器：返回 `{"detail": "服务器内部错误，请联系管理员"}` 且 `logger.exception` 记录堆栈，避免 500 泄漏堆栈、前端解析一致。

### 17. 镜像瘦身 + 健康检查 + 清理误导配置（P2-7）
- **镜像瘦身**：`.dockerignore` 新增排除 `backend/app/data/generate_herbs.py`、`backend/app/data/generate_knowledge.py`、`backend/app/data/books/gen_*.py`——这些为数据生成脚本，运行时只需其产出的 JSON（`seed.py` 只读 JSON），剔除后减小镜像体积。
- **健康检查**：`docker-compose.yml` 新增 `healthcheck`，命中既有 `/health`（`main.py` 已实现，返回 `{"status":"ok","version":...}`）；因 `python:3.12-slim` 不含 curl/wget，改用标准库 `urllib.request` 探测，避免引入额外依赖。
- **清理误导配置**：移除 `docker-compose.yml` 中 `SECRET_KEY=please-change-this-secret`（`config.py` 根本不读取该变量，属误导性死配置，易让人误以为已设密钥）。

- 验证：`python3 -m pytest -q` 6 项通过；`npm run build` 通过（vue-tsc 0 错误 + vite 打包成功，仅第三方依赖告警）。

### 18. 数据字典颜色真正用起来：药材性味按五行本色着色
- **背景**：此前字典 `color` 仅 `患者标签` 类型真正消费，其余类型（舌象/脉象/证候/药材性味）的取色器是死控件。用户希望把颜色扩展到其它类型——以药材「四气/五味」为落点，按五行本色着色（酸木青、苦火赤、甘土黄、辛金白、咸水黑；四气寒→温 蓝→橙红梯度；毒性红橙区分）。
- **后端种子色**：`seed_dictionaries.py` 新增 `DEFAULT_HERB_TAG_COLORS`，播种 `herb_tag` 词条时写入五行本色；并对历史已存在、未设颜色的词条做**幂等回填**（仅补 `color IS NULL`），老库启动即获得本色，无需手工设。
- **前端消费**：
  - `HerbList.vue` 挂载时拉取 `GET /dictionaries?term_type=herb_tag` 构建「名称→色」映射；未设色时回退到内置五行本色常量，保证开箱即见色。
  - 药材「性味」列（表格 + 移动端卡片）改为**带色标签**：四气、五味各自按字典/本色着色，毒性（有毒/有小毒/有大毒）按红橙梯度着色。
  - 四气/五味的**筛选下拉**与**编辑弹窗下拉**选项前均加五行本色色点，便于辨识。
  - `DictionaryManage.vue` 的取色器对 `患者标签` 与 `药材性味` 两类开放（其余类型暂无消费方，仍隐藏，避免误导）。
- 验证：`python3 -m py_compile` 种子脚本通过；`npm run build` 通过（vue-tsc 0 错误）。

### 19. 字典页把药材性味颜色「亮出来」（温度/五行本色可视化）
- **背景**：上一节的改动让药材列表按颜色着色，但字典管理页里药材性味（四气/五味）的颜色仅以小圆点呈现、编辑弹窗缺少实时预览、移动端卡片视图的颜色行只对 `患者标签` 显示（漏了 `herb_tag`），导致设了自定义色也看不到「亮」出来的效果。
- **列表着色**：`DictionaryManage.vue` 桌面表格「颜色」列与移动端卡片「颜色」行，均将词项名直接渲染为**带五行/温度本色的标签**（四气寒蓝→温红梯度、五味酸青苦赤甘黄辛白咸黑；自定义色优先于默认色）。
- **编辑实时预览**：编辑弹窗的颜色项下方新增**实时预览标签**，拖动取色器即刻看到着色效果；未填自定义色时显示默认温度/五行本色并提示「当前为默认色，保存后按此色着色」。
- 验证：`npm run build` 通过（vue-tsc 0 错误 + vite 打包成功，仅第三方依赖告警）。

### 20. 修复浅色（含白色）标签文字不可见
- **问题**：上一节把标签文字色设为所选颜色、背景为该色 10% 透明，选白色（及近似浅色）时白字 + 近白背景导致标签「啥也没有」。
- **修复**：新增 `readableInk(hex)` 按颜色相对亮度计算对比前景色——浅色用深字/深边框、深色用浅字；标签改为**实色填充**，与「把颜色亮出来」的初衷一致。`HerbList.vue`（药材性味）与 `DictionaryManage.vue`（字典列表/卡片/编辑预览）三处统一采用，确保白色等任意色均清晰可读。
- 验证：`npm run build` 通过（vue-tsc 0 错误）。

### 21. 颜色扩展到证型/脉象/舌象（字典页全类型着色 + 辨证页四诊下拉色点）
- **背景**：此前字典 `color` 仅「患者标签」与「药材性味」真正消费。经方家关注的证型/脉象/舌象三类仍是无作用的死控件。按「六经五色 / 脉类 / 舌色苔」配色，把颜色真正用起来（AI 辨证结论保持原模板不改，仅作配色参考）。
- **后端种子色（经方本义）**：
  - 证型（六经配五色）：太阳寒水=黑蓝、阳明燥金=白、少阳相火=红、太阴湿土=黄、少阴君火=紫、厥阴风木=青（合病取首经）。
  - 脉象（按脉类/阴阳寒热）：浮表=青蓝、沉里=黑、迟寒=蓝、数热=红、虚=灰、实=棕红、滑痰饮=黄、涩血瘀=紫、弦肝胆=青绿、洪热盛=橙、细血虚=淡粉、缓湿=黄褐、微=浅灰、紧寒束=深蓝。
  - 舌象（按色/苔关键词）：绛=深红、紫=青紫、青=木青、红=赤、淡=淡蓝灰、白、黄、灰、黑、少/无/花=灰、滑=浅蓝。
  - `seed_dictionaries.py` 播种时写入对应默认色，并对**历史已存在、未设色**的证型/舌象/脉象词条做幂等回填（`color IS NULL` 才补），老库启动即带本色。
- **前端消费**：
  - `DictionaryManage.vue`：取色器与「颜色」列/卡片行**对所有词类开放**；`tagChipStyle(term)` 按 `term_type` 泛化取默认色（证型看六经、脉象看脉类、舌象看色苔、药材性味看五行本色），并复用 `readableInk` 保证白色等浅色可读。
  - `DiagnosisChat.vue` 四诊分析的三处下拉（舌质/舌苔/脉象）选项前均加**本色色点**（字典色优先，缺失回退默认色），与字典页配色一致。
- 验证：`python3 -m py_compile` 种子脚本通过；`npm run build` 通过（vue-tsc 0 错误）。

### 22. 就诊记录里证型/舌象/脉象统一用上字典色（修正「固定色误导」）
- **澄清**：此前就诊记录里「证型」看起来有颜色，其实是 `VisitCard.vue` 中 `<el-tag type="warning">` 的**固定橙色**（所有证型同色，并非字典驱动），而舌象/脉象纯文本无颜色——三者都**没有真正用上字典色**，易被误导。本次统一改为字典色驱动。
- **新增共享工具** `frontend/src/utils/dictColors.ts`：集中六经/脉类/舌色/五行本色映射 + 亮度自适应 `readableInk`，并带**模块级缓存**的 `useDictColors()`（全应用共享一次 `/dictionaries` 拉取，避免每张就诊卡片重复请求）；取色逻辑 `字典色优先，缺失回退默认色`，故即使库未回填也一定有正确本色。
- **就诊记录展示着色**：
  - `VisitCard.vue`（就诊列表卡片）：证型/舌质/舌苔/脉象均渲染为字典色带色标签；脉象按「、,，/」拆分多值逐个着色。
  - `PatientDetail.vue`（就诊详情弹窗）：舌象/脉象/证型 改用字典色标签。
  - `VisitRecord.vue`（辨证论治摘要）：证型改用字典色标签。
- **录入表单一致**：`VisitRecord.vue` 的舌质/舌苔/脉象/证型四处下拉选项前均加**本色色点**（与 `DiagnosisChat` 一致），录入时也能看到字典色。
- 验证：`python3 -m py_compile` 通过；`npm run build` 通过（vue-tsc 0 错误）。注：字典页已可手动设色或靠种子/回填写库，前端均会如实采用。

### 23. P1-4 迁移规范化：版本表追踪替代游离裸写 ALTER
- **现状梳理**：版本追踪机制（`schema_migrations` 表 + `@migration` 装饰器 + 幂等重放）早已存在于 `app/migrations.py`；真正「游离、未被追踪」的裸 ALTER 只剩 `scripts/migrate_herb_tags.py`（给 `herbs` 加 `grade/flavors/meridians/directions/tags/contraindication`），且它基于**旧 schema 的 `flavor/meridian_tropism/category` 源列**、`flavors` 类型(TEXT) 与模型/m0001(JSON) 冲突、4 列未声明在 `Herb` 模型 → ORM 与库不一致。
- **吸收游离脚本到版本化迁移**：新增 `m0004`，通过受控、带版本号的 `_add_column` 补齐 `herbs` 的 `grade/meridians/directions/tags/contraindication`（`flavors` 已由 m0001 以 JSON 形式补齐，不再重复）；并把原脚本的遗留数据回填逻辑抽成 `_backfill_herb_tags()`，**用源列存在性做硬守卫**（当前模型已无这些源列，现网库为空操作，且杜绝对不存在的列 SELECT 报错）。
- **ORM 与库对齐**：`app/models/herb.py` 补声明 `grade/meridians/directions/tags`（JSON/文本），使 `create_all` 与迁移产物一致，消除「库有列、模型无声明」的漂移。
- **删除游离脚本** `scripts/migrate_herb_tags.py`（职责已并入 m0004，且确认无代码引用）。
- **测试隔离修复（必要前置）**：原 `tests/test_migrations.py` 只替换 `engine` 未替换 `SessionLocal`，导致 `m0002/m0003` 打到共享 `tcm_doctor.db` 而缺表；改为一并替换 `SessionLocal` 指向临时引擎，并扩充断言覆盖 m0004 新增列与版本号 `["0001".."0004"]`、幂等计数=4。
- 验证：`python3 -m pytest tests/ -q` 全绿（6 passed）；`py_compile` 通过。
- 备注：`pyproject.toml` 仍声明未使用的 `alembic`（项目刻意用自研轻量迁移替代其 SQLite batch 繁琐）；本次未改动，留作后续清理项。