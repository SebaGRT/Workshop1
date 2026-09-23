#!/usr/bin/env python3
"""Descarga las bases públicas utilizadas en W1 (Chile, 2020-2024).

Fuentes oficiales:
- MINSAL/DEIS: Urgencias, REM y Establecimientos.
- FONASA: GRD.
- INE: cartografía del Censo 2024.

El script intenta resolver automáticamente tanto URLs directas como portales dinámicos.
No requiere paquetes externos: usa únicamente la biblioteca estándar de Python.

Uso habitual
------------
    python3 descargar_datos.py

Opciones útiles
---------------
    python3 descargar_datos.py --solo REM GRD
    python3 descargar_datos.py --force
    python3 descargar_datos.py --dry-run
    python3 descargar_datos.py --abrir-catalogos

Notas
-----
1. Los portales oficiales pueden cambiar su HTML o sus URLs. Para REM se usa primero
   el patrón histórico oficial del repositorio DEIS y, si falla, descubrimiento web.
2. Para FONASA GRD y la cartografía INE, el script rastrea las páginas oficiales y
   sus recursos (incluidos JavaScript) buscando los archivos de descarga publicados.
3. Cada descarga se valida de forma básica (tamaño, firma ZIP cuando corresponde) y
   se registra en DESCARGAS_REALIZADAS.csv con URL final, tamaño y SHA-256.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from html.parser import HTMLParser
import argparse
import csv
import hashlib
import html
import io
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile

ROOT = Path(__file__).resolve().parent
YEARS = tuple(range(2020, 2025))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 W1-BI-UDD/2026"
DEFAULT_TIMEOUT = 120

DIRECT = {
    "Urgencias": [
        (2020, "AtencionesUrgencia2020.zip", "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2020.zip"),
        (2021, "AtencionesUrgencia2021.zip", "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2021.zip"),
        (2022, "AtencionesUrgencia2022.zip", "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2022.zip"),
        (2023, "AtencionesUrgencia2023.zip", "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2023.zip"),
        (2024, "AtencionesUrgencia2024.zip", "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2024.zip"),
        ("2020-2024", "Diccionario_AtencionesUrgencia.xlsx", "https://datos.gob.cl/dataset/be2a922f-8ea4-4ebc-8828-0c713b702cd2/resource/79c05b22-391b-4dbd-a362-ba088fecabab/download/diccionario-de-datos-atencionesurgencia.xlsx"),
    ],
    "Establecimientos": [
        *[(y, f"Base_Establecimientos_{y}.xlsx", f"https://repositoriodeis.minsal.cl/ContenidoSitioWeb2020/Establecimientos/Base%20de%20Establecimientos%20{y}.xlsx") for y in YEARS],
        *[(y, f"Diccionario_Establecimientos_{y}.xlsx", f"https://repositoriodeis.minsal.cl/ContenidoSitioWeb2020/Establecimientos/Diccionario%20de%20Datos%20{y}.xlsx") for y in YEARS],
    ],
    # El patrón SERIE_REM_AAAA.zip está documentado en publicaciones que enlazan al
    # repositorio oficial DEIS y funciona históricamente para la serie anual REM.
    "REM": [
        *[(y, f"SERIE_REM_{y}.zip", f"https://repositoriodeis.minsal.cl/DatosAbiertos/REM/SERIE_REM_{y}.zip") for y in YEARS],
    ],
}

PORTALS = {
    "REM": [
        "https://deis.minsal.cl/#datosabiertos",
        "https://deis.minsal.cl/",
        "https://deis.minsal.cl/sistemas/",
    ],
    "GRD": [
        "https://www.fonasa.cl/sites/fonasa/datos-abiertos/bases-grd",
        "https://datosabiertos.fonasa.cl/",
    ],
    "cartografia_censo_2024": [
        "https://brave-grass-0c5df3c0f.3.azurestaticapps.net/",
        "https://censo2024.ine.gob.cl/resultados/",
        "https://www.ine.gob.cl/herramientas/portal-de-mapas/geodatos-abiertos",
    ],
}

BINARY_EXTS = (".zip", ".7z", ".rar", ".csv", ".xlsx", ".xls", ".parquet", ".geojson", ".gpkg", ".gdb", ".pdf")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self._href = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag.lower() == "a" and d.get("href"):
            self._href = d["href"]
            self._text = []
        if tag.lower() == "script" and d.get("src"):
            self.scripts.append(d["src"])

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def safe_name(s: str) -> str:
    s = unquote(str(s))
    return "".join(c if c.isalnum() or c in " ._-()[]" else "_" for c in s).strip() or "archivo"


def request(url: str, timeout: int, method: str = "GET", range_bytes: int | None = None):
    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.7",
        "Referer": url,
    }
    if range_bytes:
        headers["Range"] = f"bytes=0-{range_bytes-1}"
    req = urllib.request.Request(url, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_text(url: str, timeout: int, max_bytes: int = 6_000_000) -> tuple[str, str]:
    with request(url, timeout) as r:
        raw = r.read(max_bytes)
        final = r.geturl()
        ctype = (r.headers.get("Content-Type") or "").lower()
        charset = "utf-8"
        m = re.search(r"charset=([\w.-]+)", ctype)
        if m:
            charset = m.group(1)
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return text, final


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_download(path: Path, url: str) -> tuple[bool, str]:
    if not path.exists() or path.stat().st_size < 200:
        return False, "archivo demasiado pequeño"
    lower = (path.name + " " + url).lower()
    if ".zip" in lower:
        try:
            with zipfile.ZipFile(path) as z:
                bad = z.testzip()
                if bad:
                    return False, f"ZIP corrupto: {bad}"
        except zipfile.BadZipFile:
            return False, "no es un ZIP válido"
    return True, "OK"


def download(url: str, dest: Path, timeout: int, force: bool, dry_run: bool, log_rows: list[dict]) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print(f"  = {dest.relative_to(ROOT)} ya existe; se omite")
        ok, why = validate_download(dest, url)
        return ok
    print(f"  -> {dest.relative_to(ROOT)}")
    print(f"     {url}")
    if dry_run:
        return True
    tmp = dest.with_name(dest.name + ".part")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.7",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r, tmp.open("wb") as f:
            final_url = r.geturl()
            total = r.headers.get("Content-Length")
            copied = 0
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                copied += len(chunk)
                if total and total.isdigit() and copied % (10 * 1024 * 1024) < 1024 * 1024:
                    print(f"     {copied/1024/1024:.1f}/{int(total)/1024/1024:.1f} MB", end="\r")
        tmp.replace(dest)
        ok, why = validate_download(dest, url)
        if not ok:
            raise RuntimeError(why)
        digest = sha256(dest)
        size = dest.stat().st_size
        print(f"     OK {size/1024/1024:.1f} MB  sha256={digest[:16]}...")
        log_rows.append({
            "archivo": str(dest.relative_to(ROOT)),
            "url_solicitada": url,
            "url_final": final_url,
            "bytes": size,
            "sha256": digest,
            "fecha_descarga_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return True
    except Exception as e:
        print(f"     ERROR: {type(e).__name__}: {e}")
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        return False


def extract_urls_from_text(text: str, base_url: str) -> list[tuple[str, str]]:
    """Extrae enlaces de HTML/JS/JSON, incluidos URLs escapados en bundles JS."""
    text = html.unescape(text).replace("\\/", "/")
    out: list[tuple[str, str]] = []

    p = LinkParser()
    try:
        p.feed(text)
        for href, label in p.links:
            out.append((urljoin(base_url, href), label))
        for src in p.scripts:
            out.append((urljoin(base_url, src), "__SCRIPT__"))
    except Exception:
        pass

    # URLs absolutas y rutas de archivos comunes en JS/JSON.
    abs_rx = re.compile(r"https?://[^\s\"'<>\\]+", re.I)
    rel_rx = re.compile(r"(?:(?:\.\.?/)|/)[^\s\"'<>]+?\.(?:zip|7z|rar|csv|xlsx?|parquet|geojson|gpkg|pdf)(?:\?[^\s\"'<>]*)?", re.I)
    for m in abs_rx.finditer(text):
        u = m.group(0).rstrip(").,;]}>")
        out.append((u, ""))
    for m in rel_rx.finditer(text):
        out.append((urljoin(base_url, m.group(0)), ""))

    # Deduplicar conservando la etiqueta más informativa.
    dedup: dict[str, str] = {}
    for u, label in out:
        if not u.startswith(("http://", "https://")):
            continue
        if u not in dedup or (not dedup[u] and label):
            dedup[u] = label
    return list(dedup.items())


def is_binary_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in BINARY_EXTS) or any(ext + "?" in url.lower() for ext in BINARY_EXTS)


def crawl(seed_urls: list[str], timeout: int, max_pages: int = 20, max_depth: int = 2) -> list[tuple[str, str, str]]:
    """Rastreo pequeño de páginas oficiales; devuelve (url, label/context, source_page)."""
    q: list[tuple[str, int]] = [(u, 0) for u in seed_urls]
    seen: set[str] = set()
    found: dict[str, tuple[str, str]] = {}
    seed_hosts = {urlparse(u).netloc.lower() for u in seed_urls}

    while q and len(seen) < max_pages:
        url, depth = q.pop(0)
        if url in seen or depth > max_depth:
            continue
        seen.add(url)
        try:
            text, final = fetch_text(url, timeout)
        except Exception as e:
            print(f"     aviso: no se pudo leer {url}: {type(e).__name__}: {e}")
            continue
        for link, label in extract_urls_from_text(text, final):
            if is_binary_url(link):
                found.setdefault(link, (label, final))
                continue
            parsed = urlparse(link)
            host = parsed.netloc.lower()
            low = link.lower()
            # JS del propio sitio puede contener los links binarios que genera una SPA.
            if label == "__SCRIPT__" and depth <= max_depth:
                if host in seed_hosts or host.endswith("azurestaticapps.net"):
                    q.append((link, depth + 1))
                continue
            # Seguir sólo unas pocas páginas potencialmente relevantes del mismo ecosistema oficial.
            if depth < max_depth and (
                host in seed_hosts
                or host.endswith("fonasa.cl")
                or host.endswith("minsal.cl")
                or host.endswith("ine.gob.cl")
                or host.endswith("azurestaticapps.net")
            ):
                if any(k in low for k in ("grd", "rem", "censo", "cartograf", "descarga", "download", "datos-abiertos", "data")):
                    q.append((link, depth + 1))

    return [(u, label, src) for u, (label, src) in found.items()]


def rank_candidate(url: str, label: str, category: str, year: int | None = None) -> int:
    t = (url + " " + label).lower()
    score = 0
    if year is not None:
        score += 50 if str(year) in t else -20
    if category == "REM":
        score += 50 if "rem" in t else 0
        score += 30 if "serie" in t else 0
        score += 10 if ".zip" in t else 0
        score -= 40 if "remasep" in t else 0
    elif category == "GRD":
        score += 60 if "grd" in t else 0
        score += 25 if "publico" in t or "externo" in t else 0
        score += 15 if ".zip" in t else 0
        score -= 20 if "manual" in t or "informe" in t else 0
    elif category == "cartografia_censo_2024":
        score += 60 if "cartograf" in t else 0
        score += 35 if "censo" in t and "2024" in t else 0
        score += 30 if any(k in t for k in ("nacional", "pais", "país", "chile")) else 0
        score += 20 if any(k in t for k in ("shape", "shp", "geodatabase", "gdb")) else 0
        score += 15 if ".zip" in t else 0
        score -= 50 if any(k in t for k in ("microdato", "persona", "hogar", "vivienda")) else 0
        score -= 25 if any(k in t for k in ("region_", "regional")) else 0
    return score


def download_direct_category(cat: str, timeout: int, force: bool, dry_run: bool, logs: list[dict]) -> dict[int | str, bool]:
    status: dict[int | str, bool] = {}
    for year, name, url in DIRECT.get(cat, []):
        dest = ROOT / cat / (str(year) if isinstance(year, int) else "documentacion") / safe_name(name)
        status[year] = download(url, dest, timeout, force, dry_run, logs)
    return status


def download_rem_fallback(missing_years: list[int], timeout: int, force: bool, dry_run: bool, logs: list[dict]) -> list[int]:
    if not missing_years:
        return []
    print("\nREM: buscando automáticamente enlaces alternativos en DEIS...")
    candidates = crawl(PORTALS["REM"], timeout, max_pages=18, max_depth=2)
    still = []
    for y in missing_years:
        ranked = sorted(candidates, key=lambda x: rank_candidate(x[0], x[1], "REM", y), reverse=True)
        good = [c for c in ranked if rank_candidate(c[0], c[1], "REM", y) >= 70]
        success = False
        for url, label, src in good[:5]:
            name = Path(urlparse(url).path).name or f"SERIE_REM_{y}.zip"
            if str(y) not in (url + label):
                continue
            if download(url, ROOT / "REM" / str(y) / safe_name(name), timeout, force, dry_run, logs):
                success = True
                break
        if not success:
            still.append(y)
    return still



def download_rem_dictionaries(timeout: int, force: bool, dry_run: bool, logs: list[dict]) -> list[int]:
    """Intenta obtener los diccionarios anuales REM desde DEIS.

    DEIS indica que códigos, columnas y secciones pueden variar por año, por lo que
    el diccionario anual es parte útil del paquete. Primero se prueban convenciones
    históricas del repositorio y luego se rastrean los portales oficiales.
    """
    print("\nREM: buscando diccionarios anuales DEIS...")
    unresolved: list[int] = []
    discovered = None
    for y in YEARS:
        dest_dir = ROOT / "REM" / str(y) / "documentacion"
        guesses = [
            f"https://repositoriodeis.minsal.cl/DatosAbiertos/REM/DICCIONARIO_REM_{y}.xlsx",
            f"https://repositoriodeis.minsal.cl/DatosAbiertos/REM/Diccionario_REM_{y}.xlsx",
            f"https://repositoriodeis.minsal.cl/DatosAbiertos/REM/DICCIONARIO_{y}.xlsx",
            f"https://repositoriodeis.minsal.cl/DatosAbiertos/REM/Diccionario%20REM%20{y}.xlsx",
        ]
        ok = False
        # En ejecución real, detenerse al primer URL válido. En dry-run mostrar sólo el primero.
        for i, url in enumerate(guesses):
            if dry_run and i > 0:
                break
            if download(url, dest_dir / f"Diccionario_REM_{y}.xlsx", timeout, force, dry_run, logs):
                ok = True
                break
        if ok:
            continue
        if discovered is None:
            discovered = crawl(PORTALS["REM"], timeout, max_pages=22, max_depth=3)
        ranked = []
        for url, label, src in discovered:
            t = (url + " " + label).lower()
            score = 0
            score += 50 if "rem" in t else 0
            score += 60 if "diccion" in t else 0
            score += 50 if str(y) in t else -30
            score -= 80 if "remasep" in t else 0
            if score >= 100:
                ranked.append((score, url, label))
        ranked.sort(reverse=True)
        for _, url, label in ranked[:8]:
            ext = Path(urlparse(url).path).suffix or ".xlsx"
            if download(url, dest_dir / safe_name(f"Diccionario_REM_{y}{ext}"), timeout, force, dry_run, logs):
                ok = True
                break
        if not ok:
            unresolved.append(y)
    return unresolved

def discover_and_download_grd(timeout: int, force: bool, dry_run: bool, logs: list[dict]) -> list[int]:
    print("\nGRD: buscando archivos oficiales publicados por FONASA...")
    candidates = crawl(PORTALS["GRD"], timeout, max_pages=30, max_depth=3)
    missing = []
    for y in YEARS:
        ranked = sorted(candidates, key=lambda x: rank_candidate(x[0], x[1], "GRD", y), reverse=True)
        good = [c for c in ranked if rank_candidate(c[0], c[1], "GRD", y) >= 70]
        success = False
        for url, label, src in good[:8]:
            if str(y) not in (url + " " + label):
                continue
            name = Path(urlparse(url).path).name or f"GRD_{y}.zip"
            if download(url, ROOT / "GRD" / str(y) / safe_name(name), timeout, force, dry_run, logs):
                success = True
                break
        if not success:
            missing.append(y)
    return missing


def discover_and_download_censo(timeout: int, force: bool, dry_run: bool, logs: list[dict]) -> bool:
    print("\nCartografía Censo 2024: buscando paquete nacional oficial INE...")
    candidates = crawl(PORTALS["cartografia_censo_2024"], timeout, max_pages=35, max_depth=3)
    ranked = sorted(candidates, key=lambda x: rank_candidate(x[0], x[1], "cartografia_censo_2024"), reverse=True)

    # Primero intentar un paquete nacional claramente identificado.
    good = [c for c in ranked if rank_candidate(c[0], c[1], "cartografia_censo_2024") >= 80]
    for url, label, src in good[:12]:
        t = (url + " " + label).lower()
        if not ("cartograf" in t or "shape" in t or "shp" in t or "geodatabase" in t or "gdb" in t):
            continue
        name = Path(urlparse(url).path).name or "Cartografia_Censo_2024_Chile.zip"
        if download(url, ROOT / "cartografia_censo_2024" / safe_name(name), timeout, force, dry_run, logs):
            return True
    return False


def write_log(rows: list[dict]) -> None:
    if not rows:
        return
    path = ROOT / "DESCARGAS_REALIZADAS.csv"
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["archivo", "url_solicitada", "url_final", "bytes", "sha256", "fecha_descarga_local"])
        if not exists:
            w.writeheader()
        w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser(description="Descarga automática de fuentes W1 para BI trimestral.")
    p.add_argument("--solo", nargs="*", choices=["Urgencias", "REM", "Establecimientos", "GRD", "cartografia_censo_2024"],
                   help="Descargar únicamente las categorías indicadas.")
    p.add_argument("--force", action="store_true", help="Volver a descargar archivos existentes.")
    p.add_argument("--dry-run", action="store_true", help="Mostrar lo que haría sin descargar archivos.")
    p.add_argument("--abrir-catalogos", action="store_true", help="Abrir páginas oficiales si alguna descarga automática no se resuelve.")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout HTTP por solicitud (default: {DEFAULT_TIMEOUT}s).")
    args = p.parse_args()

    selected = set(args.solo or ["Urgencias", "REM", "Establecimientos", "GRD", "cartografia_censo_2024"])
    logs: list[dict] = []
    unresolved: dict[str, list[str]] = {}

    print("W1 Business Intelligence — descargas públicas Chile 2020-2024")
    print("Directorio:", ROOT)
    print("Categorías:", ", ".join(sorted(selected)))

    if "Urgencias" in selected:
        print("\n[Urgencias] Descarga directa MINSAL/DEIS")
        st = download_direct_category("Urgencias", args.timeout, args.force, args.dry_run, logs)
        bad = [str(k) for k, v in st.items() if not v]
        if bad:
            unresolved["Urgencias"] = bad

    if "Establecimientos" in selected:
        print("\n[Establecimientos] Descarga directa MINSAL/DEIS")
        st = download_direct_category("Establecimientos", args.timeout, args.force, args.dry_run, logs)
        bad = [str(k) for k, v in st.items() if not v]
        if bad:
            unresolved["Establecimientos"] = bad

    if "REM" in selected:
        print("\n[REM] Serie anual MINSAL/DEIS")
        st = download_direct_category("REM", args.timeout, args.force, args.dry_run, logs)
        missing = [y for y in YEARS if not st.get(y)]
        missing = download_rem_fallback(missing, args.timeout, args.force, args.dry_run, logs)
        missing_dict = download_rem_dictionaries(args.timeout, args.force, args.dry_run, logs)
        rem_issues = [f"base {y}" for y in missing] + [f"diccionario {y}" for y in missing_dict]
        if rem_issues:
            unresolved["REM"] = rem_issues

    if "GRD" in selected:
        missing = discover_and_download_grd(args.timeout, args.force, args.dry_run, logs)
        if missing:
            unresolved["GRD"] = [str(y) for y in missing]

    if "cartografia_censo_2024" in selected:
        ok = discover_and_download_censo(args.timeout, args.force, args.dry_run, logs)
        if not ok:
            unresolved["cartografia_censo_2024"] = ["2024"]

    if not args.dry_run:
        write_log(logs)

    if unresolved:
        print("\nNo se pudieron resolver automáticamente todos los archivos:")
        for cat, vals in unresolved.items():
            print(f"  - {cat}: {', '.join(vals)}")
            for u in PORTALS.get(cat, []):
                print(f"      {u}")
                if args.abrir_catalogos:
                    try:
                        webbrowser.open(u)
                    except Exception:
                        pass
        print("\nLos demás archivos sí quedan descargados. Puede volver a ejecutar el script; no repite archivos existentes.")
        return 2

    print("\nTodas las categorías seleccionadas quedaron resueltas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
