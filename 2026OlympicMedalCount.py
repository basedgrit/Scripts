"""
MC 2026 Olympic Medal Dashboard - Code Flow Overview
=====================================================

This script creates a live-updating web dashboard showing top 3 countries by gold medals
for the 2026 Winter Olympics. The data flow:

1. BACKGROUND UPDATER THREAD (updater_loop):
   - Runs continuously at a configurable interval (default 60 seconds)
   - Fetches the Wikipedia medal table, parses HTML tables to extract medal counts
   - Extracts top 3 countries by gold medals and stores in shared STATE dict
   - Catches and stores any errors in shared STATE for display

2. HTTP SERVER (Handler class + ThreadingHTTPServer):
   - Listens on localhost:8787 (configurable)
   - GET /: Serves HTML dashboard with embedded JavaScript
   - GET /api/top3: Returns current STATE as JSON
   - POST /api/refresh: Triggers immediate medal update (manual refresh)

3. BROWSER (JavaScript):
   - Auto-loads dashboard at startup (unless --no-browser flag)
   - Polls /api/top3 every N seconds to fetch latest data
   - Updates HTML display with top 3 countries and medal counts
   - Shows last update timestamp and any errors

Key threading: Shared STATE dict is protected by LOCK to prevent data races.

Run:
  python .\2026OlympicMedalCount.py --interval 60

Open:
  http://127.0.0.1:8787/
  http://127.0.0.1:8787/api/top3
"""

# Standard library: argument parsing, dates, JSON, threading, HTTP server, web browser automation
import argparse
import datetime as dt
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from urllib.parse import urlparse  # Strip query strings from URLs

# Third-party: data processing and HTTP requests
import pandas as pd
import requests

# Optional: improves country-name -> ISO2 code matching for accurate flag images
try:
    import pycountry  # pip install pycountry
except Exception:
    pycountry = None  # Fallback if not installed

# Wikipedia URL with ?action=render for cleaner HTML (strips navigation skin)
WIKI_RENDER = "https://en.wikipedia.org/wiki/2026_Winter_Olympics_medal_table?action=render"

# Version string sent in API responses and User-Agent
APP_VERSION = "flags-img-v1"

# Hardcoded country-name -> ISO 3166-1 alpha-2 code mapping for flags.
# Works without pycountry. Add more entries as needed for better coverage.
NAME_TO_ISO2 = {
    "Norway": "NO",
    "Switzerland": "CH",
    "Austria": "AT",
    "Germany": "DE",
    "Sweden": "SE",
    "Finland": "FI",
    "Netherlands": "NL",
    "France": "FR",
    "Italy": "IT",
    "United States": "US",
    "United States of America": "US",
    "Canada": "CA",
    "United Kingdom": "GB",
    "Great Britain": "GB",
    "Japan": "JP",
    "China": "CN",
    "South Korea": "KR",
    "Republic of Korea": "KR",
    "Czechia": "CZ",
    "Czech Republic": "CZ",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "Poland": "PL",
    "Ukraine": "UA",
    "Belgium": "BE",
    "Denmark": "DK",
    "Ireland": "IE",
    "Iceland": "IS",
    "Spain": "ES",
    "Australia": "AU",
    "New Zealand": "NZ",
}

NAME_ALIASES = {
    "Great Britain": "United Kingdom",
    "United States of America": "United States",
    "Czech Republic": "Czechia",
    "Korea, South": "South Korea",
    "Korea, North": "North Korea",
    "Russian Federation": "Russia",
}


def country_to_iso2(country: str) -> str:
    """Convert country name to ISO 3166-1 alpha-2 code for flag image URLs."""
    name = (country or "").strip()
    # Normalize variations (e.g., "United States of America" -> "United States")
    name = NAME_ALIASES.get(name, name)

    # Try built-in hardcoded map first (fastest, works offline)
    if name in NAME_TO_ISO2:
        return NAME_TO_ISO2[name]

    # Fallback to pycountry if available and name is not empty
    if not pycountry or not name:
        return ""

    # Try exact match in pycountry
    hit = pycountry.countries.get(name=name)
    if hit:
        return getattr(hit, "alpha_2", "") or ""

    # Try fuzzy search (handles slight name variations)
    try:
        hit = pycountry.countries.search_fuzzy(name)[0]
        return getattr(hit, "alpha_2", "") or ""
    except Exception:
        # Name not found: return empty string
        return ""


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert multi-level column headers to single strings joined with ' | '."""
    if isinstance(df.columns, pd.MultiIndex):
        # Join nested column levels with separator, skip NaN values
        df.columns = [
            " | ".join([str(x) for x in col if str(x) != "nan"]).strip()
            for col in df.columns.to_list()
        ]
    else:
        # Single-level columns: just convert to strings
        df.columns = [str(c) for c in df.columns]
    return df


def pick_col(cols, tokens):
    """Find first column name containing all tokens (case-insensitive substring match)."""
    for c in cols:
        s = str(c).lower()
        # Return column if all tokens appear somewhere in the column name
        if all(t.lower() in s for t in tokens):
            return c
    return None  # No match found


def fetch_medal_table() -> pd.DataFrame:
    """
    Returns: DataFrame columns [country, gold, silver, bronze, total]
    """
    resp = requests.get(
        WIKI_RENDER,
        headers={"User-Agent": f"mc2026-top3-web/{APP_VERSION}"},
        timeout=30,
    )
    resp.raise_for_status()

    tables = pd.read_html(StringIO(resp.text), flavor="lxml")

    for t in tables:
        df = flatten_columns(t.copy())
        joined = " ".join(str(c).lower() for c in df.columns)

        if not all(k in joined for k in ["gold", "silver", "bronze", "total"]):
            continue

        country_col = (
            pick_col(df.columns, ["noc"])
            or pick_col(df.columns, ["country"])
            or pick_col(df.columns, ["team"])
        )
        if country_col is None and len(df.columns) >= 2:
            country_col = df.columns[1]

        gold_col = pick_col(df.columns, ["gold"])
        silver_col = pick_col(df.columns, ["silver"])
        bronze_col = pick_col(df.columns, ["bronze"])
        total_col = pick_col(df.columns, ["total"])

        if not all([country_col, gold_col, silver_col, bronze_col, total_col]):
            continue

        out = df[[country_col, gold_col, silver_col, bronze_col, total_col]].copy()
        out.columns = ["country", "gold", "silver", "bronze", "total"]

        out["country"] = (
            out["country"].astype(str)
            .str.replace(r"\[.*?\]", "", regex=True)
            .str.strip()
        )

        out = out[~out["country"].str.lower().str.contains("total", na=False)]

        for c in ["gold", "silver", "bronze", "total"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")

        out = out.dropna(subset=["gold", "silver", "bronze", "total"]).copy()
        for c in ["gold", "silver", "bronze", "total"]:
            out[c] = out[c].astype(int)

        out = out[out["country"].str.len() > 0]
        return out

    raise RuntimeError("No medal table found (page layout changed or table not present yet).")


def top3_by_gold(df: pd.DataFrame):
    t3 = (
        df.sort_values(["gold", "silver", "bronze", "country"],
                       ascending=[False, False, False, True])
        .head(3)
        .reset_index(drop=True)
    )

    rows = []
    for i in range(len(t3)):
        country = str(t3.loc[i, "country"])
        rows.append({
            "rank": i + 1,
            "country": country,
            "iso2": country_to_iso2(country),  # ✅ for flag images
            "gold": int(t3.loc[i, "gold"]),
            "silver": int(t3.loc[i, "silver"]),
            "bronze": int(t3.loc[i, "bronze"]),
        })
    return rows


STATE = {
    "version": APP_VERSION,
    "updated_at": None,
    "source": "Wikipedia (rendered)",
    "rows": [],
    "error": None,
}
LOCK = threading.Lock()


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MC 2026 • Top 3 Gold</title>
  <style>
  :root{
    /* responsive sizing knobs */
    --pad: clamp(8px, 3vw, 18px);
    --radius: clamp(10px, 2.5vw, 16px);

    --title: clamp(14px, 3.4vw, 22px);
    --meta: clamp(10px, 2.2vw, 14px);
    --row: clamp(14px, 3.8vw, 24px);

    --flagw: clamp(18px, 5.5vw, 30px); /* flag width scales with window */
    --gap: clamp(6px, 1.6vw, 10px);
  }

  body {
    font-family: system-ui, Segoe UI, Arial, sans-serif;
    margin: var(--pad);
  }

  /* Fill the available window */
  .card {
    width: calc(100vw - (var(--pad) * 2));
    height: calc(100vh - (var(--pad) * 2));
    max-width: none;

    border: 1px solid #ddd;
    border-radius: var(--radius);
    padding: var(--pad);

    display: flex;
    flex-direction: column;
    box-sizing: border-box;
  }

  .title {
    font-size: var(--title);
    font-weight: 700;
    margin-bottom: 6px;
    line-height: 1.1;
  }

  .meta {
    color: #555;
    font-size: var(--meta);
    margin-bottom: 10px;
  }

  /* Rows container grows/shrinks with window */
  #rows {
    flex: 1;
    overflow: auto;
  }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;

    font-size: var(--row);
    padding: 8px 0;
    border-top: 1px solid #eee;
    line-height: 1.1;
  }
  .row:first-of-type { border-top: none; }

  .left {
    display: flex;
    align-items: center;
    gap: var(--gap);
    min-width: 0;
  }

  .left span {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .flagimg{
    width: var(--flagw);
    aspect-ratio: 4 / 3;   /* matches 24x18 */
    height: auto;
    border-radius: 2px;
    box-shadow: 0 0 0 1px rgba(0,0,0,0.06);
    flex: 0 0 auto;
  }

  button {
    margin-top: var(--pad);
    padding: clamp(6px, 1.8vw, 10px) clamp(10px, 2.4vw, 14px);
    border-radius: 10px;
    border: 1px solid #ccc;
    background: #fff;
    cursor: pointer;
    font-size: var(--meta);
    align-self: flex-start;
  }
  button:hover { background: #f6f6f6; }

  .err {
    color: #b00020;
    font-size: var(--meta);
    margin-top: 10px;
    white-space: pre-wrap;
  }
</style>

</head>
<body>
  <div class="card">
    <div class="title">Milano Cortina 2026 — Top 3 (Gold)</div>
    <div class="meta" id="meta">Loading…</div>

    <div id="rows"></div>

    <div style="margin-top: 12px;">
      <button onclick="refreshNow()">Refresh now</button>
    </div>

    <div class="err" id="err"></div>
  </div>

<script>
  const intervalSec = __INTERVAL__;

  function flagImgHTML(iso2, country){
    const code = (iso2 || "").toLowerCase();
    if (!code) return "";
    // FlagCDN (free). Needs internet access from your browser.
    return `
      <img class="flagimg"
           src="https://flagcdn.com/24x18/${code}.png"
           srcset="https://flagcdn.com/48x36/${code}.png 2x"
           alt="${country} flag">`;
  }

  async function load() {
    const res = await fetch("/api/top3?ts=" + Date.now(), { cache: "no-store" });
    const data = await res.json();

    document.getElementById("meta").textContent =
      `v${data.version} • Last updated: ${data.updated_at || "—"} • Source: ${data.source} • Refresh: ${intervalSec}s`;

    const rowsDiv = document.getElementById("rows");
    rowsDiv.innerHTML = "";

    if (data.rows && data.rows.length) {
      data.rows.forEach(r => {
        const div = document.createElement("div");
        div.className = "row";

        const flag = flagImgHTML(r.iso2, r.country);

        div.innerHTML =
          `<div class="left">${r.rank}. ${flag}<span>${r.country}</span></div>` +
          `<div><b>${r.gold}</b> 🥇</div>`;

        rowsDiv.appendChild(div);
      });
    } else {
      const div = document.createElement("div");
      div.className = "row";
      div.innerHTML = `<div>—</div><div>—</div>`;
      rowsDiv.appendChild(div);
    }

    document.getElementById("err").textContent = data.error ? ("Update error: " + data.error) : "";
  }

  async function refreshNow() {
    await fetch("/api/refresh?ts=" + Date.now(), { method: "POST", cache: "no-store" });
    await load();
  }

  load();
  setInterval(load, intervalSec * 1000);
</script>
</body>
</html>
"""


def updater_loop(interval_sec: int):
    while True:
        try:
            df = fetch_medal_table()
            rows = top3_by_gold(df)
            stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with LOCK:
                STATE["updated_at"] = stamp
                STATE["rows"] = rows
                STATE["error"] = None
        except Exception as e:
            with LOCK:
                STATE["error"] = f"{type(e).__name__}: {e}"
        time.sleep(interval_sec)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path  # strips ?ts=...

        if path == "/":
            page = HTML_TEMPLATE.replace("__INTERVAL__", str(self.server.interval_sec))
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/top3":
            with LOCK:
                payload = dict(STATE)

            # Bulletproof: ensure iso2 exists even if something upstream changed
            for r in payload.get("rows", []):
                if "iso2" not in r or not r.get("iso2"):
                    r["iso2"] = country_to_iso2(r.get("country", ""))

            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path  # strips ?ts=...

        if path == "/api/refresh":
            def one_shot():
                try:
                    df = fetch_medal_table()
                    rows = top3_by_gold(df)
                    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with LOCK:
                        STATE["updated_at"] = stamp
                        STATE["rows"] = rows
                        STATE["error"] = None
                except Exception as e:
                    with LOCK:
                        STATE["error"] = f"{type(e).__name__}: {e}"

            threading.Thread(target=one_shot, daemon=True).start()
            self._send(200, b"OK", "text/plain; charset=utf-8")
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")


def main():
    ap = argparse.ArgumentParser(description="MC 2026 Top 3 Gold (local web dashboard + flag images).")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--interval", type=int, default=60, help="Seconds between updates (default: 60).")
    ap.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab.")
    args = ap.parse_args()

    interval = max(30, args.interval)

    threading.Thread(target=updater_loop, args=(interval,), daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.interval_sec = interval

    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        webbrowser.open(url)

    print(f"Serving at {url} (updates every {interval}s) version={APP_VERSION}")
    server.serve_forever()


if __name__ == "__main__":
    main()
