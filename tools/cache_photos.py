#!/usr/bin/env python3
"""Скачивает выбранные изображения Mail.ru и переводит сайт на локальные файлы."""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
DEST = ROOT / "assets" / "photos"
BASE = "https://thumb.cloud.mail.ru/weblink/thumb/xw1/YjPB/rkGWDEVGu/"
EXTS = ("JPG", "jpg", "JPEG", "jpeg", "PNG", "png")


def names() -> list[str]:
    text = HTML.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'data-photo="([A-Za-z0-9_-]+)"', text)))


def download(name: str) -> Path | None:
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / f"{name.lower()}.jpg"
    for ext in EXTS:
        url = f"{BASE}{urllib.parse.quote(name)}.{ext}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read()
            if not content_type.startswith("image/") or len(data) < 10_000:
                continue
            target.write_bytes(data)
            print(f"OK  {name}: {len(data) / 1024:.0f} KB")
            return target
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    print(f"ERR {name}: файл не найден", file=sys.stderr)
    return None


def localize_html(downloaded: dict[str, Path]) -> None:
    text = HTML.read_text(encoding="utf-8")
    for name, path in downloaded.items():
        remote_pattern = re.compile(
            rf'src="https://thumb\.cloud\.mail\.ru/weblink/thumb/xw1/YjPB/rkGWDEVGu/{re.escape(name)}\.[^"]+"'
        )
        local = path.relative_to(ROOT).as_posix()
        text = remote_pattern.sub(f'src="{local}"', text)
    HTML.write_text(text, encoding="utf-8")


def main() -> int:
    downloaded: dict[str, Path] = {}
    selected = names()
    for name in selected:
        result = download(name)
        if result:
            downloaded[name] = result
    if downloaded:
        localize_html(downloaded)
    print(f"Готово: {len(downloaded)} из {len(selected)}")
    return 0 if downloaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
