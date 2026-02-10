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
"""

# Standard library imports for CLI parsing, date/time, concurrency, and HTTP server
import argparse
import datetime as dt
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO

# Third-party imports for data processing and web requests
import pandas as pd
import requests

# Wikipedia URL for 2026 Winter Olympics medal table.
# Using "action=render" removes skin/navigation HTML and returns cleaner markup for parsing.
WIKI_RENDER = "https://en.wikipedia.org/wiki/2026_Winter_Olympics_medal_table?action=render"


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten multi-level DataFrame column names into single strings."""
    if isinstance(df.columns, pd.MultiIndex):
        # Join multi-level columns with " | " separator, skipping NaN entries
        df.columns = [
            " | ".join([str(x) for x in col if str(x) != "nan"]).strip()
            for col in df.columns.to_list()
        ]
    else:
        # Convert single-level columns to strings
        df.columns = [str(c) for c in df.columns]
    return df


def pick_col(cols, tokens):
    """Find first column name containing all tokens (case-insensitive)."""
    for c in cols:
        s = str(c).lower()
        # Return column if all search tokens are found in column name
        if all(t.lower() in s for t in tokens):
            return c
    return None  # No match found


def fetch_medal_table() -> pd.DataFrame:
    """Fetch medal table from Wikipedia. Returns DataFrame with columns:
    country, gold, silver, bronze, total.
    """
    # Fetch rendered Wikipedia page with browser user-agent
    resp = requests.get(
        WIKI_RENDER,
        headers={"User-Agent": "mc2026-top3-web/1.0"},
        timeout=30,
    )
    resp.raise_for_status()  # Raise error on bad HTTP status

    # Extract all HTML tables from the page
    tables = pd.read_html(StringIO(resp.text), flavor="lxml")

    # Search through tables for one matching medal columns pattern
    for t in tables:
        df = flatten_columns(t.copy())
        # Join all column names to check if medal columns are present
        joined = " ".join(str(c).lower() for c in df.columns)

        # Skip tables that don't have all required medal columns
        if not all(k in joined for k in ["gold", "silver", "bronze", "total"]):
            continue

        # Try to find country column by looking for NOC, country, or team keywords
        country_col = (
            pick_col(df.columns, ["noc"])
            or pick_col(df.columns, ["country"])
            or pick_col(df.columns, ["team"])
        )
        # Fallback: use second column if no country column found
        if country_col is None and len(df.columns) >= 2:
            country_col = df.columns[1]

        # Find medal and total columns
        gold_col = pick_col(df.columns, ["gold"])
        silver_col = pick_col(df.columns, ["silver"])
        bronze_col = pick_col(df.columns, ["bronze"])
        total_col = pick_col(df.columns, ["total"])

        # Skip if any required column is missing
        if not all([country_col, gold_col, silver_col, bronze_col, total_col]):
            continue

        # Extract and rename relevant columns
        out = df[[country_col, gold_col, silver_col, bronze_col, total_col]].copy()
        out.columns = ["country", "gold", "silver", "bronze", "total"]

        # Clean country names: remove Wikipedia citations like [1], [2]
        out["country"] = (
            out["country"].astype(str)
            .str.replace(r"\[.*?\]", "", regex=True)
            .str.strip()
        )

        # Remove summary rows that contain "total" in country name
        out = out[~out["country"].str.lower().str.contains("total", na=False)]

        # Convert medal columns to numeric (coerce errors to NaN)
        for c in ["gold", "silver", "bronze", "total"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")

        # Drop rows with missing medal counts, then convert to integers
        out = out.dropna(subset=["gold", "silver", "bronze", "total"]).copy()
        for c in ["gold", "silver", "bronze", "total"]:
            out[c] = out[c].astype(int)

        # Filter out empty country names
        out = out[out["country"].str.len() > 0]
        return out

    # No valid medal table found in page
    raise RuntimeError("No medal table found (page layout may have changed or table not present yet).")


def top3_by_gold(df: pd.DataFrame):
    """Return list of top 3 countries by gold medal count (with tiebreaker)."""
    # Sort by gold (desc), then silver (desc), then bronze (desc), then country name (asc)
    t3 = (
        df.sort_values(["gold", "silver", "bronze", "country"],
                       ascending=[False, False, False, True])
          .head(3)
          .reset_index(drop=True)
    )
    rows = []
    # Build list of dicts with rank and medal counts
    for i in range(len(t3)):
        rows.append({
            "rank": i + 1,
            "country": str(t3.loc[i, "country"]),
            "gold": int(t3.loc[i, "gold"]),
            "silver": int(t3.loc[i, "silver"]),
            "bronze": int(t3.loc[i, "bronze"]),
        })
    return rows


# Shared state dictionary protected by a threading lock for thread-safe access.
# Contains: updated_at (timestamp), source, rows (top 3 list), error (if any)
STATE = {
    "updated_at": None,
    "source": "Wikipedia (rendered)",
    "rows": [],
    "error": None,
}
LOCK = threading.Lock()  # Synchronizes access to STATE across threads


# HTML template for browser dashboard. Contains embedded JavaScript for auto-refresh.
HTML_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MC 2026 • Top 3 Gold</title>
  <style>
    body { font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 24px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; max-width: 520px; }
    .title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
    .meta { color: #555; font-size: 13px; margin-bottom: 12px; }
    .row { display: flex; justify-content: space-between; font-size: 18px; padding: 8px 0; border-top: 1px solid #eee; }
    .row:first-of-type { border-top: none; }
    .muted { color: #666; font-size: 13px; margin-top: 10px; }
    button { padding: 8px 10px; border-radius: 10px; border: 1px solid #ccc; background: #fff; cursor: pointer; }
    button:hover { background: #f6f6f6; }
    .err { color: #b00020; font-size: 13px; margin-top: 10px; white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="card">
    <div class="title">Milano Cortina 2026 — Top 3 (Gold)</div>
    <div class="meta" id="meta">Loading…</div>

    <div id="rows"></div>

    <div style="margin-top: 14px;">
      <button onclick="refreshNow()">Refresh now</button>
    </div>

    <div class="muted">Auto-refreshes every <span id="interval"></span> seconds.</div>
    <div class="err" id="err"></div>
  </div>

<script>
  const intervalSec = __INTERVAL__;
  document.getElementById("interval").textContent = intervalSec;

  async function load() {
    const res = await fetch("/api/top3");
    const data = await res.json();

    document.getElementById("meta").textContent =
      `Last updated: ${data.updated_at || "—"} • Source: ${data.source}`;

    const rowsDiv = document.getElementById("rows");
    rowsDiv.innerHTML = "";

    if (data.rows && data.rows.length) {
      data.rows.forEach(r => {
        const div = document.createElement("div");
        div.className = "row";
        div.innerHTML = `<div>${r.rank}. ${r.country}</div><div><b>${r.gold}</b> 🥇</div>`;
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
    await fetch("/api/refresh", { method: "POST" });
    await load();
  }

  load();
  setInterval(load, intervalSec * 1000);
</script>
</body>
</html>
"""


def updater_loop(interval_sec: int):
    """Background thread: periodically fetch medals and update shared STATE."""
    while True:
        try:
            # Fetch current medal table from Wikipedia
            df = fetch_medal_table()
            rows = top3_by_gold(df)
            stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Update shared state safely
            with LOCK:
                STATE["updated_at"] = stamp
                STATE["rows"] = rows
                STATE["error"] = None
        except Exception as e:
            # Store error message in shared state if fetch fails
            with LOCK:
                STATE["error"] = f"{type(e).__name__}: {e}"
        time.sleep(interval_sec)  # Wait before next update


class Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the local server."""
    def _send(self, code: int, body: bytes, content_type: str):
        """Helper to send HTTP response with standard headers."""
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")  # Prevent caching
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests: / returns HTML dashboard, /api/top3 returns JSON data."""
        if self.path == "/":
            # Serve HTML page with interval replaced
            page = HTML_PAGE.replace("__INTERVAL__", str(self.server.interval_sec))
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return

        if self.path == "/api/top3":
            # Return current state as JSON
            with LOCK:
                payload = dict(STATE)
            self._send(200, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        """Handle POST requests: /api/refresh manually triggers a medal table update."""
        if self.path == "/api/refresh":
            # Run update in background thread to avoid blocking the request
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
    """Parse CLI args, start updater thread, and launch HTTP server."""
    ap = argparse.ArgumentParser(description="MC 2026 Top 3 Gold (local web dashboard, no Tk).")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--interval", type=int, default=60, help="Seconds between background updates (recommended 60+).")
    ap.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab.")
    args = ap.parse_args()

    # Enforce minimum interval for API rate-limiting courtesy
    interval = max(30, args.interval)

    # Start background updater thread (daemon so it exits with main)
    t = threading.Thread(target=updater_loop, args=(interval,), daemon=True)
    t.start()

    # Create and configure local HTTP server
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.interval_sec = interval

    # Open browser tab unless --no-browser flag set
    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        webbrowser.open(url)

    print(f"Serving Top 3 dashboard at {url} (updates every {interval}s)")
    server.serve_forever()  # Block until interrupted


# Entry point: run main() when script is executed directly
if __name__ == "__main__":
    main()
