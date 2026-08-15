# Agent Engineering Lab

面向 Agent 应用开发与 Agent 算法岗位的可运行项目作品集。GitHub Pages 提供统一导航，两个项目展示页通过公开 Railway URL 嵌入实际服务，因此访客可以直接操作项目功能。

## 在线入口

- `index.html`：项目导航页，包含 OpsPilot 与 ReliabilityLab 两个入口。
- `opspilot.html`：安全、可恢复、带人工审批的 Agent 运行时展示页。
- `reliability.html`：故障注入、策略对照和最终状态验收展示页。
- `config.js`：只保存公开 URL；不保存 API Key、Railway Token 或模型凭证。

## 两个项目

### OpsPilot

安全可恢复的生产运维 Agent 运行时，展示工具契约、策略门禁（Policy Gate）、人工审批（Human-in-the-Loop）、SQLite checkpoint 和可回放执行轨迹。

项目展示页：[`opspilot.html`](./opspilot.html)

### AgentReliabilityLab

面向工具调用 Agent 的执行型可靠性评测框架，覆盖固定场景、timeout/HTTP 500 故障注入、策略基线、恢复率与未授权副作用统计。

项目展示页：[`reliability.html`](./reliability.html)

## 部署约定

两个服务共用仓库根目录的 `Dockerfile.railway` 与 `railway.json`，通过 Railway 环境变量区分应用：

| 服务 | `AGENT_APP` | 健康检查 | 公开页面 |
| --- | --- | --- | --- |
| OpsPilot | `opspilot` | `/api/health` | `/` |
| ReliabilityLab | `reliability` | `/api/health` | `/` |

部署后，将两个公开 HTTPS 地址写入 `config.js` 的 `opspilotUrl` 与 `reliabilityUrl`，GitHub Pages 会自动把项目展示页的 iframe、在线按钮和状态标签更新为真实服务。

## 本地运行

```powershell
python -m opspilot
python -m agent_reliability_lab
```

访问 `http://127.0.0.1:8787/` 或通过 `PORT` 环境变量指定端口。运行测试：

```powershell
python -m unittest discover -s tests -v
```

## 安全边界

- 线上演示使用模拟基础设施，不连接真实生产环境。
- `.env`、模型密钥和 Railway 凭证不进入此公开仓库。
- iframe 只在 `config.js` 中加载显式配置的公开 URL。

本仓库只发布导航页、项目展示页和 UI 规范；运行时代码不在未经确认的情况下同步到公开仓库。旧版 `oncall-agent-build/` 与 `patchpilot-agent/` 目录暂时保留，用于历史兼容；当前导航与 Railway 目标以 OpsPilot、AgentReliabilityLab 为准。
