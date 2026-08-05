# OnCall 独立测试报告

运行日期：2026-08-05（Asia/Shanghai）

## 本地自动化测试

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp benchmarks\pytest-temp-final
```

- 结果：`31 passed`
- Python：3.12.13
- 警告：6 条 FastEmbed 相关警告；无失败
- 说明：显式指定工作区可写的临时目录，避免系统临时目录权限干扰测试结果
- 范围：API、连接器、确定性 Agent Engine、知识库检索、公开数据映射、状态页降级策略

## Railway 线上 API 验证

地址：`https://oncall-agent-production-4c9c.up.railway.app`

| 检查项 | 实际结果 |
|---|---|
| `/api/health` | `status=ok` |
| DeepSeek 配置状态 | `deepseek_configured=true` |
| `/api/scenarios` | 12 个场景 |
| `/api/dashboard` | 12 个事故，`data_mode=live` |

## 检索基准边界

检索 Recall/MRR 结果见同目录的 `analysis-report.md`。该 benchmark 使用固定 Wikimedia 回放快照和固定参考资料，属于离线回归集；它不是线上流量压测，也不测量 DeepSeek token 消耗。
