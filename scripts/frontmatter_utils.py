import fcntl
import os
import re
import time
from pathlib import Path


FRONTMATTER_RE = re.compile(r"^(---\s*\n)(.*?)(---\s*\n)", re.DOTALL)


def split_frontmatter(content: str) -> tuple[str, str, str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError("frontmatter missing")
    prefix = match.group(1)
    fm_text = match.group(2)
    suffix = match.group(3) + content[match.end():]
    return prefix, fm_text, suffix


def parse_frontmatter_text(fm_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def normalize_status(value: str | None) -> str:
    if value is None or value == "":
        return "active"
    normalized = value.split("#", 1)[0].strip()
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in ("'", '"')
    ):
        normalized = normalized[1:-1].strip()
    return normalized or "active"


def upsert_frontmatter_fields(content: str, updates: dict[str, str]) -> str:
    prefix, fm_text, suffix = split_frontmatter(content)
    lines = fm_text.splitlines()
    seen: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key in updates:
            new_lines.append(f"{key}: {updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}: {value}")

    new_fm_text = "\n".join(new_lines).rstrip() + "\n"
    return prefix + new_fm_text + suffix


def atomic_write_text(path: str, content: str, lock_path: str, timeout_seconds: float = 10.0) -> None:
    target = Path(path)
    lock = Path(lock_path)
    tmp = target.with_name(target.name + ".tmp")
    lock.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()

    with open(lock, "w", encoding="utf-8") as lock_file:
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > timeout_seconds:
                    raise TimeoutError(f"lock timeout: {lock}")
                time.sleep(0.1)

        try:
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, target)
        except Exception:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
            raise
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
