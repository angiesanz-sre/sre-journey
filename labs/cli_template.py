#!/usr/bin/env python3
import os
import sys
import logging
import argparse
from pathlib import Path
import requests
import time
import json
from typing import Optional

def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Tiny API CLI: GET from a host with optional path, auth, logging, TLS controls.",
        epilog=(
            "Examples:\n"
            "  %(prog)s --host https://httpbin.org --query get\n"
            "  %(prog)s --host https://httpbin.org --query status/404 --verbose\n"
            "  %(prog)s --host https://expired.badssl.com --insecure --verbose\n"
            "  %(prog)s --host https://httpbin.org --query basic-auth/user/pass --user user --password pass --verbose\n"
            "  %(prog)s --host https://httpbin.org/get --out out.json\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--query", help="Path you want to GET from the host (e.g., 'get' or 'status/404').")
    p.add_argument("--host", default=os.getenv("SPLUNK_HOST"), help="Base URL, e.g. https://api.example.com (or $SPLUNK_HOST)")
    p.add_argument("--user", default=os.getenv("SPLUNK_USER"), help="Username for auth (or $SPLUNK_USER)")
    p.add_argument("--password", default=os.getenv("SPLUNK_PASSWORD"), help="Password/token for auth (or $SPLUNK_PASSWORD)")
    p.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification (NOT recommended).")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    p.add_argument("--out", help="File to save output instead of printing it. Parent dirs will be created.")
    p.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds (default: 10)")
    p.add_argument("--search", required=True, help="The Splunk search string to run, e.g. 'search index=_internal | head 5'")
    p.add_argument("--earliest", help="Earliest time for the search, e.g. -15m@m or 2025-10-26T00:00:00")
    p.add_argument("--latest", help="Latest time for the search, e.g. now or 2025-10-26T23:59:59")
    p.add_argument("--outdir", help="Directory to save results (default: a folder named with today's date)")


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger("tiny-cli")

def make_session(args, logger: logging.Logger) -> requests.Session:
    if not args.host:
        logger.error("Missing --host (or $SPLUNK_HOST). Example: https://api.example.com")
        sys.exit(2)
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    if args.insecure:
        s.verify = False
        logger.warning("TLS verification is DISABLED (--insecure). Use only with trusted servers.")
    if args.user and args.password:
        s.auth = (args.user, args.password)
        logger.info("Using HTTP Basic Auth (user/password provided).")
    return s

def create_search_job(session, base, search, earliest, latest, timeout):
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
        raise RuntimeError(f"Failed to create search job. Response: {data}")
    return sid

def poll_until_done(session, base, sid, timeout, logger, max_wait_s=120.0, interval_s=1.5):
    """
    Poll /services/search/jobs/<sid> until isDone == True.
    Raises TimeoutError if it doesn't finish within max_wait_s.
    """
    status_url = f"{base}/services/search/jobs/{sid}"
    deadline = time.time() + max_wait_s

    while True:
        # 1) Ask Splunk for the job status (JSON)
        resp = session.get(status_url, params={"output_mode": "json"}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # 2) Extract isDone safely (and loudly if the shape is unexpected)
        try:
            is_done = bool(data["entry"][0]["content"]["isDone"])
        except Exception:
            # Show a short snippet so it's debuggable
            raise RuntimeError(f"Unexpected job status payload: {json.dumps(data)[:300]}")

        # 3) Stop conditions
        if is_done:
            logger.info("Search job %s is done.", sid)
            return

        if time.time() > deadline:
            raise TimeoutError(f"Search job {sid} not done after {max_wait_s}s.")

        # 4) Not done yet: wait a bit and try again
        logger.debug("Waiting for job %s to finish...", sid)
        time.sleep(interval_s)

def fetch_results_json(session, base, sid, timeout):
    """
    Download results as JSON.
    Returns a Python dict (parsed JSON).
    """
    url = f"{base}/services/search/jobs/{sid}/results"
    params = {"output_mode": "json", "count": 0}
    resp = session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_results_csv(session, base, sid, timeout):
    """
    Download results as CSV.
    Returns the CSV as a string.
    """
    url = f"{base}/services/search/jobs/{sid}/results"
    params = {"output_mode": "csv", "count": 0}
    resp = session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def main(argv=None) -> int:
    parser = build_parser()
    add_common_args(parser)
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbose)

    base = args.host.rstrip("/")
    url = f"{base}/{args.query.lstrip('/')}" if args.query else base
    logger.debug("args parsed: host=%s query=%s insecure=%s out=%s verbose=%s",
                 args.host, args.query, args.insecure, args.out, args.verbose)
    logger.info("GET %s", url)

    try:
        resp = requests.Session()  # we want our configured session:
        session = make_session(args, logger)
        resp = session.get(url, timeout=args.timeout)
        resp.raise_for_status()
    except requests.exceptions.SSLError:
        logger.error("TLS/SSL error. If this is a trusted server with a self-signed cert, re-run with --insecure. Otherwise, fix the certificate.")
        return 1
    except requests.exceptions.Timeout:
        logger.error("Request timed out. Check your network or increase --timeout.")
        return 1
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection error: %s. Check --host or your network.", e)
        return 1
    except requests.exceptions.HTTPError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        text = getattr(getattr(e, "response", None), "text", "")
        snippet = (text or "")[:200]
        logger.error("HTTP %s received. Body: %s", status if status is not None else "error", snippet or "(empty)")
        return 1
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return 1

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        logger.info("Wrote %d bytes to %s", len(resp.content), out_path)
    else:
        print(resp.text)

    return 0

if __name__ == "__main__":
    sys.exit(main())
