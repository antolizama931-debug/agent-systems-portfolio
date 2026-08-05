# OnCall 量化 Benchmark 报告

## 评价问题

在固定、可回放的人工标注查询集上，BM25 词法检索、FastEmbed 多语言向量检索和 Reciprocal Rank Fusion (RRF) 混合检索的召回与延迟分别是多少？同时测量确定性 Agent Run 的端到端墙钟时间、工具调用数，以及静态 API 路由和自动化测试规模。

## 语料与标注集

| 项目 | 实测值 |
|---|---:|
| 文档数 | 12 |
| 文本块数 | 12 |
| 字符数 | 4917 |
| 查询数 | 12 |
| 查询语言标签 | en, mixed, zh |
| 语料模式 | verified-snapshot+fixed-reference |

语料由 6 条仓库内 Wikimedia Status verified snapshot 和 6 条固定参考资料组成。`relevant_keys` 是人工审查标签；12 条查询规模较小，不能外推生产 Recall 或语言覆盖率。

## 检索结果

| 方法 | 状态 | Recall@1 | Recall@3 | Recall@5 | MRR | 平均延迟 (ms) | P50 (ms) | P95 (ms) | 延迟样本数 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 | measured | 79.17% | 95.83% | 100.00% | 90.28% | 0.180 | 0.164 | 0.288 | 60 |
| Dense | measured | 58.33% | 79.17% | 95.83% | 71.81% | 4.614 | 4.569 | 5.232 | 60 |
| Hybrid RRF | measured | 79.17% | 87.50% | 95.83% | 89.17% | 4.759 | 4.702 | 5.394 | 60 |

Dense 首次查询冷启动耗时：`1488.551 ms`。该值包含模型初始化和全语料 embedding，不能与 warm P50 直接比较。

## Agent Run、API 与测试规模

| 项目 | 实测值 |
|---|---:|
| Agent Run 模式 | deterministic-local-engine |
| Agent Run 重复次数 | 20 |
| Agent Run 平均墙钟耗时 (ms) | 2.882 |
| Agent Run P50/P95 (ms) | 2.615 / 3.312 |
| 每次工具调用数 | 5.000 |
| API 唯一路径数 | 17 |
| HTTP method-route 对数 | 20 |
| pytest 收集用例数 | 31 |

Agent Run 是确定性本地引擎 + 临时 SQLite 的重复测量，不是 DeepSeek 生产调用耗时。DeepSeek token usage：`not_measured`；原因见 JSON。

## 实际支持格式探针

| 文件类型 | 解析结果 | media type | 字符数 |
|---|---|---|---:|
| runbook.md | passed | text/markdown | 45 |
| incident.txt | passed | text/plain | 15 |
| evidence.pdf | passed | application/pdf | 19 |

Recall@5 相对 BM25 基线的绝对差值：Dense -4.17 pp，Hybrid RRF -4.17 pp。负值表示当前固定集上的回落，不能表述为提升。


## 可写入简历的严格表述

> 在 12 条人工标注查询、12 个固定文档和当前实现的离线回放集上，BM25、Dense 与 RRF 的 Recall@5、MRR 和 warm P50/P95 延迟分别为本报告实测值；该结果用于当前 benchmark 的方法比较，不代表生产泛化性能。

可将“处理 12 份文档、12 个文本块”写入简历，但应保留语料时间点和数据模式。API 数量与 pytest 数量是代码静态/收集结果，不应表述为线上吞吐指标。

## 禁止的表述

- “系统 Recall@5 稳定提升 X%”：当前只有单一小规模标注集，无独立数据集、seed 或置信区间。
- “支持 X 种语言”：当前只测试了中文、英文和中英混合查询，不能推出完整语言覆盖率。
- “平均 token 消耗为 0”：确定性降级不等于模型消耗为 0；本次没有调用 DeepSeek API。
- “Railway 线上检索延迟”：本报告运行在本地环境，不能替代线上压测。

## 来源与限制

实时来源探测状态写在 `benchmark.json` 的 `source_probe` 中；如果 mode 是 `verified-snapshot` 或 `external-fallback`，应明确写成离线回放/降级来源。延迟样本是重复测量，不是相互独立的统计样本；没有进行显著性检验。
