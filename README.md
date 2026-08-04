# Agent Systems Portfolio

统一项目导航站，连接两个独立部署的 Agent 应用：

- **OnCall Agent**：可审计的智能运维事故响应系统；
- **MewCode Showcase**：带结构化工具轨迹和权限门的编程智能体在线演示。

## Monorepo 结构

```text
.
├── index.html / styles.css / app.js   # GitHub Pages 统一导航
├── oncall-agent-build/                # Railway Service 1
└── patchpilot-agent/                  # MewCode Showcase（目录名兼容既有 Railway Root）
```

## 发布

1. 根目录通过 `.github/workflows/pages.yml` 发布 GitHub Pages；
2. Railway 为两个 Agent 创建独立 Service；
3. Service Root Directory 分别设置为 `/oncall-agent-build` 与 `/patchpilot-agent`；
4. 获得 MewCode 公网域名后，更新根目录 `config.js`；
5. `config.js` 只允许放公开 URL，禁止放任何 API Key 或 Token。

当前 MewCode Railway 地址：

```text
https://mewcode-production.up.railway.app
```

统一导航由 GitHub Pages 提供，MewCode 服务内保留返回入口。
