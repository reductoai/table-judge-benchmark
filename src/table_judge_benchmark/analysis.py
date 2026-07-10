from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .benchmark import RESULT_KEYS


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _normalized_usage(usage: dict[str, Any] | None) -> dict[str, int] | None:
    if not usage:
        return None
    input_tokens = usage.get("input_tokens", usage.get("prompt_token_count"))
    output_tokens = usage.get("output_tokens")
    details = usage.get("output_tokens_details") or {}
    reasoning_tokens = details.get("reasoning_tokens", details.get("thinking_tokens"))
    if output_tokens is None:
        visible = usage.get("candidates_token_count")
        thoughts = usage.get("thoughts_token_count", 0)
        if visible is not None:
            output_tokens = visible + thoughts
            reasoning_tokens = thoughts
    if input_tokens is None or output_tokens is None:
        return None
    input_details = usage.get("input_tokens_details") or {}
    if "cache_creation_input_tokens" in usage:
        uncached = int(input_tokens)
        cached = int(usage.get("cache_read_input_tokens") or 0)
        cache_write = int(usage.get("cache_creation_input_tokens") or 0)
        input_tokens = uncached + cached + cache_write
    else:
        cached = int(input_details.get("cached_tokens") or usage.get("cached_content_token_count") or 0)
        cache_write = int(input_details.get("cache_write_tokens") or 0)
        uncached = max(0, int(input_tokens) - cached - cache_write)
    return {
        "input": int(input_tokens),
        "uncached_input": uncached,
        "cached_input": cached,
        "cache_write_input": cache_write,
        "output": int(output_tokens),
        "reasoning": int(reasoning_tokens or 0),
    }


def _usage_metrics(
    records: list[dict[str, Any]],
    pricing: dict[str, Any] | None,
) -> dict[str, Any]:
    usage = [value for row in records if (value := _normalized_usage(row.get("usage"))) is not None]
    tokens = {
        "count": len(usage),
        **{
            key: sum(value[key] for value in usage)
            for key in (
                "input",
                "uncached_input",
                "cached_input",
                "cache_write_input",
                "output",
                "reasoning",
            )
        },
    }
    estimated_cost = None
    if pricing and usage:
        cache_write_rate = pricing["cache_write_input"]
        if cache_write_rate is None and tokens["cache_write_input"]:
            raise ValueError("cache-write price is required when cache-write tokens are nonzero")
        total = (
            tokens["uncached_input"] * pricing["input"]
            + tokens["cached_input"] * pricing["cached_input"]
            + tokens["cache_write_input"] * (cache_write_rate or 0)
            + tokens["output"] * pricing["output"]
        ) / 1_000_000
        estimated_cost = {
            "total": total,
            "per_judgment": total / len(usage),
        }
    return {
        "tokens": tokens,
        "estimated_cost_usd": estimated_cost,
    }


def _rejected(record: dict[str, Any]) -> bool:
    return any(record["judgments"].get(key) is False for key in RESULT_KEYS)


def _latest_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = {}
    for record in records:
        key = (record["model"], record["stem"], record["condition"])
        latest[key] = record
    return list(latest.values())


def _paired_metrics(clean: list[dict[str, Any]], corrupted: list[dict[str, Any]]) -> dict[str, Any]:
    clean_by_stem = {row["stem"]: row for row in clean}
    corrupted_by_stem = {row["stem"]: row for row in corrupted}
    stems = sorted(clean_by_stem.keys() & corrupted_by_stem.keys())
    false_positives = sum(_rejected(clean_by_stem[stem]) for stem in stems)
    true_positives = sum(_rejected(corrupted_by_stem[stem]) for stem in stems)
    return {
        "samples": len(stems),
        "false_positives": false_positives,
        "fpr": _rate(false_positives, len(stems)),
        "true_positives": true_positives,
        "tpr": _rate(true_positives, len(stems)),
    }


def _corruption_breakdown(corrupted: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    breakdown = {}
    for value in sorted({row.get(field) for row in corrupted if row.get(field)}):
        subset = [row for row in corrupted if row.get(field) == value]
        true_positives = sum(_rejected(row) for row in subset)
        injected = sum(row["judgments"].get(row.get("expected_judgment")) is False for row in subset)
        breakdown[value] = {
            "true_positives": true_positives, "injected_rubric_hits": injected, "total": len(subset),
            "tpr": _rate(true_positives, len(subset)),
            "injected_rubric_detection_rate": _rate(injected, len(subset)),
        }
    return breakdown


def _model_metrics(
    records: list[dict[str, Any]],
    expected_attempts: int,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    successful = [row for row in records if row.get("status") == "success"]
    clean = [row for row in successful if row["condition"] == "clean"]
    corrupted = [row for row in successful if row["condition"] == "corrupted"]
    false_positives = sum(_rejected(row) for row in clean)
    true_positives = sum(_rejected(row) for row in corrupted)
    injected_hits = sum(row["judgments"].get(row.get("expected_judgment")) is False for row in corrupted)
    false_negatives = len(corrupted) - true_positives
    precision = _rate(true_positives, true_positives + false_positives)
    f1 = _rate(2 * true_positives, 2 * true_positives + false_positives + false_negatives)
    paired = _paired_metrics(clean, corrupted)
    fpr_by_criterion = {}
    for key in RESULT_KEYS:
        count = sum(row["judgments"].get(key) is False for row in clean)
        fpr_by_criterion[key] = {
            "count": count,
            "total": len(clean),
            "rate": _rate(count, len(clean)),
        }
    tpr_by_error_type = _corruption_breakdown(corrupted, "error_type")
    tpr_by_error_subtype = _corruption_breakdown(corrupted, "error_subtype")
    macro_rates = [row["tpr"] for row in tpr_by_error_type.values() if row["tpr"] is not None]
    return {
        "attempted": expected_attempts,
        "successful": len(successful),
        "failed": expected_attempts - len(successful),
        "coverage": _rate(len(successful), expected_attempts),
        "attempted_pairs": expected_attempts // 2,
        "paired_complete": paired["samples"],
        "clean_successful": len(clean),
        "corrupted_successful": len(corrupted),
        "false_positives": false_positives,
        "fpr": _rate(false_positives, len(clean)),
        "true_positives": true_positives,
        "tpr": _rate(true_positives, len(corrupted)),
        "injected_rubric_hits": injected_hits,
        "injected_rubric_detection_rate": _rate(injected_hits, len(corrupted)),
        "precision": precision,
        "f1": f1,
        "macro_tpr": sum(macro_rates) / len(macro_rates) if macro_rates else None,
        "fpr_by_criterion": fpr_by_criterion,
        "tpr_by_error_type": tpr_by_error_type,
        "tpr_by_error_subtype": tpr_by_error_subtype,
        "paired": paired,
    } | _usage_metrics(successful, pricing)


def _language(stem: str) -> str:
    for language in ("arabic", "chinese", "english", "german", "japanese", "korean"):
        if f"__{language}__" in stem or stem.startswith(f"{language}_"):
            return language
    return "other"


def summarize_results(
    records: Iterable[dict[str, Any]],
    pricing: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = _latest_records(records)
    by_model = defaultdict(list)
    for record in current:
        by_model[record["model"]].append(record)

    unique_corrupted = {}
    for record in current:
        if record["condition"] == "corrupted":
            unique_corrupted.setdefault(record["stem"], record)
    languages = Counter(_language(stem) for stem in unique_corrupted)
    error_types = Counter(row.get("error_type", "unknown") for row in unique_corrupted.values())
    error_subtypes = Counter(row.get("error_subtype", "unknown") for row in unique_corrupted.values())
    return {
        "definitions": {
            "fpr": "Any rubric dimension is False on a clean image/HTML pair.",
            "tpr": "Any rubric dimension is False on a corrupted pair.",
            "injected_rubric_detection_rate": "The rubric targeted by the injected corruption is False.",
            "coverage": "Successful responses divided by attempted responses.",
        },
        "dataset": {
            "samples": len(unique_corrupted),
            "languages": dict(sorted(languages.items())),
            "error_types": dict(sorted(error_types.items())),
            "error_subtypes": dict(sorted(error_subtypes.items())),
        },
        "pricing_per_million_tokens": pricing or {},
        "models": {
            model: _model_metrics(rows, 2 * len(unique_corrupted), (pricing or {}).get(model))
            for model, rows in sorted(by_model.items())
        },
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    if isinstance(data, list):
        return data
    raise ValueError(f"unsupported results shape in {path}")


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def render_markdown(summary: dict[str, Any]) -> str:
    rows = sorted(
        summary["models"].items(),
        key=lambda item: item[1]["f1"] if item[1]["f1"] is not None else -1,
        reverse=True,
    )
    lines = [
        "# Benchmark results",
        "",
        "TPR means the judge marked **any** rubric dimension false on a corrupted pair. ",
        "Injected-rubric detection requires the rubric targeted by the corruption to be false.",
        "",
        "| Model | Coverage | FPR ↓ | TPR ↑ | Injected-rubric detection ↑ | F1 ↑ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, metrics in rows:
        lines.append(
            f"| `{model}` | {_percent(metrics['coverage'])} | {_percent(metrics['fpr'])} | "
            f"{_percent(metrics['tpr'])} | {_percent(metrics['injected_rubric_detection_rate'])} | "
            f"{_percent(metrics['f1'])} |"
        )
    lines.extend([
        "",
        "## Dataset composition",
        "",
        f"- Samples: {summary['dataset']['samples']}",
        f"- Error types: {summary['dataset']['error_types']}",
        f"- Filename-derived language strata: {summary['dataset']['languages']}",
        "",
        "Full-precision metrics are stored in `summary.json`.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze table-judge benchmark results")
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pricing", type=Path)
    args = parser.parse_args()

    records = []
    for path in args.input:
        records.extend(load_records(path))
    pricing = json.loads(args.pricing.read_text(encoding="utf-8")) if args.pricing else None
    summary = summarize_results(records, pricing)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.output_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
