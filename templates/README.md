# 基础数据包（templates/）

本目录用于**存放 / 编写官方基础数据包**，通过 **GitHub Release 资产**分发给用户。
源码仓库与安装包默认保持「纯框架」（不含临床数据），真实数据包**作为 Release 资产上传，不提交进 git**。

## 用户怎么用

1. 到本仓库的 **Releases** 页面下载需要的基础数据包（如 `tcm-base-core.zip`）；
2. 解压得到若干 JSON 文件；
3. 打开对应模块的**顶部工具栏**（药材字典 / 中药方库 / 针灸方库 / 穴位 / 知识库），点「上传导入」，选择对应 JSON 即可。
   - 仅管理员可见导入按钮（受 `system:write` 权限控制）；
   - 导入为**幂等 upsert**：按药名 / 穴名 / 方名增量写入，重复导入不重复、不冲业务数据；
   - 仅白名单参考知识表会被写入，`patients` / `prescriptions` / `stock_batches` 等业务数据永不打包。

> 随安装包（exe / Docker 镜像）附带的内置数据，可在工具栏点「导入内置」一键载入；
> GitHub 源码克隆版通常不含内置数据，请用「上传导入」。

## 数据包格式（当前：单类型文件）

当前导入以**单个内容类型**的 JSON 文件为单位。后端按「你正在导入的模块」决定类型，文件本体只需提供 `items` 数组：

```json
{
  "type": "herbs",
  "version": 1,
  "items": [
    { "name": "人参", "flavors": ["甘","微苦"], "efficacy": "大补元气", "is_active": true }
  ]
}
```

- `type` 为说明性字段（取值：`herbs` / `classic_formulas` / `acupoint_formulas` / `acupoints` / `knowledge`），实际导入类型由所在模块决定；
- `version` 可选；真正被读取的是 `items` 数组（直接传 `[...]` 也可以）；
- 字段与各模块录入项一致，**无需** `id` / `created_at`；同名自动更新，不存在则新增；
- 最稳妥的做法：在模块工具栏点「导出当前」得到同格式文件，再在此基础上修改。

## 发布包布局（规划：分层 + manifest）

后续正式发布包按**依赖关系**分层，并配 `manifest.json` 作为包清单（字段见 [`manifest.example.json`](manifest.example.json)）：

```
templates/
├── manifest.json          # 清单：版本 / 来源 / 条目数 / sha256 / 依赖
├── core/                  # 药材 + 穴位 + 基础字典（必装，体积小）
├── formulas/              # 中药方库 + 针灸方库（依赖 core）
└── books/                 # 医籍文库（体积最大，可选）
```

`manifest.json` 声明 `schema_version`（防结构漂移）、`sha256`（防传输损坏）、`depends_on`（防引用悬空）。
该分层 bundle 的批量导入为**规划中**能力；现阶段用户仍按上面的「单类型文件」逐类导入即可。

## 版权与免责

内置示例内容整理自《倪海厦人纪》系列及中医经典，**仅供学习交流，不构成任何临床诊疗依据**。
使用前请对照权威典籍核对；若用于教学分享或二次分发，请注意相关版权。
