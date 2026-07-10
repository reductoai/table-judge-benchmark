# Benchmark data

This release contains 538 table images, their faithful HTML transcriptions, and one frozen corrupted HTML counterpart per table:

```text
benchmark/
├── images/                      538 PNG images
├── html/                        538 clean HTML files
├── corrupted_html/              538 one-error counterparts
├── error-type-assignments.json  frozen assignment order and top-level types
├── manifest.jsonl               paths, error metadata, and SHA-256 checksums
└── README.md                    corruption design and reproduction notes
```

The clean images are rendered directly from the trusted HTML, so every clean image–HTML pair matches by construction. The corrupted counterpart changes exactly one controlled property. See the [benchmark design](benchmark/README.md) for the corruption rules, severity audit, checksums, and regeneration commands.

The source tables derive from the [FinePDFs dataset](https://huggingface.co/datasets/HuggingFaceFW/finepdfs), whose dataset card lists the corpus under ODC-By. Filename-derived language labels are inherited provenance hints, not audited language annotations:

| Stratum | Tables |
|---|---:|
| Korean | 213 |
| Chinese | 88 |
| Other | 78 |
| Japanese | 70 |
| German | 44 |
| English | 28 |
| Arabic | 17 |

Public filenames replace long internal pipeline prefixes with compact labels such as `chinese_finepdf_...`. All 538 public image, clean-HTML, and corrupted-HTML content hashes match the execution manifest.

## Pricing snapshot

[`pricing-2026-07-08.json`](pricing-2026-07-08.json) stores the standard API rates used by the analyzer, in USD per one million tokens. Every model entry includes the official `source_url` used to verify its rates. The filename records the capture date; preview pricing can change, so recheck those links before reusing the estimates.

For GPT-5.6, cache writes are priced at 1.25 times uncached input and cache reads at a 90% discount. Claude uses the five-minute cache-write rate. Gemini uses the standard tier for prompts up to 200,000 tokens; every benchmark prompt is below that threshold. GPT-5.4 and GPT-5.5 have no separate cache-write price in the snapshot, so their JSON values are `null`. Both models report zero cache-write tokens in these logs, making that field irrelevant to their estimates. Gemini also reports zero cache-write tokens here.

The analyzer applies the recorded rates to provider-reported uncached input, cache-read input, cache-write input, and output tokens. Estimated costs exclude failed attempts, stalled calls without usage, negotiated discounts, tax, and invoice reconciliation.

## Release note

FinePDFs lists ODC-By for the corpus, but rights in underlying source documents can vary. Confirm redistribution approval, attribution, and takedown handling before publishing the image and HTML assets. The code and response records can be released separately if the derived data is withheld.
