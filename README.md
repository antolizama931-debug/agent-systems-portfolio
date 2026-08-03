# Agent Systems Portfolio

统一项目导航站，连接两个独立部署的 Agent 应用：

- **OnCall Agent**：可审计的智能运维事故响应系统；
- **PatchPilot**：审批门控的软件维护智能体。

## Monorepo 结构

```text
.
├── index.html / styles.css / app.js   # GitHub Pages 统一导航
├── oncall-agent-build/                # Railway Service 1
└── patchpilot-agent/                  # Railway Service 2
```

## 发布

1. 根目录通过 `.github/workflows/pages.yml` 发布 GitHub Pages；
2. Railway 为两个 Agent 创建独立 Service；
3. Service Root Directory 分别设置为 `/oncall-agent-build` 与 `/patchpilot-agent`；
4. 获得 PatchPilot 公网域名后，更新根目录 `config.js`；
5. `config.js` 只允许放公开 URL，禁止放任何 API Key 或 Token。

当前 PatchPilot Railway 地址：

```text
https://patchpilot-agent-production.up.railway.app
```

在 GitHub Pages 发布完成前，统一导航也会由 PatchPilot 暂时托管在 `/portfolio/`。
