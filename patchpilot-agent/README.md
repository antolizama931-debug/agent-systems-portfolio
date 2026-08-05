# MewCode Showcase

MewCode Showcase 是本地终端编程智能体 MewCode 的浏览器安全演示层。它真实执行“模型决策 -> 结构化工具 -> 工具观察 -> 下一轮决策”的有界 Agent Loop，但不向公网开放模型密钥、任意文件路径、外部仓库或 Shell。

## 在线版本的安全边界

- 只处理源码内版本化的内存 Fixture；
- 只读工具自动运行，`EditFile` 必须经过一次人工批准；
- `Pytest` 是固定目标的确定性验证事件，不接收用户命令；
- 每次模型、工具、权限事件均以结构化轨迹返回；
- 不复制或公开课程来源的完整 MewCode CLI 源码。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

打开 `http://127.0.0.1:8010`，API 文档位于 `http://127.0.0.1:8010/docs`。

## 测试

独立测试摘要见 [`TEST_REPORT.md`](TEST_REPORT.md)，包含本地 pytest 和 Railway 线上 API 验证结果。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Railway

当前保留 monorepo 中的目录名 `patchpilot-agent`，以兼容既有 Railway Service 的 Root Directory。目录内已不包含 PatchPilot 实现；部署稳定后可在 Railway 控制台将服务重命名为 `mewcode-showcase`。
