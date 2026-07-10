# Analysis and figure package

## Metrics

A response is positive when at least one of its three rubric decisions is `False`.

- **FPR** = positive successful clean responses / successful clean responses.
- **TPR** = positive successful corrupted responses / successful corrupted responses.
- **Injected-rubric detection** = corrupted responses whose preassigned rubric is `False` / successful corrupted responses.
- **Precision** = true positives / (true positives + clean false positives).
- **F1** is the harmonic mean of precision and TPR.
- **Coverage** = successful responses / 1,076 expected responses.

TPR is operational: did the judge stop the corrupted pair? Injected-rubric detection is diagnostic: did it identify the rubric targeted by the synthetic corruption? The measures differ because rubric dimensions can overlap. Removing a row, for example, can reasonably affect both content and structure.

## Headline results


| Model                  | Success     | FPR ↓    | TPR ↑     | Injected-rubric detection ↑ | F1 ↑      |
| ---------------------- | ----------- | -------- | --------- | --------------------------- | --------- |
| Claude Opus 4.8        | 1,074/1,076 | **6.5%** | 96.3%     | 92.7%                       | **94.9%** |
| Claude Opus 4.7        | 1,076/1,076 | 12.1%    | 97.6%     | 96.3%                       | 93.1%     |
| GPT-5.5                | 1,076/1,076 | 15.1%    | 98.5%     | 98.1%                       | 92.3%     |
| GPT-5.6 Sol            | 1,076/1,076 | 15.6%    | 97.4%     | 97.0%                       | 91.4%     |
| Gemini 3.1 Pro Preview | 1,076/1,076 | 19.3%    | **99.4%** | 94.4%                       | 90.9%     |
| GPT-5.6 Terra          | 1,076/1,076 | 16.2%    | 96.7%     | 95.9%                       | 90.8%     |
| GPT-5.4                | 1,076/1,076 | 25.5%    | 99.3%     | **99.3%**                   | 88.3%     |
| GPT-5.6 Luna           | 1,076/1,076 | 11.9%    | 84.6%     | 82.3%                       | 86.1%     |


The point-estimate FPR–TPR frontier contains Opus 4.8, Opus 4.7, GPT-5.5, and Gemini. This is not a general pairwise ranking. Sol is narrowly dominated on these two axes by GPT-5.5 but has an estimated 57% lower cost.

## Results by injected error type

Each cell reports `TPR / injected-rubric detection`:


| Model                  | Content       | Formatting     | Structure     |
| ---------------------- | ------------- | -------------- | ------------- |
| Claude Opus 4.8        | 97.2% / 97.2% | 94.4% / 94.4%  | 97.2% / 86.6% |
| Claude Opus 4.7        | 96.7% / 95.6% | 98.3% / 96.1%  | 97.8% / 97.2% |
| GPT-5.5                | 99.4% / 99.4% | 96.6% / 96.1%  | 99.4% / 98.9% |
| GPT-5.6 Sol            | 96.1% / 95.6% | 97.2% / 96.6%  | 98.9% / 98.9% |
| Gemini 3.1 Pro Preview | 99.4% / 99.4% | 100.0% / 99.4% | 98.9% / 84.4% |
| GPT-5.6 Terra          | 96.1% / 95.6% | 95.0% / 93.9%  | 98.9% / 98.3% |
| GPT-5.4                | 99.4% / 99.4% | 99.4% / 99.4%  | 98.9% / 98.9% |
| GPT-5.6 Luna           | 93.3% / 93.3% | 62.6% / 55.9%  | 97.8% / 97.8% |


Gemini's 14.5-point structure gap is the largest difference between the measures outside Luna's formatting weakness. Gemini usually stops removed-row cases but often marks content rather than `structural_preservation=False`.

### Content subtypes


| Model                  | Numeric substitution | Adjacent-letter typo |
| ---------------------- | -------------------- | -------------------- |
| Claude Opus 4.8        | 97.8% / 97.8%        | 96.7% / 96.7%        |
| Claude Opus 4.7        | 98.9% / 98.9%        | 94.4% / 92.2%        |
| GPT-5.5                | 100.0% / 100.0%      | 98.9% / 98.9%        |
| GPT-5.6 Sol            | 96.7% / 96.7%        | 95.6% / 94.4%        |
| Gemini 3.1 Pro Preview | 100.0% / 100.0%      | 98.9% / 98.9%        |
| GPT-5.6 Terra          | 95.6% / 94.4%        | 96.7% / 96.7%        |
| GPT-5.4                | 100.0% / 100.0%      | 98.9% / 98.9%        |
| GPT-5.6 Luna           | 93.3% / 93.3%        | 93.3% / 93.3%        |


## False positives by rubric

Category rates overlap because a clean pair can receive more than one false rubric:


| Model                  | Overall FPR | Content | Structure | Formatting |
| ---------------------- | ----------- | ------- | --------- | ---------- |
| Claude Opus 4.8        | 6.5%        | 1.5%    | 4.7%      | 0.9%       |
| Claude Opus 4.7        | 12.1%       | 3.0%    | 8.4%      | 1.9%       |
| GPT-5.5                | 15.1%       | 11.2%   | 3.9%      | 5.4%       |
| GPT-5.6 Sol            | 15.6%       | 10.0%   | 3.7%      | 6.1%       |
| Gemini 3.1 Pro Preview | 19.3%       | 14.7%   | 7.2%      | 1.9%       |
| GPT-5.6 Terra          | 16.2%       | 11.5%   | 5.6%      | 5.8%       |
| GPT-5.4                | 25.5%       | 18.6%   | 7.4%      | 14.5%      |
| GPT-5.6 Luna           | 11.9%       | 8.7%    | 3.2%      | 3.2%       |


## GPT-5.5 versus GPT-5.6 Sol


| Measure                             | GPT-5.5 | GPT-5.6 Sol |
| ----------------------------------- | ------- | ----------- |
| Clean false positives               | 81/538  | 84/538      |
| True positives                      | 530/538 | 524/538     |
| Injected-rubric detections          | 528/538 | 522/538     |
| F1                                  | 92.3%   | 91.4%       |
| Estimated $/1k successful judgments | $76.59  | $32.73      |


GPT-5.5 leads by three clean false positives and six true positives, or 0.9 F1 points. Sol's estimated cost is 57% lower.

## Why Luna's FPR is lower

Luna produces 64 clean false positives and 455 true positives. Sol produces 84 and 524. Luna's lower FPR therefore comes with 69 additional misses on corrupted pairs.

Formatting accounts for most of the gap:


| Model | Formatting true positives | Injected formatting-rubric hits | Missed |
| ----- | ------------------------- | ------------------------------- | ------ |
| Sol   | 174/179                   | 173/179                         | 5      |
| Terra | 170/179                   | 168/179                         | 9      |
| Luna  | 112/179                   | 100/179                         | 67     |


Among Luna's 67 formatting misses, Sol catches 64, Terra catches 62, and both catch 61. Both specifically mark `formatting_fidelity=False` in all 61 shared catches. 

### Representative formatting disagreement

The source row in `chinese_finepdf_00008946_page_44_block_5` is regular and upright. Its [corrupted HTML](../../../data/benchmark/corrupted_html/chinese_finepdf_00008946_page_44_block_5_unexpected_bold_italic_row.html) makes every letter-containing body cell bold and italic. Sol and Terra identify the added emphasis; Luna returns all three rubrics as `True` and describes it as faithful. This example represents the measured 61-case shared pattern rather than an isolated miss.

Two additional cases confirm the same behavior: a regular English Hb row in `[finepdf_00290850_page_28_0](../../../data/benchmark/corrupted_html/finepdf_00290850_page_28_0_unexpected_bold_italic_row.html)`, and a German title that starts bold but upright in `[german_finepdf_00023497_page_4_block_2.aug_0](../../../data/benchmark/corrupted_html/german_finepdf_00023497_page_4_block_2.aug_0_unexpected_bold_italic_row.html)`. Sol and Terra identify the injected italics; Luna accepts both.

### Representative clean-pair false positive

The image and faithful HTML for `Pre-Primany / Primany` contain the same source misspelling. GPT-5.4, GPT-5.5, Claude Opus 4.8, Sol, Terra, and Luna reject the clean pair because they claim the source uses the corrected spelling. Sol and Gemini similarly reject a clean `Total income and endownments` pair after normalizing it to `endowments`. These cases illustrate a recurring failure mode: the judge copyedits instead of comparing.

## Token and cost calculation


| Model                  | Mean input | Mean reasoning | Mean visible or unseparated output | Est. $/1k successful |
| ---------------------- | ---------- | -------------- | ---------------------------------- | -------------------- |
| Claude Opus 4.8        | 2,526      | —              | 5,788                              | $157.33              |
| Claude Opus 4.7        | 2,537      | —              | 4,415                              | $123.05              |
| GPT-5.5                | 1,917      | 2,079          | 158                                | $76.59               |
| GPT-5.6 Sol            | 1,869      | 574            | 140                                | $32.73               |
| Gemini 3.1 Pro Preview | 2,139      | 1,954          | 162                                | $29.67               |
| GPT-5.6 Terra          | 1,869      | 719            | 154                                | $18.76               |
| GPT-5.4                | 1,885      | 4,113          | 190                                | $69.20               |
| GPT-5.6 Luna           | 1,869      | 1,894          | 156                                | $14.55               |


Anthropic does not separate adaptive-thinking tokens from visible output in returned usage, so its full output count appears in one column. The analyzer multiplies provider-reported token components by the rates in `[pricing-2026-07-08.json](../../../data/pricing-2026-07-08.json)`; every model entry in that file includes the official pricing URL.

