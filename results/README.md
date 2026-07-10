# Raw benchmark results

The benchmark contains one JSONL file per requested model. Together, the eight files contain 8,653 physical records. Analysis selects the latest record for each `(model, stem, condition)` key, yielding 8,606 successful judgments and two terminal Claude Opus 4.8 failures across 8,608 expected keys. Extra rows preserve failed attempts followed by retries.

GPT-5.6 Sol, Terra, and Luna were refreshed on July 9, 2026. The five comparison-model files retain their selected complete results from the immediately preceding batch. Inputs, prompt, corruptions, provider settings, and scoring are frozen across batches.

```text
benchmark/
├── claude-opus-4-7.jsonl
├── claude-opus-4-8.jsonl
├── gemini-3.1-pro-preview.jsonl
├── gpt-5.4.jsonl
├── gpt-5.5.jsonl
├── gpt-5.6-luna.jsonl
├── gpt-5.6-sol.jsonl
├── gpt-5.6-terra.jsonl
└── analysis/
    ├── README.md
    ├── figure-data.json
    ├── summary.json
    ├── summary.md
    └── nine publication PNGs
```

Every successful row retains parsed judgments, raw model response, provider-reported usage, request ID when returned, and provider-resolved model ID. Corrupted rows also retain the injected-error type, subtype, intended rubric, and exact mutation metadata. Client timing is retained as provenance but excluded from the article because runtime conditions were not controlled.

## Evaluation protocol

For every table and model, the runner creates two independent requests:

1. the image plus faithful HTML;
2. the same image plus its fixed corrupted HTML.

The prompt asks for content accuracy, structural preservation, and formatting fidelity as separate booleans. OpenAI image requests use high detail; Gemini uses high media resolution; Claude uses adaptive thinking at maximum effort. The exact prompt is stored at `[src/table_judge_benchmark/prompt.txt](../src/table_judge_benchmark/prompt.txt)`, with SHA-256 `ca08d720488a4271403f5aced04aa5c2681895cde47c1eeea6f803b802d9ed11`.

The parser rejects missing, invalid, or conflicting boolean tags. Results are append-only: a retry never overwrites its failed attempt, and a previously successful key is skipped.

### Execution settings


| Model queue                 | Initial concurrency | Initial output ceiling | Retry ceiling when needed     |
| --------------------------- | ------------------- | ---------------------- | ----------------------------- |
| GPT-5.4                     | 24                  | 32,768                 | 65,536                        |
| GPT-5.5                     | 96 shared           | 16,384                 | 32,768                        |
| GPT-5.6 Sol / Terra refresh | 96 shared           | 32,768                 | same                          |
| Claude Opus 4.7 / 4.8       | 32 shared           | 100,000                | 128,000                       |
| Gemini 3.1 Pro Preview      | 32                  | 16,384                 | 32,768                        |
| GPT-5.6 Luna refresh        | 8                   | 32,768                 | 65,536 for one targeted retry |


All OpenAI calls use `xhigh` reasoning effort. Higher ceilings are used only for keys that fail to emit a parseable answer at the initial ceiling. A ceiling is not a token allocation: successful requests stop naturally, and cost uses actual provider-reported usage.

## Model identity

The runner passes each requested model string directly to its provider SDK and contains no client-side alias or fallback mapping. Every successful public row contains nonempty raw response text and a nonempty provider-resolved model ID:


| Requested model          | Provider-resolved model  |
| ------------------------ | ------------------------ |
| `gpt-5.4`                | `gpt-5.4-2026-03-05`     |
| `gpt-5.5`                | `gpt-5.5-2026-04-23`     |
| `gpt-5.6-sol`            | `gpt-5.6-sol`            |
| `gpt-5.6-terra`          | `gpt-5.6-terra`          |
| `gpt-5.6-luna`           | `gpt-5.6-luna`           |
| `claude-opus-4-7`        | `claude-opus-4-7`        |
| `claude-opus-4-8`        | `claude-opus-4-8`        |
| `gemini-3.1-pro-preview` | `gemini-3.1-pro-preview` |


## Coverage and retries


| Model             | Failures | Clean successes | Corrupted successes | Complete pairs |
| ----------------- | -------- | --------------- | ------------------- | -------------- |
| Claude Opus 4.8   | 2        | 537             | 537                 | 537            |
| Every other model | 0        | 538             | 538                 | 538            |


Opus 4.8 fails on both conditions of `korean_finepdf_00024850_page_30_block_6`. The initial 100,000-token attempt and 128,000-token retry emit no visible judgment tags. The failures are retained rather than rerun at a different reasoning effort.

The Luna file retains one failed parse attempt followed by a successful targeted retry for corrupted `korean_finepdf_00041236_page_0_block_2`. The latest-key view therefore has full Luna coverage while preserving the failed attempt for audit.

## Reproduce the analysis

Install locked dependencies:

```bash
uv sync --frozen --extra providers --extra render
```

Regenerate the canonical JSON and Markdown summary from the checked-in raw responses:

```bash
uv run table-judge-analyze \
  --input results/benchmark/claude-opus-4-7.jsonl \
    results/benchmark/claude-opus-4-8.jsonl \
    results/benchmark/gemini-3.1-pro-preview.jsonl \
    results/benchmark/gpt-5.4.jsonl \
    results/benchmark/gpt-5.5.jsonl \
    results/benchmark/gpt-5.6-luna.jsonl \
    results/benchmark/gpt-5.6-sol.jsonl \
    results/benchmark/gpt-5.6-terra.jsonl \
  --pricing data/pricing-2026-07-08.json \
  --output-dir /tmp/table-judge-analysis
```

The [pricing JSON](../data/pricing-2026-07-08.json) includes the official verification URL for every rate. The [analysis README](benchmark/analysis/README.md) defines the metrics and documents the complete figure and table package.

## Execution limitations

- One request per condition does not measure run-to-run variance.
- GPT-5.6 and comparison models were executed in adjacent batches; provider behavior can change even with identical inputs and settings.
- Preview behavior, availability, and pricing can change.
- Unit-cost estimates exclude failed attempts and are not the experiment invoice.
- Client latency is excluded because the runtime environment was not controlled.

GPT-5.4 Mini would provide an OpenAI cost floor; a current Claude Sonnet or Gemini Flash model would improve the cross-provider cost–quality comparison. New runs should use the frozen manifest and prompt and be preregistered before outcomes are inspected.