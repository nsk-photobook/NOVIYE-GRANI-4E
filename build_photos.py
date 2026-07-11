#!/usr/bin/env python3
"""Download real photos from a public Mail.ru Cloud folder and prepare GitHub Pages assets.

No authentication is used: only the public share link configured below.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import shutil
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

PUBLIC_SHARE = "YjPB/rkGWDEVGu"
PUBLIC_URL = f"https://cloud.mail.ru/public/{PUBLIC_SHARE}"
FOLDER_API = "https://cloud.mail.ru/api/v2/folder"
TOKEN_API = "https://cloud.mail.ru/api/v2/tokens/download"
OUTPUT_DIR = Path("photos")
MANIFEST = OUTPUT_DIR / "manifest.json"
MAX_SELECTED = 24
MAX_CANDIDATES = 90
MAX_SOURCE_BYTES = 45 * 1024 * 1024
MAX_TOTAL_DOWNLOAD = 1_200 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".jfif"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "ru,en;q=0.8",
}


@dataclass
class Candidate:
    name: str
    weblink: str
    size: int
    data: bytes | None = None
    width: int = 0
    height: int = 0
    score: float = 0.0
    dhash: int = 0

    @property
    def orientation(self) -> str:
        ratio = self.width / max(self.height, 1)
        if ratio > 1.16:
            return "landscape"
        if ratio < 0.86:
            return "portrait"
        return "square"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get_json(s: requests.Session, url: str, **kwargs):
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = s.get(url, timeout=(20, 90), **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Не удалось получить JSON: {url}: {last_error}")


def get_text(s: requests.Session, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = s.get(url, timeout=(20, 90))
            response.raise_for_status()
            return response.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Не удалось открыть {url}: {last_error}")


def get_token(s: requests.Session) -> str:
    payload = None
    try:
        payload = get_json(s, TOKEN_API)
    except Exception:
        # Some Mail.ru deployments expose this endpoint as POST.
        response = s.post(TOKEN_API, timeout=(20, 90))
        response.raise_for_status()
        payload = response.json()
    token = payload.get("body", {}).get("token") or payload.get("token")
    if not token:
        raise RuntimeError("Mail.ru не вернул download token")
    return str(token)


def decode_embedded_url(value: str) -> str:
    value = value.replace(r"\/", "/").replace(r"\u0026", "&")
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return value


def get_base_url(s: requests.Session) -> str:
    html = get_text(s, PUBLIC_URL)
    patterns = [
        r'"weblink_get"\s*:\s*\[\s*\{[^\]]*?"url"\s*:\s*"([^"]+)"',
        r'"weblink_get"\s*:\s*\[\s*\{\s*"count"\s*:\s*\d+\s*,\s*"url"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.S)
        if match:
            return decode_embedded_url(match.group(1)).rstrip("/")

    # Fallback for newer page payloads: locate any datacloudmail weblink/get endpoint.
    match = re.search(r'https?:\\?/\\?/[^"<]+?datacloudmail\\?\.ru\\?/weblink/get', html)
    if match:
        return decode_embedded_url(match.group(0)).rstrip("/")
    raise RuntimeError("Не найден сервер скачивания Mail.ru (weblink_get)")


def normalize_weblink(item: dict) -> str:
    link = str(item.get("weblink") or "").strip()
    for prefix in ("https://cloud.mail.ru/public/", "http://cloud.mail.ru/public/"):
        if link.startswith(prefix):
            link = link[len(prefix):]
    link = link.strip("/")
    name = str(item.get("name") or "").strip("/")
    if name and not link.endswith("/" + name) and link != name:
        link = f"{link}/{name}" if link else f"{PUBLIC_SHARE}/{name}"
    return link


def list_folder(s: requests.Session, weblink: str) -> list[dict]:
    result: list[dict] = []
    offset = 0
    limit = 500
    while True:
        payload = get_json(
            s,
            FOLDER_API,
            params={"weblink": weblink.strip("/"), "offset": offset, "limit": limit, "api": 2},
        )
        body = payload.get("body", payload)
        items = body.get("list") or []
        result.extend(items)
        if len(items) < limit:
            break
        offset += limit
    return result


def walk_public_folder(s: requests.Session, root: str) -> list[Candidate]:
    found: list[Candidate] = []
    visited: set[str] = set()

    def walk(link: str) -> None:
        normalized = link.strip("/")
        if normalized in visited:
            return
        visited.add(normalized)
        for item in list_folder(s, normalized):
            item_type = str(item.get("type") or "")
            item_link = normalize_weblink(item)
            name = str(item.get("name") or Path(item_link).name)
            if item_type == "folder":
                walk(item_link)
            elif item_type == "file":
                ext = Path(name).suffix.lower()
                size = int(item.get("size") or 0)
                if ext in IMAGE_EXTENSIONS and (not size or size <= MAX_SOURCE_BYTES):
                    found.append(Candidate(name=name, weblink=item_link, size=size))

    walk(root)
    return found


def safe_path(path: str) -> str:
    return urllib.parse.quote(path, safe="/~@()$*!=:;,.+'")


def download_bytes(s: requests.Session, url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = s.get(url, headers={"Referer": PUBLIC_URL}, timeout=(20, 180))
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            data = response.content
            if data.startswith(b"<!DOCTYPE html") or "text/html" in content_type:
                raise RuntimeError("вместо изображения получена HTML-страница")
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Не удалось скачать {url}: {last_error}")


def difference_hash(image: Image.Image) -> int:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for row in range(8):
        for col in range(8):
            value <<= 1
            value |= pixels[row * 9 + col] > pixels[row * 9 + col + 1]
    return value


def analyze(candidate: Candidate) -> Candidate | None:
    assert candidate.data is not None
    try:
        with Image.open(io.BytesIO(candidate.data)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return None
    width, height = image.size
    if min(width, height) < 700 or width * height < 900_000:
        return None
    sample = image.convert("L")
    sample.thumbnail((256, 256), Image.Resampling.LANCZOS)
    edge = sample.filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edge).mean[0]
    contrast = ImageStat.Stat(sample).stddev[0]
    candidate.width = width
    candidate.height = height
    candidate.dhash = difference_hash(image)
    # Resolution matters, but avoid allowing it to dominate visual quality entirely.
    candidate.score = math.log2(width * height) + min(edge_mean / 8, 5) + min(contrast / 30, 3)
    return candidate


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def select_diverse(candidates: list[Candidate], limit: int) -> list[Candidate]:
    candidates.sort(key=lambda c: (-c.score, c.name.casefold()))
    unique: list[Candidate] = []
    for candidate in candidates:
        if any(hamming(candidate.dhash, other.dhash) <= 5 for other in unique):
            continue
        unique.append(candidate)

    selected: list[Candidate] = []
    targets = {"landscape": 11, "portrait": 10, "square": 3}
    for orientation, count in targets.items():
        selected.extend([c for c in unique if c.orientation == orientation][:count])
    selected_ids = {id(c) for c in selected}
    for candidate in unique:
        if len(selected) >= limit:
            break
        if id(candidate) not in selected_ids:
            selected.append(candidate)
            selected_ids.add(id(candidate))
    # Keep a natural filename order after quality/diversity selection.
    return sorted(selected[:limit], key=lambda c: c.name.casefold())


def save_webp(candidate: Candidate, output: Path) -> tuple[int, int]:
    assert candidate.data is not None
    with Image.open(io.BytesIO(candidate.data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "WEBP", quality=83, method=6)
    return image.size


def build_from_local(source_dir: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            item = Candidate(name=path.name, weblink=str(path), size=path.stat().st_size, data=path.read_bytes())
            analyzed = analyze(item)
            if analyzed:
                candidates.append(analyzed)
    return select_diverse(candidates, MAX_SELECTED)


def build_from_cloud() -> list[Candidate]:
    s = session()
    token = get_token(s)
    base_url = get_base_url(s)
    candidates = walk_public_folder(s, PUBLIC_SHARE)
    if not candidates:
        raise RuntimeError("В публичной папке не найдено поддерживаемых фотографий")

    # Prefer a deterministic filename order and cap traffic for very large source folders.
    candidates.sort(key=lambda c: c.name.casefold())
    analyzed: list[Candidate] = []
    downloaded = 0
    for candidate in candidates[:MAX_CANDIDATES]:
        if downloaded >= MAX_TOTAL_DOWNLOAD:
            break
        file_url = f"{base_url}/{safe_path(candidate.weblink)}?key={urllib.parse.quote(token)}"
        try:
            candidate.data = download_bytes(s, file_url)
            downloaded += len(candidate.data)
            prepared = analyze(candidate)
            if prepared:
                analyzed.append(prepared)
                print(f"OK  {candidate.name}  {candidate.width}x{candidate.height}")
            else:
                print(f"SKIP {candidate.name}: неподдерживаемое или слишком маленькое изображение")
        except Exception as exc:  # noqa: BLE001
            print(f"WARN {candidate.name}: {exc}", file=sys.stderr)

    if not analyzed:
        raise RuntimeError("Не удалось скачать и распознать фотографии из публичной папки")
    return select_diverse(analyzed, MAX_SELECTED)


def write_output(selected: list[Candidate]) -> None:
    temp = Path(".photos-build")
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True)
    entries = []
    # Use the strongest landscape image as the cover whenever possible.
    cover = max((c for c in selected if c.orientation == "landscape"), key=lambda c: c.score, default=max(selected, key=lambda c: c.score))
    ordered = [cover] + [c for c in selected if c is not cover]
    for index, candidate in enumerate(ordered, 1):
        filename = f"photo-{index:02d}.webp"
        width, height = save_webp(candidate, temp / filename)
        entries.append(
            {
                "src": f"photos/{filename}",
                "width": width,
                "height": height,
                "orientation": "landscape" if width > height * 1.16 else "portrait" if height > width * 1.16 else "square",
                "alt": f"Выпускной альбом 4Е — фотография {index}",
            }
        )

    if not entries:
        raise RuntimeError("Нет выбранных фотографий для публикации")
    manifest = {
        "title": "Новые грани · 4Е",
        "source": PUBLIC_URL,
        "count": len(entries),
        "hero": entries[0]["src"],
        "photos": entries,
    }
    (temp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    temp.rename(OUTPUT_DIR)
    print(f"Готово: {len(entries)} локальных WebP-фотографий в {OUTPUT_DIR}/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, help="Локальная папка для теста вместо Mail.ru")
    args = parser.parse_args()
    selected = build_from_local(args.source_dir) if args.source_dir else build_from_cloud()
    write_output(selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
