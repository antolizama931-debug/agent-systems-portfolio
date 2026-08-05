"""可复现的 OnCall 检索与 Agent Run 基准。

该脚本只使用项目现有实现，不替换检索器逻辑。语料采用仓库内可回放的
Wikimedia Status 快照和固定的官方/外部参考资料；同时探测实时来源并把
``live``、``partial-live`` 或 ``fallback`` 状态写入结果，避免把离线快照
误写成实时数据。

运行：

    .venv\\Scripts\\python.exe benchmarks\\knowledge_retrieval_benchmark.py

结果写入 ``benchmarks/results``。报告中的 relevance label 是人工标注的
小规模测试集，只用于比较当前实现的相对表现，不代表生产泛化性能。
"""

from __future__ import annotations

import asyncio
import ast
import html
import hashlib
import importlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from io import BytesIO
from pathlib import Path
from statistics import mean
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine import analyze_incident  # noqa: E402
from app.knowledge import KnowledgeBaseStore, _tokenize, extract_document_text  # noqa: E402
from app.models import IncidentRequest, Severity  # noqa: E402
from app.public_sources import (  # noqa: E402
    EXTERNAL_ANALOGIES,
    UPSTREAM_OFFICIAL_REFERENCES,
    WikimediaKnowledgeClient,
)
from app.runtime import AgentRunStore  # noqa: E402
from app.statuspage import MultiStatusClient, snapshot_scenarios  # noqa: E402


RESULTS_DIR = ROOT / "benchmarks" / "results"
QUERIES_PATH = ROOT / "benchmarks" / "queries.json"
REPEATS = 5
AGENT_RUN_REPEATS = 20
TOP_K = 20


def load_queries() -> list[dict[str, Any]]:
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries.json 必须是非空数组")
    for query in queries:
        if not isinstance(query, dict) or not query.get("id") or not query.get("text"):
            raise ValueError("每条查询必须包含 id 和 text")
        if not query.get("relevant_keys"):
            raise ValueError(f"查询 {query.get('id')} 缺少人工标注 relevant_keys")
    return queries


def _minimal_pdf(text: str) -> bytes:
    """生成一个无外部依赖的最小 PDF，仅用于验证 PDF 文本提取路径。"""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 12 Tf\n72 720 Td\n({escaped}) Tj\nET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF".encode("ascii")
    )
    return bytes(output)


def format_probe() -> dict[str, Any]:
    """对上传解析器的 PDF/Markdown/TXT 路径做真实调用。"""
    samples = {
        "runbook.md": b"# Runbook\n\nCheck the service health endpoint.",
        "incident.txt": "网络延迟升高，先检查上游依赖。".encode("utf-8"),
        "evidence.pdf": _minimal_pdf("OnCall PDF evidence"),
    }
    results: dict[str, Any] = {}
    for filename, data in samples.items():
        started = time.perf_counter()
        try:
            safe_name, text, media_type = extract_document_text(filename, data)
            results[filename] = {
                "status": "passed",
                "safe_name": safe_name,
                "media_type": media_type,
                "character_count": len(text),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        except Exception as exc:  # pragma: no cover - retained as evidence if a dependency breaks
            results[filename] = {
                "status": "failed",
                "error": str(exc)[:300],
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
    return results


async def source_probe() -> dict[str, Any]:
    """探测真实来源；探测结果不直接改变固定 benchmark 语料。"""
    result: dict[str, Any] = {}
    status_client = MultiStatusClient(cache_seconds=0)
    try:
        scenarios = await asyncio.wait_for(status_client.get_scenarios(), timeout=25)
        result["statuspage"] = {
            "mode": status_client.last_mode,
            "error": status_client.last_error,
            "scenario_count": len(scenarios),
        }
    except Exception as exc:
        result["statuspage"] = {
            "mode": "probe-failed",
            "error": str(exc)[:400],
            "scenario_count": 0,
        }

    knowledge_client = WikimediaKnowledgeClient(cache_seconds=0)
    try:
        documents = await asyncio.wait_for(knowledge_client.get_documents(), timeout=35)
        result["wikitech"] = {
            "mode": knowledge_client.last_mode,
            "error": knowledge_client.last_error,
            "document_count": len(documents),
        }
    except Exception as exc:
        result["wikitech"] = {
            "mode": "probe-failed",
            "error": str(exc)[:400],
            "document_count": 0,
        }
    return result


def build_store() -> tuple[KnowledgeBaseStore, list[Any], list[Any]]:
    """构建固定、可回放的 12 文档语料：6 条状态快照 + 6 条参考资料。"""
    scenarios = snapshot_scenarios()
    records = [*UPSTREAM_OFFICIAL_REFERENCES, *EXTERNAL_ANALOGIES]
    store = KnowledgeBaseStore(max_documents=100)
    store.sync_scenarios(scenarios)
    store.sync_public_documents(records)
    return store, scenarios, records


def _document_id(key: str, scenario_keys: set[str]) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16].upper()
    return f"STATUS-{digest}" if key in scenario_keys else f"PUBLIC-{digest}"


def _chunks(store: KnowledgeBaseStore) -> list[Any]:
    with store._lock:  # benchmark 需要读取实现内部的同一批 chunk，避免复制索引逻辑
        return [chunk for items in store._chunks.values() for chunk in items]


def ranked_ids(store: KnowledgeBaseStore, query: str, method: str) -> list[str]:
    chunks = _chunks(store)
    if method == "bm25":
        # 相关性标签按文档级维护；同一文档的多个 chunk 只能计一次。
        return list(dict.fromkeys(chunk.document_id for chunk in store._bm25_ranking(_tokenize(query), chunks)))
    if method == "dense":
        return list(dict.fromkeys(chunk.document_id for chunk in store._dense_ranking(query, chunks)))
    if method == "hybrid_rrf":
        return list(dict.fromkeys(citation.document_id for citation in store.search(query, top_k=TOP_K)))
    raise ValueError(f"unknown retrieval method: {method}")


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def latency_summary(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "mean_ms": round(mean(values), 3) if values else 0.0,
        "p50_ms": round(percentile(values, 0.50), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "min_ms": round(min(values), 3) if values else 0.0,
        "max_ms": round(max(values), 3) if values else 0.0,
    }


def retrieval_metric(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    found = len(set(ranked[:k]).intersection(relevant))
    return found / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for index, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def evaluate_retrieval(
    store: KnowledgeBaseStore,
    queries: list[dict[str, Any]],
    scenario_keys: set[str],
) -> dict[str, Any]:
    methods = ("bm25", "dense", "hybrid_rrf")
    query_targets = {
        item["id"]: {
            _document_id(key, scenario_keys) for key in item["relevant_keys"]
        }
        for item in queries
    }
    available: dict[str, bool] = {method: True for method in methods}
    rankings: dict[str, dict[str, list[str]]] = {method: {} for method in methods}
    latencies: dict[str, list[float]] = {method: [] for method in methods}

    # 第一次 dense 调用包含模型初始化和全语料 embedding，单独报告 cold start。
    cold_start: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        first_dense = ranked_ids(store, queries[0]["text"], "dense")
        cold_start["dense_first_query_ms"] = round((time.perf_counter() - started) * 1000, 3)
        cold_start["dense_available"] = bool(first_dense)
    except Exception as exc:  # pragma: no cover - diagnostic evidence
        cold_start["dense_first_query_ms"] = round((time.perf_counter() - started) * 1000, 3)
        cold_start["dense_available"] = False
        cold_start["error"] = str(exc)[:300]

    for query in queries:
        query_id = query["id"]
        for method in methods:
            try:
                # 记录 warm-up 后的排名，并用同一查询重复测量操作延迟。
                first = ranked_ids(store, query["text"], method)
                rankings[method][query_id] = first
                for _ in range(REPEATS):
                    started = time.perf_counter()
                    ranked_ids(store, query["text"], method)
                    latencies[method].append((time.perf_counter() - started) * 1000)
            except Exception as exc:  # pragma: no cover - diagnostic evidence
                available[method] = False
                rankings[method][query_id] = []
                latencies[method].append(0.0)
                cold_start.setdefault("method_errors", {})[method] = str(exc)[:300]

    # dense 不可用时，hybrid 可能退化为 BM25；报告状态而不把它伪装成完整混合检索。
    dense_available = any(rankings["dense"].values())
    available["dense"] = dense_available
    available["hybrid_rrf"] = available["hybrid_rrf"] and dense_available

    metrics: dict[str, Any] = {}
    for method in methods:
        if not available[method]:
            metrics[method] = {
                "status": "unavailable" if method == "dense" else "degraded-bm25-only",
                "n_queries": len(queries),
                "recall_at_1": None,
                "recall_at_3": None,
                "recall_at_5": None,
                "mrr": None,
                "latency_ms": latency_summary(latencies[method]),
            }
            continue
        ranks = [rankings[method][query["id"]] for query in queries]
        metrics[method] = {
            "status": "measured",
            "n_queries": len(queries),
            "recall_at_1": round(mean(retrieval_metric(rank, query_targets[q["id"]], 1) for rank, q in zip(ranks, queries)), 6),
            "recall_at_3": round(mean(retrieval_metric(rank, query_targets[q["id"]], 3) for rank, q in zip(ranks, queries)), 6),
            "recall_at_5": round(mean(retrieval_metric(rank, query_targets[q["id"]], 5) for rank, q in zip(ranks, queries)), 6),
            "mrr": round(mean(reciprocal_rank(rank, query_targets[q["id"]]) for rank, q in zip(ranks, queries)), 6),
            "latency_ms": latency_summary(latencies[method]),
        }
    baseline = metrics["bm25"]
    for method in methods:
        metrics[method]["delta_vs_bm25_percentage_points"] = {
            key: (
                None
                if metrics[method][key] is None or baseline[key] is None
                else round((metrics[method][key] - baseline[key]) * 100, 3)
            )
            for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr")
        }
    per_query = []
    for query in queries:
        query_id = query["id"]
        targets = sorted(query_targets[query_id])
        method_rows: dict[str, Any] = {}
        for method in methods:
            ranked = rankings[method][query_id]
            first_relevant = next(
                (index for index, item in enumerate(ranked, start=1) if item in query_targets[query_id]),
                None,
            )
            method_rows[method] = {
                "status": metrics[method]["status"],
                "first_relevant_rank": first_relevant,
                "recall_at_5": retrieval_metric(ranked, query_targets[query_id], 5)
                if metrics[method]["status"] == "measured"
                else None,
                "ranked_document_ids": ranked[:TOP_K],
            }
        per_query.append({"id": query_id, "relevant_document_ids": targets, "methods": method_rows})
    return {
        "methods": metrics,
        "per_query": per_query,
        "cold_start": cold_start,
        "repeats_per_query": REPEATS,
    }


def run_agent_benchmark(repeats: int = AGENT_RUN_REPEATS) -> dict[str, Any]:
    request = IncidentRequest(
        description="production API latency and 503 errors increased after a deployment; retry amplification is suspected",
        service="checkout-api",
        severity=Severity.SEV2,
        environment="production",
        change_event="deployment checkout-api v2.4.1",
    )
    wall_times: list[float] = []
    tool_counts: list[int] = []
    tool_durations: list[int] = []
    with tempfile.TemporaryDirectory(prefix="oncall-agent-run-") as directory:
        run_store = AgentRunStore(max_runs=repeats + 2, data_dir=Path(directory))
        try:
            for index in range(repeats):
                started = time.perf_counter()
                analysis = analyze_incident(request)
                run = run_store.create(request=request, analysis=analysis, session_id=f"benchmark-{index}")
                wall_times.append((time.perf_counter() - started) * 1000)
                tool_counts.append(len(run.tool_calls))
                tool_durations.append(sum(tool.duration_ms for tool in run.tool_calls))
        finally:
            # Windows keeps SQLite handles locked until the connection is explicitly closed.
            run_store._connection.close()
    return {
        "status": "measured",
        "mode": "deterministic-local-engine",
        "repeats": repeats,
        "wall_clock_ms": latency_summary(wall_times),
        "tool_calls": {
            "mean": round(mean(tool_counts), 3),
            "min": min(tool_counts),
            "max": max(tool_counts),
        },
        "reported_tool_duration_ms": latency_summary([float(value) for value in tool_durations]),
        "token_usage": {
            "status": "not_measured",
            "deepseek_api_key_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
            "reason": "本 benchmark 未调用 DeepSeek API；确定性本地引擎没有模型 token usage 返回值。",
        },
    }


def api_route_stats() -> dict[str, Any]:
    """在临时数据目录导入 FastAPI 应用，统计实际注册路由。"""
    previous = os.environ.get("ONCALL_DATA_DIR")
    with tempfile.TemporaryDirectory(prefix="oncall-api-stats-") as directory:
        os.environ["ONCALL_DATA_DIR"] = directory
        try:
            module = importlib.import_module("app.main")
            routes = [
                route
                for route in module.app.routes
                if getattr(route, "path", "").startswith("/api")
            ]
            methods = [
                f"{method} {route.path}"
                for route in routes
                for method in sorted(getattr(route, "methods", set()))
            ]
            return {
                "status": "measured",
                "unique_paths": len({route.path for route in routes}),
                "method_route_pairs": len(methods),
                "routes": methods,
            }
        finally:
            # app.main owns SQLite connections created at import time.
            for name in ("run_store", "alert_store"):
                resource = getattr(locals().get("module"), name, None)
                connection = getattr(resource, "_connection", None)
                if connection is not None:
                    connection.close()
            if previous is None:
                os.environ.pop("ONCALL_DATA_DIR", None)
            else:
                os.environ["ONCALL_DATA_DIR"] = previous


def test_count() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"(\d+) tests? collected", output)
    count = int(match.group(1)) if match else len([line for line in completed.stdout.splitlines() if line.startswith("tests/")])
    return {"status": "measured" if completed.returncode == 0 else "collection-failed", "count": count}


def svg_bar_chart(metrics: dict[str, Any]) -> str:
    """用标准库生成小型 SVG，避免 benchmark 依赖绘图库。"""
    methods = ["bm25", "dense", "hybrid_rrf"]
    labels = {"bm25": "BM25", "dense": "Dense", "hybrid_rrf": "Hybrid RRF"}
    colors = {"bm25": "#4c78a8", "dense": "#f58518", "hybrid_rrf": "#54a24b"}
    width, height = 820, 440
    chart_left, chart_width = 90, 650
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="40" y="30" font-family="Arial,sans-serif" font-size="18" fill="#1f2937">Offline retrieval benchmark (hand-labeled queries)</text>',
    ]
    for chart_index, (title, key, scale, unit) in enumerate(
        [("Recall@5", "recall_at_5", 1.0, "%"), ("Warm P50 latency", "p50_ms", None, " ms")]
    ):
        top = 60 + chart_index * 185
        parts.append(f'<text x="{chart_left}" y="{top}" font-family="Arial,sans-serif" font-size="14" fill="#374151">{title}</text>')
        parts.append(f'<line x1="{chart_left}" y1="{top + 135}" x2="{chart_left + chart_width}" y2="{top + 135}" stroke="#9ca3af"/>')
        max_value = 1.0 if scale else max((metrics[m]["latency_ms"][key] for m in methods if metrics[m]["status"] == "measured"), default=1.0)
        max_value = max(max_value, 1e-9)
        for index, method in enumerate(methods):
            info = metrics[method]
            value = info[key] if key == "recall_at_5" else info["latency_ms"][key]
            if value is None or info["status"] != "measured":
                value = 0.0
            bar_height = 110 * float(value) / max_value
            x = chart_left + 55 + index * 190
            y = top + 135 - bar_height
            parts.append(f'<rect x="{x}" y="{y:.2f}" width="100" height="{bar_height:.2f}" fill="{colors[method]}" rx="4"/>')
            display = f"{value * 100:.1f}%" if unit == "%" else f"{value:.2f} ms"
            parts.append(f'<text x="{x + 50}" y="{max(y - 7, top + 15):.2f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#111827">{display}</text>')
            parts.append(f'<text x="{x + 50}" y="{top + 155}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#374151">{labels[method]}</text>')
    parts.append('<text x="40" y="425" font-family="Arial,sans-serif" font-size="11" fill="#6b7280">Results are measured on 12 fixed queries; not a production generalization claim.</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def write_outputs(payload: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "benchmark.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    retrieval = payload["retrieval"]["methods"]
    corpus = payload["corpus"]
    agent = payload["agent_run"]
    report = f"""# OnCall 量化 Benchmark 报告

## 评价问题

在固定、可回放的人工标注查询集上，BM25 词法检索、FastEmbed 多语言向量检索和 Reciprocal Rank Fusion (RRF) 混合检索的召回与延迟分别是多少？同时测量确定性 Agent Run 的端到端墙钟时间、工具调用数，以及静态 API 路由和自动化测试规模。

## 语料与标注集

| 项目 | 实测值 |
|---|---:|
| 文档数 | {corpus['document_count']} |
| 文本块数 | {corpus['chunk_count']} |
| 字符数 | {corpus['character_count']} |
| 查询数 | {payload['query_set']['count']} |
| 查询语言标签 | {', '.join(payload['query_set']['languages'])} |
| 语料模式 | {corpus['mode']} |

语料由 6 条仓库内 Wikimedia Status verified snapshot 和 6 条固定参考资料组成。`relevant_keys` 是人工审查标签；12 条查询规模较小，不能外推生产 Recall 或语言覆盖率。

## 检索结果

| 方法 | 状态 | Recall@1 | Recall@3 | Recall@5 | MRR | 平均延迟 (ms) | P50 (ms) | P95 (ms) | 延迟样本数 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 | {retrieval['bm25']['status']} | {fmt(retrieval['bm25']['recall_at_1'])} | {fmt(retrieval['bm25']['recall_at_3'])} | {fmt(retrieval['bm25']['recall_at_5'])} | {fmt(retrieval['bm25']['mrr'])} | {retrieval['bm25']['latency_ms']['mean_ms']:.3f} | {retrieval['bm25']['latency_ms']['p50_ms']:.3f} | {retrieval['bm25']['latency_ms']['p95_ms']:.3f} | {retrieval['bm25']['latency_ms']['n']} |
| Dense | {retrieval['dense']['status']} | {fmt(retrieval['dense']['recall_at_1'])} | {fmt(retrieval['dense']['recall_at_3'])} | {fmt(retrieval['dense']['recall_at_5'])} | {fmt(retrieval['dense']['mrr'])} | {retrieval['dense']['latency_ms']['mean_ms']:.3f} | {retrieval['dense']['latency_ms']['p50_ms']:.3f} | {retrieval['dense']['latency_ms']['p95_ms']:.3f} | {retrieval['dense']['latency_ms']['n']} |
| Hybrid RRF | {retrieval['hybrid_rrf']['status']} | {fmt(retrieval['hybrid_rrf']['recall_at_1'])} | {fmt(retrieval['hybrid_rrf']['recall_at_3'])} | {fmt(retrieval['hybrid_rrf']['recall_at_5'])} | {fmt(retrieval['hybrid_rrf']['mrr'])} | {retrieval['hybrid_rrf']['latency_ms']['mean_ms']:.3f} | {retrieval['hybrid_rrf']['latency_ms']['p50_ms']:.3f} | {retrieval['hybrid_rrf']['latency_ms']['p95_ms']:.3f} | {retrieval['hybrid_rrf']['latency_ms']['n']} |

Dense 首次查询冷启动耗时：`{payload['retrieval']['cold_start'].get('dense_first_query_ms', '未测量')} ms`。该值包含模型初始化和全语料 embedding，不能与 warm P50 直接比较。

## Agent Run、API 与测试规模

| 项目 | 实测值 |
|---|---:|
| Agent Run 模式 | {agent['mode']} |
| Agent Run 重复次数 | {agent['repeats']} |
| Agent Run 平均墙钟耗时 (ms) | {agent['wall_clock_ms']['mean_ms']:.3f} |
| Agent Run P50/P95 (ms) | {agent['wall_clock_ms']['p50_ms']:.3f} / {agent['wall_clock_ms']['p95_ms']:.3f} |
| 每次工具调用数 | {agent['tool_calls']['mean']:.3f} |
| API 唯一路径数 | {payload['api']['unique_paths']} |
| HTTP method-route 对数 | {payload['api']['method_route_pairs']} |
| pytest 收集用例数 | {payload['tests']['count']} |

Agent Run 是确定性本地引擎 + 临时 SQLite 的重复测量，不是 DeepSeek 生产调用耗时。DeepSeek token usage：`{agent['token_usage']['status']}`；原因见 JSON。

## 实际支持格式探针

| 文件类型 | 解析结果 | media type | 字符数 |
|---|---|---|---:|
"""
    for filename, info in payload["format_probe"].items():
        report += f"| {filename} | {info['status']} | {info.get('media_type', '-')} | {info.get('character_count', '-')} |\n"
    report += (
        f"\nRecall@5 相对 BM25 基线的绝对差值：Dense {pp(retrieval['dense']['delta_vs_bm25_percentage_points']['recall_at_5'])}，"
        f"Hybrid RRF {pp(retrieval['hybrid_rrf']['delta_vs_bm25_percentage_points']['recall_at_5'])}。"
        "负值表示当前固定集上的回落，不能表述为提升。\n"
    )
    report += """

## 可写入简历的严格表述

> 在 12 条人工标注查询、12 个固定文档和当前实现的离线回放集上，BM25、Dense 与 RRF 的 Recall@5、MRR 和 warm P50/P95 延迟分别为本报告实测值；该结果用于当前 benchmark 的方法比较，不代表生产泛化性能。

可将“处理 {docs} 份文档、{chunks} 个文本块”写入简历，但应保留语料时间点和数据模式。API 数量与 pytest 数量是代码静态/收集结果，不应表述为线上吞吐指标。

## 禁止的表述

- “系统 Recall@5 稳定提升 X%”：当前只有单一小规模标注集，无独立数据集、seed 或置信区间。
- “支持 X 种语言”：当前只测试了中文、英文和中英混合查询，不能推出完整语言覆盖率。
- “平均 token 消耗为 0”：确定性降级不等于模型消耗为 0；本次没有调用 DeepSeek API。
- “Railway 线上检索延迟”：本报告运行在本地环境，不能替代线上压测。

## 来源与限制

实时来源探测状态写在 `benchmark.json` 的 `source_probe` 中；如果 mode 是 `verified-snapshot` 或 `external-fallback`，应明确写成离线回放/降级来源。延迟样本是重复测量，不是相互独立的统计样本；没有进行显著性检验。
""".format(docs=corpus["document_count"], chunks=corpus["chunk_count"])
    (RESULTS_DIR / "analysis-report.md").write_text(report, encoding="utf-8")
    (RESULTS_DIR / "retrieval_metrics.svg").write_text(svg_bar_chart(retrieval), encoding="utf-8")
    (RESULTS_DIR / "stats-appendix.md").write_text(
        "# 统计附录\n\n完整逐查询排名、延迟和来源探测记录见 `benchmark.json`。本次未使用多 seed 或独立测试集，因此不报告显著性检验。\n",
        encoding="utf-8",
    )
    (RESULTS_DIR / "figure-catalog.md").write_text(
        "# 图目录\n\n- `retrieval_metrics.svg`：Recall@5 与 warm P50 延迟的实测柱状图。\n",
        encoding="utf-8",
    )


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.2f}%"


def pp(value: float | None) -> str:
    """Format an absolute percentage-point difference, not a relative percent."""
    return "-" if value is None else f"{value:+.2f} pp"


def main() -> None:
    queries = load_queries()
    source_probe_result = asyncio.run(source_probe())
    store, scenarios, records = build_store()
    scenario_keys = {scenario.key for scenario in scenarios}
    status = store.status()
    documents = store.list()
    namespace_counts = Counter(document.namespace for document in documents)
    media_type_counts = Counter(document.media_type for document in documents)
    corpus = {
        "mode": "verified-snapshot+fixed-reference",
        "document_count": len(documents),
        "chunk_count": status.chunk_count,
        "character_count": sum(document.character_count for document in documents),
        "namespace_counts": dict(sorted(namespace_counts.items())),
        "media_type_counts": dict(sorted(media_type_counts.items())),
        "supported_upload_formats_probed": ["PDF", "Markdown", "TXT"],
    }
    retrieval = evaluate_retrieval(store, queries, scenario_keys)
    payload = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "benchmark_version": 1,
        "corpus": corpus,
        "query_set": {
            "count": len(queries),
            "languages": sorted({str(query.get("language", "unknown")) for query in queries}),
            "labeling": "hand-labeled relevance at document level",
            "queries": queries,
        },
        "retrieval": retrieval,
        "format_probe": format_probe(),
        "agent_run": run_agent_benchmark(),
        "api": api_route_stats(),
        "tests": test_count(),
        "source_probe": source_probe_result,
        "reproducibility": {
            "python": sys.version.split()[0],
            "retrieval_repeats_per_query": REPEATS,
            "agent_run_repeats": AGENT_RUN_REPEATS,
            "top_k": TOP_K,
            "dense_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "rrf_rank_constant": 60,
        },
    }
    write_outputs(payload)
    print(json.dumps({"results_dir": str(RESULTS_DIR), "corpus": corpus, "retrieval": retrieval["methods"], "agent_run": payload["agent_run"], "api": payload["api"], "tests": payload["tests"], "source_probe": source_probe_result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
