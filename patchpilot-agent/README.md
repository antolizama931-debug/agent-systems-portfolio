# PatchPilot Agent

PatchPilot 是一个可审计、带人工审批的软件维护智能体演示。它使用 LangGraph 编排仓库分析、维护计划和补丁预览，通过 SQLite 保存运行轨迹，并在人工批准后将固定补丁应用到临时 fixture 副本中，执行真实 Pytest，再完成独立审查。

如果你第一次接触该项目，请先阅读：[PatchPilot 项目入门与接手指南](docs/PROJECT_GUIDE.zh-CN.md)。文档从用户流程、架构、核心代码、API、MCP、安全边界、测试、部署和面试演示逐步说明，并明确区分当前实现与后续扩展。

## 当前边界

公开版本不是通用编码 Agent：

- 只处理仓库内两个版本化 Python fixture；
- 不接受任意 Git URL、代码上传、文件路径或测试命令；
- 不持有 GitHub 写权限，不创建或合并真实 Pull Request；
- 测试只执行服务端固定的 `python -m pytest -q`，超时为 10 秒；
- SQLite 适合 Railway 单实例演示，多副本生产环境需要 PostgreSQL；
- Railway 运行时不使用 Docker-in-Docker。生产级不可信代码执行应放到独立沙箱服务。

## 工作流

```text
Repo Analyst → Coordinator → Patch Preview → Human Approval
                                             ├─ Reject → Stop
                                             └─ Approve → Apply → Pytest → Review
```

运行轨迹、补丁、审批人、测试输出和审查结论均写入 `data/patchpilot.db`。

## MCP

服务通过官方 MCP Python SDK 暴露 Streamable HTTP 端点：

```text
http://127.0.0.1:8010/mcp/
```

公开工具：

| 工具 | 权限 | 说明 |
|---|---|---|
| `repo_list_files` | 只读 | 列出固定 fixture 文件 |
| `repo_read_file` | 只读 | 读取固定 fixture 内的文本文件 |
| `patch_preview` | 只读 | 生成预定义最小补丁，不修改文件 |

真正的补丁应用函数不暴露为 MCP 工具，只能在 API 记录人工批准后调用。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.ps1
```

打开：

- 应用：`http://127.0.0.1:8010`
- API：`http://127.0.0.1:8010/docs`
- MCP：`http://127.0.0.1:8010/mcp/`

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Railway

仓库采用隔离式 Monorepo。为 PatchPilot 创建单独 Railway Service，并设置：

```text
Root Directory: /patchpilot-agent
Config File: /patchpilot-agent/railway.json
Health Check: /api/health
```

如需跨部署保存运行记录，挂载 Railway Volume，并设置：

```text
PATCHPILOT_DATA_DIR=/data
```

OnCall Agent 使用另一个 Service，Root Directory 为 `/oncall-agent-build`。根目录静态站作为两个 Agent 的统一项目导航。
