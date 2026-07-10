# Benchmark design

The benchmark contains 538 paired clean/corrupted examples:


| Error type       | Cases   | Corruption                                                        |
| ---------------- | ------- | ----------------------------------------------------------------- |
| Content: numeric | 90      | Change one numeric body-cell value                                |
| Content: typo    | 90      | Transpose two adjacent, distinct Unicode letters in one body cell |
| Formatting       | 179     | Bold and italicize letter-containing cells in one body row        |
| Structure        | 179     | Remove one row                                                    |
| **Total**        | **538** | **One fixed corruption per table**                                |


## Corruption rules

Text typos never modify headers, tags, or HTML entities. The injector finds the longest eligible contiguous sequence of visible Unicode letters in a body cell, transposes one adjacent pair of distinct letters near its center, and changes only that occurrence.

Formatting corruptions never modify `<th>` cells or numeric-only, symbol-only, punctuation-only, or empty cells. The injector selects the body row with the most eligible `<td>` cells and applies bold italics only to cells containing visible letters.


| Selected formatting subset                                         | Cases |
| ------------------------------------------------------------------ | ----- |
| Every targeted cell starts plain                                   | 159   |
| At least one target is already bold                                | 17    |
| Every target is already bold, so the effective addition is italics | 10    |
| At least one target is already italic                              | 4     |


The groups overlap. No target is already both bold and italic, no selected `<td>` has an existing inline style attribute, every target contains a Unicode letter, and every counterpart changes rendered emphasis. Two cases include the literal alphabetic placeholder `[symbol]`; they satisfy the selection rule but are not used as qualitative examples.

`error-type-assignments.json` freezes both assignment order and top-level error type. The order keeps the 90/90 numeric-versus-typo split stable even when public filenames differ from internal identifiers.

## Rebuild and inspect

Rebuild all corruptions in a new directory without making API calls:

```bash
uv run python scripts/build_benchmark.py --output-dir /tmp/table-judge-benchmark
```

Render one clean or corrupted HTML file:

```bash
uv run --extra render python scripts/render_html.py \
  data/benchmark/corrupted_html/chinese_finepdf_00008946_page_44_block_5_unexpected_bold_italic_row.html \
  /tmp/corrupted-table.png
```

The renderer uses WeasyPrint, PDFium, and Pillow, crops whitespace, and caps output at 1,505,280 pixels. It renders `<th>` cells bold and `<td>` cells at regular weight. Font and native-library differences can change exact pixels across operating systems.

Verify the checked-in manifest and 8,608-call plan without credentials or charges:

```bash
uv run table-judge-run \
  --models gpt-5.4 gpt-5.5 claude-opus-4-7 claude-opus-4-8 \
    gemini-3.1-pro-preview gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna \
  --manifest data/benchmark/manifest.jsonl \
  --output /tmp/plan.jsonl \
  --dry-run
```

## Data limitations

- The benchmark covers synthetic numeric, text, row-removal, and emphasis errors rather than the full space of table transcription failures.
- Error types are globally balanced, but language strata are not.
- Filename-derived language is a coarse provenance proxy, and some tables contain multiple languages.
