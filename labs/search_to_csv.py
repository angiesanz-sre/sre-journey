import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

import requests


# ---------- Utilities ----------

def today_stamp() -> str:
    """UTC date string for folder naming, e.g., '20251026'."""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ---------- CLI + Logging ----------

def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Run a Splunk search via REST and save results to CSV + JSON.",
        epilog=(
            "Examples:\n"
            "  %(prog)s --host https://stack.splunkcloud.com "
            "--user $SPLUNK_USER --password $SPLUNK_PASSWORD "
            "--search 'search index=_internal | head 5'\n"
            "  %(prog)s --host https://stack.splunkcloud.com "
            "--search 'search index=_internal sourcetype=splunkd' "
            "--earliest -15m@m --latest now --verbose\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

def add_args(p: argparse.ArgumentParser) -> None:
    # Connection & behavior
    p.add_argument("--host", default=os.getenv("SPLUNK_HOST"),
                   help="Splunk base URL (or $SPLUNK_HOST), e.g. https://stack.splunkcloud.com")
    p.add_argument("--user", default=os.getenv("SPLUNK_USER"),
                   help="Username (or $SPLUNK_USER)")
    p.add_argument("--password", default=os.getenv("SPLUNK_PASSWORD"),
                   help="Password or token (or $SPLUNK_PASSWORD)")
    p.add_argument("--timeout", type=float, default=20.0,
                   help="HTTP timeout seconds (default: 20)")
    p.add_argument("--insecure", action="store_true",
                   help="Skip TLS cert verification (NOT recommended)")
    p.add_argument("--verbose", action="store_true",
                   help="Enable debug logging")

    # Search inputs
    p.add_argument("--search", required=True,
                   help="SPL to run, e.g. 'search index=_internal | head 5'")
    p.add_argument("--earliest",
                   help="earliest_time, e.g. -15m@m or 2025-10-26T00:00:00")
    p.add_argument("--latest",
                   help="latest_time, e.g. now or 2025-10-26T23:59:59")

    # Output location
    p.add_argument("--outdir",
                   help="Directory to save results (default: today's UTC date folder)")


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger("search-to-csv")


# ---------- HTTP helpers ----------

def make_session(args, logger: logging.Logger) -> requests.Session:
    if not args.host or not args.user or not args.password:
        logger.error("Missing host/user/password. Use flags or env vars: "
                     "SPLUNK_HOST, SPLUNK_USER, SPLUNK_PASSWORD.")
        sys.exit(2)

    s = requests.Session()
    s.auth = (args.user, args.password)
    s.headers.update({"Accept": "application/json"})
    s.verify = not args.insecure
    if args.insecure:
        logger.warning("TLS verification DISABLED (--insecure). Use only with trusted servers.")
    return s


# ---------- Splunk search flow ----------

def create_search_job(session: requests.Session, base: str, search: str,
                      earliest: str | None, latest: str | None, timeout: float) -> str:
    """Create a Splunk search job and return its SID."""
    url = f"{base}/services/search/jobs"
    payload = {"search": search}
    if earliest:
        payload["earliest_time"] = earliest
    if latest:
        payload["latest_time"] = latest

    resp = session.post(url, data=payload, params={"output_mode": "json"}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    sid = data.get("sid")
    if not sid:
        raise RuntimeError(f"Failed to create search job. Response: {json.dumps(data)[:300]}")
    return sid


def poll_until_done(session: requests.Session, base: str, sid: str, timeout: float,
                    logger: logging.Logger, max_wait_s: float = 120.0, interval_s: float = 1.5) -> None:
    """
    Poll /services/search/jobs/<sid> until isDone == True.
    Raises TimeoutError if it doesn't finish within max_wait_s.
    """
    status_url = f"{base}/services/search/jobs/{sid}"
    deadline = time.time() + max_wait_s

    while True:
        resp = session.get(status_url, params={"output_mode": "json"}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        try:
            is_done = bool(data["entry"][0]["content"]["isDone"])
        except Exception:
            raise RuntimeError(f"Unexpected job status payload: {json.dumps(data)[:300]}")

        if is_done:
            logger.info("Search job %s is done.", sid)
            return

        if time.time() > deadline:
            raise TimeoutError(f"Search job {sid} not done after {max_wait_s}s.")

        logger.debug("Waiting for job %s to finish...", sid)
        time.sleep(interval_s)


def fetch_results_json(session: requests.Session, base: str, sid: str, timeout: float) -> dict:
    """Download results as JSON (parsed to dict)."""
    url = f"{base}/services/search/jobs/{sid}/results"
    resp = session.get(url, params={"output_mode": "json", "count": 0}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_results_csv(session: requests.Session, base: str, sid: str, timeout: float) -> str:
    """Download results as CSV (raw text)."""
    url = f"{base}/services/search/jobs/{sid}/results"
    resp = session.get(url, params={"output_mode": "csv", "count": 0}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# ---------- Main ----------

def main(argv=None) -> int:
    parser = build_parser()
    add_args(parser)
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbose)

    base = (args.host or "").rstrip("/")
    session = make_session(args, logger)

    try:
        logger.info("Creating search job...")
        sid = create_search_job(session, base, args.search, args.earliest, args.latest, args.timeout)
        logger.info("SID: %s", sid)

        logger.info("Polling until job completes...")
        poll_until_done(session, base, sid, args.timeout, logger)

        logger.info("Fetching results (JSON + CSV)...")
        results_json = fetch_results_json(session, base, sid, args.timeout)
        results_csv  = fetch_results_csv(session, base, sid, args.timeout)

        folder = Path(args.outdir or today_stamp())
        folder.mkdir(parents=True, exist_ok=True)
        stamp = folder.name  # e.g., 20251026
        json_path = folder / f"results-{stamp}.json"
        csv_path  = folder / f"results-{stamp}.csv"

        json_path.write_text(json.dumps(results_json, indent=2), encoding="utf-8")
        csv_path.write_text(results_csv, encoding="utf-8")
        logger.info("Saved JSON → %s", json_path)
        logger.info("Saved CSV  → %s", csv_path)
        return 0

    except requests.exceptions.SSLError:
        logger.error("TLS/SSL error. If using a self-signed cert, try --insecure (last resort).")
        return 1
    except requests.exceptions.Timeout:
        logger.error("Request timed out. Try a smaller search or increase --timeout.")
        return 1
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection error: %s. Verify --host and network reachability.", e)
        return 1
    except requests.exceptions.HTTPError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        text = getattr(getattr(e, "response", None), "text", "")
        snippet = (text or "")[:300]
        logger.error("HTTP %s from Splunk. Body: %s", status if status is not None else "error", snippet or "(empty)")
        logger.error("Troubleshooting: check credentials/role, --host, and --timeout.")
        return 1
    except TimeoutError as e:
        logger.error(str(e))
        logger.error("Tip: increase max wait or narrow the time range.")
        return 1
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
