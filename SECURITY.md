# 安全策略

感谢你帮助保护 `lfx-liam-bundle` 与其用户。

## 支持的版本

| 版本  | 是否接受安全修复 |
|-------|------------------|
| 0.2.x | ✅               |
| < 0.2 | ❌               |

## 如何报告漏洞

**请不要**通过公开 GitHub Issue 披露安全漏洞。

请通过以下方式私下报告：

1. 使用 GitHub 仓库的 **Security Advisories**（Prefered）：  
   `https://github.com/loadingvx/lfx-liam-bundle/security/advisories/new`
2. 若无法使用 Advisories，请向维护者发送私信，并在标题标明 `[SECURITY]`。

报告请尽量包含：

- 影响版本与运行环境（Langflow / lfx 版本、后端 Astra 或 Arango）
- 复现步骤与最小示例
- 潜在影响（数据泄露、越权、DoS 等）
- 已知缓解措施（如有）

我们会在 **7 个工作日**内确认收到，并在确认后给出修复计划时间表。

## 范围说明

本扩展会连接外部数据库（AstraDB / ArangoDB）。请勿在 Issue、PR、日志样例中粘贴真实 Token、密码或生产连接串。演示请使用脱敏占位符。
