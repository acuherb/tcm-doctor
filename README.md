# 中医诊所管理平台 (tcm-doctor)

以《伤寒论》《金匮要略》与**倪海厦经方体系**为核心的诊所管理平台：从问诊十问辨证，到六经推荐经方、一键开方发药，全流程闭环。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Electron 主进程                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ BrowserWindow │  │ PythonRunner │  │  Preload 桥接  │  │
│  │  (Chromium)   │  │ (子进程管理)  │  │ (IPC 通信)    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘  │
└─────────┼─────────────────┼─────────────────────────────┘
          │                 │
          ▼                 ▼
┌──────────────────┐  ┌──────────────────────────────────┐
│   Vue3 前端 SPA   │  │        FastAPI 后端 (8765)        │
│ ┌──────────────┐ │  │ ┌──────────────────────────────┐ │
│ │ Element Plus │ │  │ │          Routers              │ │
│ │ ECharts      │ │  │ │  /patients  /herbs  /rx     │ │
│ │ Pinia        │ │  │ │  /diagnosis  /knowledge      │ │
│ │ Vue Router   │ │  │ │  /stats  /backup  /config    │ │
│ └──────────────┘ │  │ └──────────────────────────────┘ │
│ ┌──────────────┐ │  │ ┌──────────────────────────────┐ │
│ │   api.ts     │ │  │ │         Services              │ │
│ │ (axios 请求) │ │──│ │  AI辨证  配伍检查  体质评估   │ │
│ └──────────────┘ │  │ │  向量检索  库存管理           │ │
└──────────────────┘  │ └──────────────────────────────┘ │
                      │ ┌──────────────────────────────┐ │
                      │ │      Data Layer               │ │
                      │ │  SQLite + SQLAlchemy 2.0      │ │
                      │ │  ChromaDB (可选)              │ │
                      │ └──────────────────────────────┘ │
                      └──────────┬───────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ DeepSeek │ │ 硅基流动  │ │ 知识库JSON│
              │  API     │ │  Vision  │ │  (29部)  │
              │(文字对话) │ │(图片识别)│ │          │
              └──────────┘ └──────────┘ └──────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面壳 | Electron 28 |
| 前端 | Vue 3 + Element Plus + TypeScript + Pinia + ECharts |
| 后端 | Python FastAPI + SQLAlchemy 2.0 + SQLite |
| AI 文字 | DeepSeek API (deepseek-chat / deepseek-reasoner) |
| AI 图片 | 硅基流动 Vision API (Kimi-K2.6) |
| 知识检索 | RAG 多路召回 (关键词 + ChromaDB 语义向量) |
| 打包 | electron-builder (NSIS) + PyInstaller |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- npm

### 安装与启动

```bash
# 1. 克隆项目
git clone https://github.com/acuherb/tcm-doctor.git
cd tcm-doctor

# 2. 安装后端依赖
cd backend
pip install fastapi uvicorn sqlalchemy pydantic-settings httpx python-multipart

# 3. 安装前端依赖
cd ../frontend
npm install

# 4. 启动后端（端口 8765）
cd ../backend
python -m uvicorn app.main:app --reload --port 8765

# 5. 启动前端（端口 5173，自动代理 /api → 后端）
cd ../frontend
npm run dev
```

浏览器访问 `http://localhost:5173`，进入系统设置配置 DeepSeek API Key 即可使用。

### API Key 配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| API Key | DeepSeek 对话模型密钥 | `sk-xxx` |
| 对话模型 | 纯文字对话使用的模型 | `deepseek-chat` |
| Base URL | DeepSeek API 地址 | `https://api.deepseek.com` |
| Vision 模型 | 图片识别模型（第三方） | `Pro/moonshotai/Kimi-K2.6` |
| Vision URL | Vision API 地址 | `https://api.siliconflow.cn/v1` |
| Vision Key | Vision API 密钥（留空则复用对话 Key） | `sk-yyy` |

> 图片识别为可选功能。未配置 Vision 时，上传图片不会报错，AI 将基于文字描述进行分析。

### 桌面端打包

```bash
# 1. 编译 Electron 主进程
cd electron && npx tsc && cd ..

# 2. 构建前端
cd frontend && npm run build && cd ..

# 3. 打包后端为 exe（需先 pip install pyinstaller）
cd backend && python -m PyInstaller build.spec && cd ..

# 4. 生成安装包（需配置国内镜像）
ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/" \
ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/" \
npx electron-builder --win --x64
```

产出：`dist-electron/tcm-doctor-setup-0.1.0.exe`

## 功能模块

### 患者管理
- 患者信息 CRUD + 分页搜索
- 就诊记录（四诊信息 + 辨证论治 + AI 辅助辨证 + 问诊十问 同一页面一体化完成）
- 问诊十问（倪海厦经方家十问，预定义选项 + 自填，按原文判据推出六经/寒热/虚实偏性，随病例持久化）
- 患者档案链（以**就诊时间线为主轴**聚合呈现：每条就诊卡片内联该次的问诊十问 + 四诊辨证 + 处方；历史未关联就诊的十问单独置于底部区块）

### 药品管理
- 药材字典（229 味，覆盖 18 个分类，支持异名搜索 + 批量导入/导出 JSON）
- 库存管理（入库/出库/预警/仓位/批次）
- 配伍禁忌引擎（十八反/十九畏 + 孕妇禁忌 + 毒性药检测）

### 针灸穴位库
- 腧穴字典（170 穴，合并倪师穴位索引 + 针灸 164 项，按十四经 / 任督 / 奇穴归类，带定位详情）
- 穴位增删改查 + 关键词搜索 / 按归经筛选

### 处方管理
- 处方编辑器（经典方导入 → 加减药味 → 煎服法 → 实时安全检查）
- **药方 + 针灸方双区块并列**：一张处方可同时开具中药方与针灸方（也可只开其一），自动判定 `prescription_type`（药方 / 针方 / 混合）
  - 🌿 **中药方**：方名 / 煎法 / 剂数 / 服法 / 药味明细
  - 🪡 **针灸方**：方案名（独立字段 `acupoint_formula_name`，不与中药方名混用）/ 针法 / 操作频次（每日·隔日·每周…）/ 疗程天数（数字）/ 配穴明细（穴位·针法·留针·顺序·备注）
- 处方审核 + 发药 + 库存扣减
- **经典方剂库**（经方全集，支持新增/编辑/删除/导入/导出 JSON，按六经归档）
- **针灸方库**（新增，与经典方库对齐）：把一组穴位按方名固化成可复用针灸方，内置安神定志/健脾和胃/腰痛/疏风解表/调经/醒脑开窍等 6 首针方（来源标注倪海厦·针灸 / 通用）；支持 CRUD + 导入/导出 JSON
  - 「引入到处方编辑器」可一键预填针灸方名 / 针法 / 频次 / 疗程天数 + 全部配穴
  - 处方表通过 `acupoint_formula_id` 关联针灸方库（与 `classic_formula_id` 对称）
- 辨证-选方联动（问诊十问辨证结果 → 推荐对应经方 → 一键导入开方，形成闭环）
- 处方列表 / 详情弹窗 / 打印模板均完整展示中药方与针灸方（列表新增「针灸方」列；打印中剂数/煎法/服法归属中药方区块，置于针灸方之前）

### AI 智能问诊
- 对话式问诊（DeepSeek + RAG 知识库增强）
- 四诊辨证分析（结构化四诊输入 + AI 综合辨证）
- 图片识别（舌苔照片/面色/化验单/影像报告 → AI 读取分析）
- 中西医结合（西医病名/化验指标 → 中医辨证 + 中西医结合治疗方案）
- 安全硬约束（配伍禁忌 + 孕妇禁忌 + 毒性药自动检测）

### 知识库
- 医籍文库（29 部中医经典，1313 条知识条目）
- 知识检索（关键词 + 语义向量双路检索）
- 经典方剂数据（伤寒论/金匮要略/温病条辨等出处方剂）

### 数据统计
- 工作台仪表盘（统计卡片 + 7 日就诊趋势 + 库存预警 + 待办）
- 统计报表（就诊趋势/用药分析/处方统计 ECharts 图表）

### 系统管理
- 系统设置（API 配置 + 连接测试 + 持久化到 .env）
- 登录与权限：支持**游客免密登录**（`ALLOW_GUEST_LOGIN`，默认开启）仅浏览；所有**导出 / 写操作仅限管理员（admin）**——前端对游客隐藏全部导出入口，后端 `/backup/export` 等接口对游客返回 403，防止患者隐私（PII）泄露
- 数据备份/恢复（SQLite 导出/导入/重置，仅 admin）

## 数据概况

| 数据类别 | 数量 |
|----------|------|
| 药材 | 229 味（18 个分类） |
| 经典方剂 | 146 首（伤寒论 112 + 金匮要略 + 后世方，0 缺失，六经归档） |
| 针灸方库 | 6 首（安神定志 / 健脾和胃 / 腰痛 / 疏风解表 / 调经 / 醒脑开窍，来源标注倪海厦·针灸 / 通用） |
| 穴位 | 170 穴（倪师穴位索引 + 针灸 164 项，按归经/奇穴归类） |
| 配伍禁忌规则 | 35 条（十八反 + 十九畏） |
| 知识库条目 | 1313 条 |
| 知识库来源 | 29 部中医经典 |

### 知识库收录典籍

| 类别 | 典籍 |
|------|------|
| 经典 | 伤寒论、金匮要略、黄帝内经·素问、黄帝内经·灵枢、温病条辨 |
| 专科 | 傅青主女科、妇人大全良方、脾胃论、丹溪心法 |
| 针灸 | 中医针灸学、针灸甲乙经 |
| 医案 | 临证指南医案、黄煌经方医案、岳美中医案集、蒲辅周医案、经方实验录 |
| 综合 | 医学衷中参西录 |

## 项目结构

```
tcm-doctor/
├── electron/                # Electron 主进程
│   ├── main.ts             # 窗口管理 + 后端启动
│   ├── preload.ts          # 安全桥接
│   ├── python-runner.ts    # Python 子进程管理
│   └── tsconfig.json
├── frontend/                # Vue3 前端
│   ├── src/
│   │   ├── layouts/        # 主布局（侧边栏导航）
│   │   ├── views/          # 页面组件
│   │   │   ├── dashboard/  # 工作台 + 统计报表
│   │   │   ├── patient/    # 患者管理 + 就诊记录 + 问诊十问
│   │   │   ├── herb/       # 药材字典 + 库存管理
│   │   │   ├── prescription/ # 处方编辑 + 经典方库
│   │   │   ├── knowledge/  # 知识检索 + 医籍文库
│   │   │   ├── diagnosis/  # 智能问诊（AI + 图片识别）
│   │   │   └── settings/   # 系统设置
│   │   ├── components/     # 公共组件（药材选择器/配伍警报）
│   │   ├── utils/          # api.ts（axios 封装）
│   │   └── styles/         # 中医暖色主题
│   └── vite.config.ts
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # FastAPI 入口 + CORS + 配置API
│   │   ├── config.py       # pydantic_settings 配置管理
│   │   ├── database.py     # SQLAlchemy 引擎 + 会话
│   │   ├── models/         # ORM 模型（患者/就诊/药材/方剂/知识库）
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── routers/        # API 路由（患者/药品/处方/针灸方库/针灸/知识/问诊/统计/备份/设置等模块）
│   │   ├── services/       # 业务逻辑
│   │   │   ├── ai_diagnosis_service.py  # AI 辨证（DeepSeek + Vision + RAG）
│   │   │   ├── incompatibility_checker.py # 配伍禁忌检查
│   │   │   ├── constitution_evaluator.py  # 问诊十问/六经辨证评估
│   │   │   └── vector_store.py            # ChromaDB 向量检索
│   │   └── data/           # 种子数据 + 29 部典籍 JSON
│   ├── run.py              # PyInstaller 入口
│   ├── build.spec          # PyInstaller 配置
│   ├── tcm_doctor.db       # SQLite 数据库（运行时由种子脚本生成，已被 .gitignore 忽略，不入库）
│   └── pyproject.toml
├── resources/               # 应用图标
├── electron-builder.yml     # electron-builder 打包配置
└── package.json             # Electron 根配置
```

## API 端点

| 模块 | 路径 | 说明 |
|------|------|------|
| 系统 | `GET /health` | 健康检查 |
| 系统 | `GET/PUT /api/v1/config` | 系统配置（API Key 持久化） |
| 患者 | `/api/v1/patients` | 患者 CRUD |
| 患者 | `/api/v1/patients/{id}/visits` | 就诊记录 |
| 患者 | `/api/v1/patients/{id}/constitution` | 问诊十问 / 体质辨识（支持 `visit_id` 绑定到具体就诊） |
| 药品 | `/api/v1/herbs` | 药材字典 + 详情 |
| 药品 | `/api/v1/herbs/inventory/*` | 库存管理（入库/出库/预警/汇总） |
| 药品 | `/api/v1/herbs/incompatibility-check` | 配伍禁忌检查 |
| 处方 | `/api/v1/prescriptions` | 处方 CRUD + 审核 + 发药（含 `acupoint_formula_name` / `acupoint_technique` / `treatment_frequency` / `treatment_days` 四个针灸方顶层字段） |
| 处方 | `/api/v1/prescriptions/classic-formulas` | 经典方剂库 |
| 处方 | `/api/v1/acupoint-formulas` | 针灸方库 CRUD（搜索 / 出处筛选 / 导入 / 导出） |
| 处方 | `/api/v1/acupoint-formulas/{id}` | 针灸方详情（供处方编辑器引入预填） |
| 问诊 | `POST /api/v1/diagnosis/chat` | 对话式智能问诊 |
| 问诊 | `POST /api/v1/diagnosis/analyze` | 四诊辨证分析 |
| 问诊 | `POST /api/v1/diagnosis/upload-image` | 上传诊断图片 |
| 问诊 | `GET /api/v1/diagnosis/status` | AI 服务状态 |
| 知识 | `/api/v1/knowledge/search` | 知识检索 |
| 知识 | `/api/v1/knowledge/entries` | 知识条目管理 |
| 知识 | `/api/v1/knowledge/sources` | 知识来源列表 |
| 统计 | `/api/v1/stats/dashboard` | 工作台数据 |
| 统计 | `/api/v1/stats/visits` | 就诊统计 |
| 备份 | `/api/v1/backup/export` | 导出备份 |
| 备份 | `/api/v1/backup/import` | 导入恢复 |

## 快速启动

```bash
# 方式一：一键脚本（自动检查/安装依赖、生成 .env、启动前后端）
./start.sh            # 前后端开发模式（后端 :8765 + 前端 vite）
./start.sh electron   # Electron 桌面壳开发模式

# 方式二：手动（项目根目录）
npm install           # 根依赖（concurrently / electron / typescript）
cd frontend && npm install && cd ..
cd backend && python3 -m pip install -e ".[ai]"   # 含 chromadb / openai
npm run dev           # 同时启动后端 uvicorn 与前端 vite
```

> 首次运行若缺少 `backend/.env`，脚本会生成默认开发配置；将 `DEEPSEEK_API_KEY` 填入即可启用 AI 辨证。
> 后端 API 文档：http://127.0.0.1:8765/docs

## Docker 容器部署（群晖 Container Manager / 服务器）

生产部署使用**单镜像**（内置前端静态产物 + FastAPI 后端，由 FastAPI 直接托管页面），所有持久化数据统一落在容器内的 `/data` 目录，挂载宿主机目录即可在删容器重建后保留数据。

### 1. 构建并导出镜像（在有 Docker 的构建机上）

```bash
cd tcm-doctor
docker build -t tcm-doctor:latest .
docker save tcm-doctor:latest -o tcm-doctor-image.tar
```

> 多阶段构建：前端用 `node:20-alpine` 构建 `dist`，后端用 `python:3.12-slim` 运行；镜像约 60–70MB，无需在宿主机装 Node/Python。

### 2. 群晖 Container Manager 导入并运行

- `映像 → 操作 → 导入 → 从文件`，选择 `tcm-doctor-image.tar`。
- 选中镜像 → **运行**，在向导里配置：
  - **端口**：本地 `8765` → 容器 `8765`（TCP）。务必手动指定，勿用随机端口，否则外网/反代会连错。
  - **卷（关键）**：本地目录（如 `docker/tcm-data`）→ 容器 `/data`。数据库与 `.env` 配置都在此，挂载后**删容器重建也不丢数据**。
  - 环境变量（可选）：`PORT`（默认 8765）、`DATA_DIR`（默认 `/data`）、`ALLOW_GUEST_LOGIN`（默认 `true` 开启游客浏览）。

### 3. 首次启动

- 容器启动后自动建表并灌入种子数据（药材 229 味、经典方 146 首、穴位 170、知识库 1313 条），首次约需 10–20 秒。
- 浏览器访问 `http://<主机IP>:8765`，默认账号 `admin / admin123`（首次登录建议改密）；也可「游客登录（仅浏览）」。
- 「系统设置」填入 DeepSeek API Key 即启用 AI 辨证。

### 4. 更新镜像（保留数据）

> 重要：更新前先在**「系统管理 → 数据备份 → 导出」**下载备份文件，以防万一。

1. 群晖删除旧 `tcm-doctor` 容器与旧映像；
2. 重新导入新 `tcm-doctor-image.tar` 并运行（**保持同样的 `/data` 卷映射**）；
3. 如需恢复历史数据，「系统管理 → 数据备份 → 导入」选备份文件即可。

### 5. 外网访问（群晖反代 / Cloudflare）

- 先内网直连 `http://<群晖IP>:8765` 确认应用本身正常；
- 若经反向代理或 Cloudflare（如 `tcm.xxx.xyz`）出现 **502 Bad Gateway**，通常是反代「目标端口」没指向群晖主机的 `8765`——把反代目标主机设为 `127.0.0.1`、目标端口设为 `8765` 即可。

## 脚本说明（一次性 / 种子）

后端 `backend/` 目录下存在若干**一次性数据处理脚本**，它们不参与应用常规运行，仅用于历史数据导入或校验，**不要**当作常驻入口：

| 脚本 | 用途 | 状态 |
| --- | --- | --- |
| `seed_acupoints.py` / `seed_dictionaries.py` | 主数据（腧穴 / 字典）种子，**已接入** `app/seed.py` 的 `seed_all()`，随应用启动自动增量导入 | ✅ 常驻可用 |
| `seed_nihaixia.py` | 导入倪海厦经方体系数据（一次性） | ⚠️ 一次性，已并入主库后无需再跑 |
| `_seed_formulas.py` / `_seed_jingfang.py` | 早期经典方 / 经方导入（一次性） | ⚠️ 一次性，已被 `app/data/classic_formulas.json` 取代 |
| `seed_posts.py` | 导入文章/帖子演示数据（一次性） | ⚠️ 一次性 |
| `_check_herbs_coverage.py` | 校验药材数据覆盖率（诊断用） | ⚠️ 诊断/校验工具 |
| `app/data/generate_herbs.py` / `generate_knowledge.py` | 由原始数据生成 `herbs.json` / 知识库 JSON（构建期工具） | ⚠️ 离线生成工具 |

> 应用首次启动由 `app/main.py` 的 lifespan 调用 `app/seed.py → seed_all()` 自动完成建表与种子导入；
> 如手动运行请使用 `python -m app.seed`（在 `backend/` 目录下），它会自动建表并幂等导入，不会清空既有数据。

## 致谢

本项目基于 [OMDOCTOR](https://github.com/sunshengzhuo/OMDOCTOR) 进行二次开发，感谢原作者 [@sunshengzhuo](https://github.com/sunshengzhuo) 提供的优秀开源基础。