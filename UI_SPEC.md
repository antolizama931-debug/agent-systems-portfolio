# Agent Engineering Lab UI Specification

## 目标

这是一套面向技术招聘者的 GitHub Pages 作品集界面。核心任务是让访客在 10 秒内完成：

1. 理解两个项目分别解决什么问题；
2. 进入对应的项目展示页；
3. 在展示页中直接操作 Railway 在线服务；
4. 查看源码与工程边界。

## 信息架构

```text
导航页 index.html
├── OpsPilot 展示页 opspilot.html
│   └── Railway iframe：安全可恢复 Agent 运行时
└── ReliabilityLab 展示页 reliability.html
    └── Railway iframe：故障注入与可靠性评测
```

## 设计令牌

| 类别 | 令牌 | 取值/原则 |
| --- | --- | --- |
| 背景 | `--ink` | 深蓝黑，强调工程工具感 |
| 主文字 | `--paper` | 高对比浅色 |
| 次文字 | `--muted` | 降低说明文字视觉权重 |
| OpsPilot 强调色 | `--lime` | 表示安全边界与可执行状态 |
| ReliabilityLab 强调色 | `--orange` | 表示故障注入、诊断和实验 |
| 边界 | `--line` | 低对比细线，区分卡片层级 |
| 圆角 | `--radius-*` | 卡片适中圆角，避免消费级 SaaS 风格 |
| 字体 | system stack | 不依赖外部字体，保证 GitHub Pages 可用 |

## 组件与状态

- `project-card`：项目卡片，包含场景、核心流程、能力标签和两个动作。
- `availability`：部署状态。没有公开 URL 时显示 `CONFIGURING`；配置 URL 后显示 `ONLINE`。
- `primary-button`：打开在线系统，在新标签页打开公开 Railway URL。
- `secondary-button`：查看源码或返回导航。
- `live-frame-wrap`：在线服务容器。没有 URL 时显示可解释的离线占位；有 URL 时加载 iframe。
- `detail-grid`：以三项短说明展示架构、可靠性和可观测性，不把页面变成长文档。

## 交互约束

- 导航页的两个项目入口始终可用，不依赖 Railway 是否在线。
- 在线按钮和 iframe 只从 `config.js` 读取公开 URL。
- 未配置 URL 时按钮禁用，并明确提示“部署后更新 `config.js`”，不跳转到空地址。
- 在线页面使用懒加载 iframe，避免导航页首屏同时请求两个后端。
- GitHub 与源码链接在新标签页打开，并设置 `rel="noreferrer"`。
- 生产运维项目明确显示“模拟基础设施”，避免访客误解为真实生产操作。

## 响应式与可访问性

- 使用 `meta viewport`、网格自动折叠和移动端单列布局。
- 颜色不是唯一状态信息：状态同时有文字和圆点。
- iframe 具备 `title`；按钮动作使用可读文本，不使用只有图标的关键入口。
- 所有卡片入口保持键盘可聚焦，焦点样式由浏览器默认 outline 与按钮边界共同提供。
- 不引入外部图片或第三方脚本，减少 GitHub Pages 运行时依赖。

## 验收清单

- [ ] 导航页两个入口分别跳转到 `opspilot.html` 与 `reliability.html`。
- [ ] 两个展示页都能显示架构说明、源码链接和在线服务区域。
- [ ] `config.js` 配置公开 URL 后，在线按钮与 iframe 同时生效。
- [ ] 两个 Railway 服务的 `/api/health` 返回 `status=ok`。
- [ ] 移动端宽度下页面无横向滚动，项目卡片保持可读。
- [ ] 公开仓库扫描不到 API Key、Railway Token 或 `.env`。
