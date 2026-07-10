from __future__ import annotations

import html as html_lib
import random
import re
from pathlib import Path

from .benchmark import (
    BenchmarkCase,
    ErrorInjection,
    inject_wrong_cell_value,
    inject_wrong_row_count,
)


ERROR_TYPES = ("content", "formatting", "structure")


def _has_visible_letter(cell: str) -> bool:
    text = html_lib.unescape(re.sub(r"<[^>]*>", "", cell))
    return any(character.isalpha() for character in text)


def _is_bold_and_italic(cell: str) -> bool:
    return bool(
        re.search(r"<(?:b|strong)(?:\s[^>]*)?>", cell, re.IGNORECASE)
        and re.search(r"<(?:i|em)(?:\s[^>]*)?>", cell, re.IGNORECASE)
    )


def _letter_runs(value: str) -> list[tuple[int, int]]:
    runs = []
    start = None
    index = 0
    while index < len(value):
        if value[index] == "<" and (end := value.find(">", index + 1)) >= 0:
            if start is not None:
                runs.append((start, index))
                start = None
            index = end + 1
            continue
        entity = re.match(
            r"&(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);",
            value[index:],
            re.IGNORECASE,
        )
        if entity:
            if start is not None:
                runs.append((start, index))
                start = None
            index += len(entity.group(0))
            continue
        if value[index].isalpha():
            start = index if start is None else start
        elif start is not None:
            runs.append((start, index))
            start = None
        index += 1
    if start is not None:
        runs.append((start, len(value)))
    return runs


def _transpose_letters(value: str) -> str | None:
    center = (len(value) - 2) / 2
    for index in sorted(range(len(value) - 1), key=lambda item: (abs(item - center), item)):
        if value[index] != value[index + 1]:
            return value[:index] + value[index + 1] + value[index] + value[index + 2 :]
    return None


def inject_text_typo(html: str) -> tuple[str, ErrorInjection | None]:
    candidates = []
    for cell in re.finditer(
        r"<td(?:\s[^>]*)?>(?P<content>.*?)</td>",
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        content = cell.group("content")
        for start, end in _letter_runs(content):
            original = content[start:end]
            corrupted = _transpose_letters(original)
            if corrupted is not None:
                candidates.append((len(original), cell, start, end, original, corrupted))
    if not candidates:
        return html, None

    _, cell, start, end, original, corrupted = max(candidates, key=lambda item: item[0])
    absolute_start = cell.start("content") + start
    absolute_end = cell.start("content") + end
    changed = html[:absolute_start] + corrupted + html[absolute_end:]
    return changed, ErrorInjection(
        "content",
        "misspelled_text",
        original,
        corrupted,
        cell.group(0)[:80],
        "content_accuracy",
    )


def inject_body_row_emphasis(html: str) -> tuple[str, ErrorInjection | None]:
    rows = list(re.finditer(r"<tr>.*?</tr>", html, re.DOTALL | re.IGNORECASE))
    candidates = []
    for row_index, match in enumerate(rows):
        row = match.group(0)
        if re.search(r"<th(?:\s[^>]*)?>", row, re.IGNORECASE):
            continue
        if not re.search(r"<td(?:\s[^>]*)?>", row, re.IGNORECASE):
            continue
        cells = re.findall(
            r"<td(?:\s[^>]*)?>(.*?)</td>",
            row,
            re.DOTALL | re.IGNORECASE,
        )
        target_count = sum(
            _has_visible_letter(cell) and not _is_bold_and_italic(cell)
            for cell in cells
        )
        if target_count == 0:
            continue
        candidates.append((target_count, row_index, match))
    if not candidates:
        return html, None

    target_count, row_index, match = max(candidates, key=lambda candidate: candidate[0])

    def emphasize_cell(cell_match: re.Match[str]) -> str:
        cell = cell_match.group("cell")
        if not _has_visible_letter(cell) or _is_bold_and_italic(cell):
            return cell_match.group(0)
        return (
            f'{cell_match.group("opening")[:-1]} '
            f'style="font-weight: bold; font-style: italic">'
            f'{cell}{cell_match.group("closing")}'
        )

    changed_row = re.sub(
        r"(?P<opening><td(?:\s[^>]*)?>)(?P<cell>.*?)(?P<closing></td>)",
        emphasize_cell,
        match.group(0),
        flags=re.DOTALL | re.IGNORECASE,
    )
    changed = html[: match.start()] + changed_row + html[match.end() :]
    return changed, ErrorInjection(
        "formatting",
        "unexpected_bold_italic_row",
        f"default emphasis on {target_count} alphabetic body cells",
        f"bold italic emphasis on {target_count} alphabetic body cells",
        f"body row {row_index}",
        "formatting_fidelity",
    )


def _corruption_candidates(html: str) -> dict[str, tuple[str, ErrorInjection]]:
    candidates = {}
    for kind, injector in (
        ("content_numeric", inject_wrong_cell_value),
        ("content_typo", inject_text_typo),
        ("formatting", inject_body_row_emphasis),
        ("structure", inject_wrong_row_count),
    ):
        corrupted, error = injector(html)
        if error is not None:
            candidates[kind] = (corrupted, error)
    return candidates


def _targets(total: int) -> dict[str, int]:
    base, remainder = divmod(total, len(ERROR_TYPES))
    return {
        error_type: base + (index < remainder)
        for index, error_type in enumerate(ERROR_TYPES)
    }


def _kind_targets(total: int) -> dict[str, int]:
    targets = _targets(total)
    return _content_targets(targets["content"]) | {
        "formatting": targets["formatting"],
        "structure": targets["structure"],
    }


def _content_targets(total: int) -> dict[str, int]:
    base, remainder = divmod(total, 2)
    return {
        "content_numeric": base + remainder,
        "content_typo": base,
    }


def _assign_candidates(
    prepared: list[tuple[Path, Path, dict[str, tuple[str, ErrorInjection]]]],
    remaining: dict[str, int],
    seed: int,
) -> list[BenchmarkCase]:
    prepared = prepared.copy()
    rng = random.Random(seed)
    rng.shuffle(prepared)
    prepared.sort(key=lambda item: sum(kind in remaining for kind in item[2]))
    cases = []
    for index, (image_path, html_path, candidates) in enumerate(prepared):
        future = prepared[index + 1 :]
        options = []
        for kind in remaining:
            if remaining[kind] == 0 or kind not in candidates:
                continue
            after = remaining | {kind: remaining[kind] - 1}
            if all(
                after[target] <= sum(target in later[2] for later in future)
                for target in remaining
            ):
                support = 1 + sum(kind in later[2] for later in future)
                options.append((remaining[kind] / support, kind))
        if not options:
            raise ValueError("cannot satisfy balanced corruption targets with available tables")
        _, kind = max(options, key=lambda item: (item[0], item[1]))
        remaining[kind] -= 1
        corrupted_html, error = candidates[kind]
        cases.append(BenchmarkCase(
            image_path.stem,
            image_path,
            html_path,
            corrupted_html,
            error,
        ))
    return cases


def build_balanced_cases(
    html_dir: Path,
    image_dir: Path,
    seed: int = 0,
    error_type_by_stem: dict[str, str] | None = None,
) -> list[BenchmarkCase]:
    prepared = []
    for image_path in sorted(image_dir.glob("*.png")):
        html_path = html_dir / f"{image_path.stem}.html"
        if not html_path.is_file():
            continue
        candidates = _corruption_candidates(html_path.read_text(encoding="utf-8"))
        if candidates:
            prepared.append((image_path, html_path, candidates))

    if error_type_by_stem is None:
        cases = _assign_candidates(prepared, _kind_targets(len(prepared)), seed)
    else:
        stems = {image_path.stem for image_path, _, _ in prepared}
        if set(error_type_by_stem) != stems:
            raise ValueError("saved assignments do not match the available table stems")
        prepared_by_stem = {item[0].stem: item for item in prepared}
        prepared = [prepared_by_stem[stem] for stem in error_type_by_stem]
        content = [item for item in prepared if error_type_by_stem[item[0].stem] == "content"]
        cases = _assign_candidates(
            content,
            _content_targets(len(content)),
            seed,
        )
        for image_path, html_path, candidates in prepared:
            error_type = error_type_by_stem[image_path.stem]
            if error_type == "content":
                continue
            if error_type not in candidates:
                raise ValueError(
                    f"saved {error_type} assignment is unavailable for {image_path.stem}"
                )
            corrupted_html, error = candidates[error_type]
            cases.append(BenchmarkCase(
                image_path.stem,
                image_path,
                html_path,
                corrupted_html,
                error,
            ))

    cases.sort(key=lambda case: case.stem)
    return cases
