from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import random
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


RESULT_KEYS = ("content_accuracy", "structural_preservation", "formatting_fidelity")
TAG_RE = re.compile(r"<([a-z_]+)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
PROMPT_TEMPLATE = Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8").rstrip("\n")


@dataclass(frozen=True)
class ErrorInjection:
    error_type: str
    error_subtype: str
    original_value: str
    corrupted_value: str
    location: str
    expected_judgment: str


@dataclass(frozen=True)
class BenchmarkCase:
    stem: str
    image_path: Path
    html_path: Path
    corrupted_html: str
    error: ErrorInjection


@dataclass(frozen=True)
class ModelOutput:
    text: str
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    resolved_model: str | None = None


def inject_wrong_cell_value(html: str) -> tuple[str, ErrorInjection | None]:
    match = re.search(r"<(td|th)>(\d+[.,]?\d*)</\1>", html)
    if not match:
        return html, None
    original = match.group(2)
    try:
        if "." in original or "," in original:
            corrupted = str(float(original.replace(",", ".")) + 100).replace(".", ",")
        else:
            corrupted = str(int(original) + 100)
    except ValueError:
        corrupted = "Lorem Ipsum"
    replacement = f"<{match.group(1)}>{corrupted}</{match.group(1)}>"
    changed = html[: match.start()] + replacement + html[match.end() :]
    return changed, ErrorInjection(
        "content",
        "wrong_cell_value",
        original,
        corrupted,
        match.group(0)[:80],
        "content_accuracy",
    )


def inject_missing_bold(html: str) -> tuple[str, ErrorInjection | None]:
    match = re.search(r"<td>\s*<(strong|b)>(.*?)</\1>\s*</td>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return html, None
    original = match.group(0)
    corrupted = f"<td>{match.group(2)}</td>"
    changed = html[: match.start()] + corrupted + html[match.end() :]
    return changed, ErrorInjection(
        "formatting",
        "missing_bold",
        original,
        corrupted,
        original[:80],
        "formatting_fidelity",
    )


def inject_wrong_row_count(html: str) -> tuple[str, ErrorInjection | None]:
    rows = list(re.finditer(r"<tr>.*?</tr>", html, re.DOTALL | re.IGNORECASE))
    if len(rows) < 2:
        return html, None
    target_index = 1
    match = rows[target_index]
    changed = html[: match.start()] + html[match.end() :]
    return changed, ErrorInjection(
        "structure",
        "wrong_row_count",
        match.group(0)[:80],
        "[removed]",
        f"row {target_index}",
        "structural_preservation",
    )


def choose_corruption(html: str, rng: random.Random) -> tuple[str, ErrorInjection] | None:
    candidates = []
    for injector in (inject_wrong_cell_value, inject_missing_bold, inject_wrong_row_count):
        corrupted, error = injector(html)
        if error:
            candidates.append((corrupted, error))
    return rng.choice(candidates) if candidates else None


def build_cases(html_dir: Path, image_dir: Path, seed: int = 0) -> list[BenchmarkCase]:
    rng = random.Random(seed)
    cases = []
    for image_path in sorted(image_dir.glob("*.png")):
        html_path = html_dir / f"{image_path.stem}.html"
        if not html_path.is_file():
            continue
        html = html_path.read_text(encoding="utf-8")
        corruption = choose_corruption(html, rng)
        if corruption:
            corrupted_html, error = corruption
            cases.append(BenchmarkCase(image_path.stem, image_path, html_path, corrupted_html, error))
    return cases


def _stored_path(path: Path, root: Path) -> str:
    return os.path.relpath(path.resolve(), root.resolve())


def write_manifest(cases: list[BenchmarkCase], manifest_path: Path) -> None:
    root = manifest_path.parent
    corrupted_dir = root / "corrupted_html"
    corrupted_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for case in cases:
        corrupted_path = corrupted_dir / f"{case.stem}_{case.error.error_subtype}.html"
        corrupted_path.write_text(case.corrupted_html, encoding="utf-8")
        lines.append(json.dumps({
            "stem": case.stem,
            "image_path": _stored_path(case.image_path, root),
            "html_path": _stored_path(case.html_path, root),
            "corrupted_html_path": _stored_path(corrupted_path, root),
            "sha256": {
                "image": _sha256(case.image_path),
                "html": _sha256(case.html_path),
                "corrupted_html": _sha256(corrupted_path),
            },
            "error": asdict(case.error),
        }, ensure_ascii=False, sort_keys=True))
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_manifest(manifest_path: Path) -> list[BenchmarkCase]:
    root = manifest_path.parent

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else root / path

    cases = []
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        image_path = resolve(row["image_path"])
        html_path = resolve(row["html_path"])
        corrupted_path = resolve(row["corrupted_html_path"])
        for path in (image_path, html_path, corrupted_path):
            if not path.is_file():
                raise ValueError(f"manifest line {line_number}: missing {path}")
        for key, path in (
            ("image", image_path),
            ("html", html_path),
            ("corrupted_html", corrupted_path),
        ):
            if _sha256(path) != row["sha256"][key]:
                raise ValueError(f"manifest line {line_number}: checksum mismatch for {path}")
        cases.append(BenchmarkCase(
            row["stem"],
            image_path,
            html_path,
            corrupted_path.read_text(encoding="utf-8"),
            ErrorInjection(**row["error"]),
        ))
    return cases


def parse_judgments(response: str) -> dict[str, bool]:
    values: dict[str, list[bool]] = {key: [] for key in RESULT_KEYS}
    for tag, body in TAG_RE.findall(response or ""):
        key = tag.lower()
        if key not in values:
            continue
        normalized = body.strip().lower()
        if normalized not in {"true", "false"}:
            raise ValueError(f"invalid boolean in {key}")
        values[key].append(normalized == "true")
    missing = [key for key, items in values.items() if not items]
    if missing:
        raise ValueError(f"missing judgment tags: {missing}")
    for key, items in values.items():
        if len(set(items)) > 1:
            raise ValueError(f"conflicting duplicate tag: {key}")
    return {key: items[-1] for key, items in values.items()}


def completed_keys(records: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        (row["model"], row["stem"], row["condition"])
        for row in records
        if row.get("status") == "success"
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on {path}:{line_number}") from error
    return records


def call_with_retries(
    call: Callable[[], Any],
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    if attempts < 1:
        raise ValueError("attempts must be at least one")
    for attempt in range(attempts):
        try:
            return call()
        except Exception:
            if attempt + 1 == attempts:
                raise
            sleep(2**attempt)
    raise AssertionError("unreachable")


_clients = threading.local()


def _client(name: str, factory: Callable[[], Any]) -> Any:
    client = getattr(_clients, name, None)
    if client is None:
        client = factory()
        setattr(_clients, name, client)
    return client


def _model_dump(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value) if isinstance(value, dict) else {"value": str(value)}


def call_model(
    image_bytes: bytes,
    prompt: str,
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> ModelOutput:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    if model.startswith("claude-"):
        from anthropic import Anthropic

        client = _client("anthropic", lambda: Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]))
        with client.messages.stream(
            model=model,
            max_tokens=max_output_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": "max"},
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": encoded,
                }},
            ]}],
        ) as stream:
            text = "".join(stream.text_stream)
            response = stream.get_final_message()
        return ModelOutput(text, getattr(response, "id", None), _model_dump(response.usage), getattr(response, "model", None))

    if model.startswith("gemini-"):
        from google import genai
        from google.genai import types

        client = _client("gemini", lambda: genai.Client(api_key=os.environ["GEMINI_API_KEY"]))
        response = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/png"), prompt],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="high"),
                media_resolution="MEDIA_RESOLUTION_HIGH",
                max_output_tokens=max_output_tokens,
            ),
        )
        text = "".join(part.text for part in response.candidates[0].content.parts if part.text)
        resolved_model = getattr(response, "model_version", None) or getattr(response, "model", None)
        return ModelOutput(text, getattr(response, "response_id", None), _model_dump(response.usage_metadata), resolved_model)

    if model.startswith(("gpt-", "o")):
        from openai import OpenAI

        client = _client("openai", lambda: OpenAI(api_key=os.environ["OPENAI_API_KEY"]))
        response = client.responses.create(
            model=model,
            reasoning={"effort": reasoning_effort},
            max_output_tokens=max_output_tokens,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}", "detail": "high"},
            ]}],
        )
        return ModelOutput(response.output_text, getattr(response, "id", None), _model_dump(response.usage), getattr(response, "model", None))
    raise ValueError(f"unsupported model provider for {model!r}")


def _execute_task(
    case: BenchmarkCase,
    model: str,
    condition: str,
    reasoning_effort: str,
    max_output_tokens: int,
    retries: int,
    run_id: str,
) -> dict[str, Any]:
    html = case.html_path.read_text(encoding="utf-8") if condition == "clean" else case.corrupted_html
    started = time.monotonic()
    base = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "stem": case.stem,
        "condition": condition,
    }
    if condition == "corrupted":
        base.update({
            "error_type": case.error.error_type,
            "error_subtype": case.error.error_subtype,
            "expected_judgment": case.error.expected_judgment,
            "error_info": asdict(case.error),
        })
    last_output = None

    def call_and_parse() -> tuple[ModelOutput, dict[str, bool]]:
        nonlocal last_output
        last_output = call_model(
            case.image_path.read_bytes(),
            PROMPT_TEMPLATE.format(html=html),
            model,
            reasoning_effort,
            max_output_tokens,
        )
        return last_output, parse_judgments(last_output.text)

    try:
        output, judgments = call_with_retries(call_and_parse, attempts=retries)
        return base | {
            "status": "success",
            "judgments": judgments,
            "raw_response": output.text,
            "request_id": output.request_id,
            "resolved_model": output.resolved_model,
            "usage": output.usage,
            "latency_seconds": time.monotonic() - started,
        }
    except Exception as error:
        failed = base | {
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "latency_seconds": time.monotonic() - started,
        }
        if last_output is not None:
            failed.update({"raw_response": last_output.text, "request_id": last_output.request_id,
                           "resolved_model": last_output.resolved_model, "usage": last_output.usage})
        return failed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paired table-judge benchmark")
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--html-dir", type=Path, default=Path("data/benchmark/html"))
    parser.add_argument("--image-dir", type=Path, default=Path("data/benchmark/images"))
    parser.add_argument("--manifest", type=Path, default=Path("data/benchmark/manifest.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--reasoning-effort", default="xhigh")
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--balanced", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.manifest.exists():
        cases = load_manifest(args.manifest)
    else:
        if args.balanced:
            from .balanced import build_balanced_cases

            cases = build_balanced_cases(args.html_dir, args.image_dir, args.seed)
        else:
            cases = build_cases(args.html_dir, args.image_dir, args.seed)
        write_manifest(cases, args.manifest)
    if args.limit is not None:
        cases = cases[: args.limit]

    existing = load_jsonl(args.output)
    done = completed_keys(existing)
    tasks = [
        (case, model, condition)
        for case in cases
        for model in args.models
        for condition in ("clean", "corrupted")
        if (model, case.stem, condition) not in done
    ]
    plan = {
        "cases": len(cases),
        "models": args.models,
        "planned_calls": len(tasks),
        "already_successful": len(done),
        "error_types": {
            error_type: sum(case.error.error_type == error_type for case in cases)
            for error_type in ("content", "formatting", "structure")
        },
        "manifest_sha256": _sha256(args.manifest),
        "prompt_sha256": hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest(),
    }
    print(json.dumps(plan, indent=2))
    if args.dry_run:
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    metadata = plan | {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "concurrency": args.concurrency,
        "retries": args.retries,
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "seed": args.seed,
    }
    (args.output.parent / f"run-{run_id}.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    with args.output.open("a", encoding="utf-8", buffering=1) as handle:
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {
                executor.submit(
                    _execute_task,
                    case,
                    model,
                    condition,
                    args.reasoning_effort,
                    args.max_output_tokens,
                    args.retries,
                    run_id,
                ): (model, case.stem, condition)
                for case, model, condition in tasks
            }
            for future in as_completed(futures):
                record = future.result()
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(f"[{record['status']}] {record['model']} {record['stem']} {record['condition']}")


if __name__ == "__main__":
    main()
