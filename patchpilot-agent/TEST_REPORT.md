# MewCode 独立测试报告

运行日期：2026-08-05（Asia/Shanghai）

## 本地自动化测试

命令：

```powershell
$env:PYTHONPATH="..\tmp\mewcode-showcase-deps"
python -m pytest -q
```

- 结果：`5 passed`
- Python：3.12.13；FastAPI 0.141.1；pytest 9.1.1；httpx 0.28.1
- 警告：FastAPI/httpx TestClient 弃用提示和缓存目录权限提示；无失败
- 测试场景：健康与场景枚举、只读 Agent Loop、写入审批、拒绝分支、未知场景拒绝

## Railway 线上 API 验证

地址：`https://mewcode-production.up.railway.app`

| 检查项 | 实际结果 |
|---|---|
| `/api/health` | `status=ok` |
| 版本 | `1.0.0` |
| 执行模式 | `versioned-fixture` |
| `/api/scenarios` | 2 个场景：read-only、write |
| 只读任务 | `completed`，3 次工具调用 |
| 写入任务审批前 | `awaiting-approval` |
| 写入任务批准后 | `completed` |
| 写入任务拒绝后 | `rejected`，未出现 `EditFile` |

该服务只执行版本化 Fixture；不能把 `Pytest` 事件表述为执行了用户真实代码，也不开放任意 Shell 或文件路径。
