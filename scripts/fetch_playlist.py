#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lee el ultimo post con pinta de lista M3U de un canal publico de Telegram
(vista web t.me/s/<canal>) y lo escribe en el archivo de salida.

No necesita bot, ni token, ni PC: lo ejecuta GitHub Actions.
"""

from __future__ import annotations

import html
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CHANNEL = os.environ.get("SOURCE_CHANNEL", "").strip().lstrip("@")
OUT_PATH = Path(os.environ.get("OUT_PATH", "KN"))
ARCHIVE_DIR = os.environ.get("ARCHIVE_DIR", "historial").strip("/")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def balanced_div(source: str, start: int) -> tuple[str, int]:
    open_end = source.find(">", start)
    if open_end == -1:
        return "", len(source)
    pos = open_end + 1
    depth = 1
    open_re = re.compile(r"<div\b", re.I)
    close_re = re.compile(r"</div\s*>", re.I)
    while depth > 0:
        o = open_re.search(source, pos)
        c = close_re.search(source, pos)
        if not c:
            return source[open_end + 1 :], len(source)
        if o and o.start() < c.start():
            depth += 1
            pos = o.end()
        else:
            depth -= 1
            if depth == 0:
                return source[open_end + 1 : c.start()], c.end()
            pos = c.end()
    return "", len(source)


def html_to_text(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    text = re.sub(r"</div\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip("\n")


def channel_posts(channel: str) -> list[str]:
    page = fetch(f"https://t.me/s/{urllib.parse.quote(channel)}")
    marker = 'class="tgme_widget_message_text'
    texts: list[str] = []
    index = 0
    while True:
        found = page.find(marker, index)
        if found == -1:
            break
        open_start = page.rfind("<div", 0, found)
        if open_start == -1:
            break
        inner, index = balanced_div(page, open_start)
        texts.append(html_to_text(inner))
    return texts


def looks_like_playlist(text: str) -> bool:
    upper = text.upper()
    return "#EXTINF" in upper and ("ACESTREAM://" in upper or "HTTP" in upper)


def main() -> int:
    if not CHANNEL:
        print("ERROR: falta SOURCE_CHANNEL (ej: @micanal)", file=sys.stderr)
        return 2

    try:
        posts = channel_posts(CHANNEL)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR leyendo t.me/s/{CHANNEL}: {exc}", file=sys.stderr)
        return 2

    if not posts:
        print(f"No hay posts de texto en t.me/s/{CHANNEL} (¿canal privado?)")
        return 0

    playlists = [p for p in posts if looks_like_playlist(p)]
    if not playlists:
        print(f"Ninguno de los {len(posts)} ultimos posts parece una lista M3U; no cambio nada.")
        return 0

    text = playlists[-1].replace("\r\n", "\n").replace("\r", "\n").strip("\n") + "\n"
    entries = sum(1 for line in text.splitlines() if line.lstrip().startswith("#EXTINF"))
    print(f"Lista encontrada: {entries} entradas, {len(text.encode('utf-8'))} bytes")

    current = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
    if current == text:
        print("Sin cambios: el archivo ya tiene esa lista.")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8", newline="\n")

    if ARCHIVE_DIR:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        archive = Path(ARCHIVE_DIR) / f"{stamp}.m3u"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(text, encoding="utf-8", newline="\n")
        print(f"Copia en {archive}")

    print(f"Actualizado {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
