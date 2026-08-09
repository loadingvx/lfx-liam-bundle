# 工具包总览

## 定位

`lfx-liam-bundle` 是个人 **Langflow Extension 工具包**，不是单一功能产品。  
当前已提供一组 GraphRAG 控件；后续其它能力也应挂在同一 bundle `liam` 下。

## 架构

```text
langflow.extensions 入口
  └─ lfx_liam_bundle / extension.json
       ├─ bundle：liam
       │    └─ components/liam/*      # Langflow 界面控件
       └─ 领域包（如 graphrag/*）     # 控件背后的可复用逻辑
```

| 层级 | 路径 | 职责 |
|------|------|------|
| 扩展清单 | `extension.json` | 扩展 id、展示名、bundle 注册 |
| 控件层 | `src/lfx_liam_bundle/components/liam/` | 参数、校验、中文提示、接线 |
| 领域层 | `src/lfx_liam_bundle/graphrag/` 等 | 与 UI 解耦的业务实现 |

## 扩展新组件时

1. 在 `components/liam/` 新增组件类并导出。  
2. 在 `docs/components/` 写说明，并更新 [index.md](index.md) 表格。  
3. 复杂逻辑抽到独立领域包，避免所有功能都塞进 GraphRAG。

## 相关文档

- 组件列表：[index.md](index.md)  
- 安装：[guides/install.md](guides/install.md)  
- 最短 Flow：[guides/quickstart.md](guides/quickstart.md)
