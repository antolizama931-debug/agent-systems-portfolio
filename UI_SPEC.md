# Agent Systems UI Specification

## Design direction

“Editorial technical portfolio”：用编辑型排版和轻量系统图表达工程能力，避免把作品集做成泛化的 SaaS 仪表盘。

- Canvas：暖白纸面 + 极浅网格，制造稳定、专业的阅读背景。
- Typography：大标题负责定位项目价值，等宽小标签负责表达运行时状态。
- Color：Cobalt 用于 OpsPilot 的安全执行主题，Teal 用于 ReliabilityLab 的评测主题。
- Surface：白色卡片只承载信息分组，不使用大面积渐变和过重阴影。
- Motion：只保留按钮 hover 和 iframe 状态变化，降低展示页噪声。

## Information architecture

```text
index.html
├── OpsPilot card → opspilot.html → Railway live iframe
└── ReliabilityLab card → reliability.html → Railway live iframe
```

## Components

- `site-header`：品牌、项目锚点、GitHub 外链。
- `lab-console`：作品集级总览，展示系统数、场景数和共享工具链。
- `system-card`：每个项目的工程问题、能力标签、CSS mini visualization、状态和入口。
- `architecture-card`：项目详情页的架构/指标摘要。
- `demo-shell`：模拟浏览器工具栏 + 真实 Railway iframe。
- `service-state`：在线、未配置和重试状态；颜色不作为唯一状态信号，始终同步文字。
- `detail-points`：项目的三项可面试技术重点。

## Reliability fixes

- 每个项目页在 `body[data-live-url]` 和 iframe `src` 中保留公开 Railway URL 兜底。
- `config.js`、`showcase.js` 和 `styles.css` 使用版本化 query string，绕过 GitHub Pages 的静态资源缓存。
- `showcase.js` 优先读取 `config.js`，缺失时回退到 HTML 公开 URL。
- 在线服务失败时显示“RETRY IN NEW TAB”，不再显示错误的“部署完成后更新 config.js”。
- 不在公开配置中保存 API Key、Railway Token 或模型凭证。

## Responsive / accessibility

- 1160px 内容宽度；940px 开始单列 hero；760px 以后卡片、方法和详情区变为单列。
- 关键入口使用真实链接，键盘可聚焦；iframe 带有 `title`。
- 状态同时使用文字、颜色和状态点；`prefers-reduced-motion` 会降低过渡动画。
- 不引入外部字体、图片或第三方脚本，GitHub Pages 可独立加载。

## Acceptance checklist

- [ ] 导航页两个项目按钮分别进入两个详情页。
- [ ] 详情页首次加载即有 iframe `src`，不依赖异步 config 才能显示功能。
- [ ] 两个页面均显示 `ONLINE`，失败时提供新标签页重试入口。
- [ ] GitHub Pages 资源带版本号，配置更新不会长期命中旧缓存。
- [ ] 移动端无横向滚动，项目卡片仍保留入口和状态。
