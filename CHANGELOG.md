# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.3.1] - 2026-08-09

### Added

- 对齐微软 data_model 的双向溯源：`TextUnit.entity_ids/relationship_ids/covariate_ids`，`Document↔TextUnit`。
- 建库流水线 `link_provenance`：抽取后回填正向/反向索引并落库。
- 新组件 **GraphRAG 溯源查询**：实体→原文、原文→实体、文档→图元素。
- Local Search 输出可审计 citations，答案附「可核对原文出处」。
- 去掉旧库迁移/重建双向索引、metadata 边遗留 UI，以及未使用的 GraphRetriever 适配器与依赖。

## [0.3.0] - 2026-08-09

### Added

- 完整 GraphRAG 索引流水线：实体/关系抽取、Data Gleaning、描述摘要、分层社区、社区报告、向量化落库。
- 可选 Claims/Covariates 抽取。
- Local Search（实体邻域 + 关系 + 社区报告 + 原文）。
- Global Search（社区报告 Map-Reduce）与可选动态社区选择。
- 追加合并模式：合并已有实体/关系后重建社区与报告。
- 依赖 `networkx` 用于分层社区检测。

### Changed

- 检索模式由 GraphRetriever Eager/MMR 升级为 Local/Global Search。
- 知识库前缀命名：自动派生 `_chunks/_entities/...`，避免重复 `_chunks`。
- 维护组件清空覆盖完整知识模型表。

### Removed

- 以「仅抽实体名 + metadata 边遍历」冒充 GraphRAG 的建库/检索主路径。

## [0.2.0] - 2026-08-08

### Added

- GraphRAG 知识库实例组件（AstraDB / ArangoDB）。
- 入库建图组件：文档入库、向量索引、图边创建。
- GraphRAG 检索组件（Astra 使用 GraphRetriever，Arango 自研图扩展）。
- 知识库维护组件：统计、按 ID 删除、清空。
- 本地开发脚本：`scripts/setup-env.sh`、`scripts/deploy-to-docker.sh`。

## [0.1.0] - 2026-08-08

### Added

- 初始 extension 脚手架与 Hello 级验证通路。

[Unreleased]: https://github.com/loadingvx/lfx-liam-bundle/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/loadingvx/lfx-liam-bundle/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/loadingvx/lfx-liam-bundle/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/loadingvx/lfx-liam-bundle/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/loadingvx/lfx-liam-bundle/releases/tag/v0.1.0
