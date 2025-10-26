import os
import sys
import time
import json
import logging
import argparse

import requests

# ---------- CLI + Logging ----------

def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Validate event ingestion by checking for recent events in an index.",
        epilog=(
        "Example:\n"
        "  %(prog)s --host https://stack.splunkcloud.com "
        "--user $SPLUNK_USER --password $SPLUNK_PASSWORD "
        "--index main --earliest -15m@m --latest now --verbose\n"
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

    # Ingestion inputs
    p.add_argument("--index", required=True,
               help="Splunk index to validate (e.g., main, _internal)")
    p.add_argument("--filter",
               help="Optional extra search terms, e.g., sourcetype=syslog host=web01")
    p.add_argument("--earliest", default="-15m@m",
               help="Earliest time for search (default: -15m@m)")
    p.add_argument("--latest", default="now",
               help="Latest time for search (default: now)")


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger("ingestion-validator")


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


# ---------- Main ----------

def main(argv=None) -> int:
    parser = build_parser()
    add_args(parser)
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbose)

    base = (args.host or "").rstrip("/")
    session = make_session(args, logger)

    # Build the SPL string
    search = f'search index="{args.index}"'
    if args.filter:
        search += f" {args.filter}"
    search += " | stats count as event_count"

    try:
        logger.info("Creating search job for ingestion validation...")
        sid = create_search_job(session, base, search, args.earliest, args.latest, args.timeout)
        poll_until_done(session, base, sid, args.timeout, logger)

        results = fetch_results_json(session, base, sid, args.timeout)

        # Default to 0 if results list is empty or field missing
        count = 0
        if results.get("results"):
            count = int(results["results"][0].get("event_count", "0"))

        print(f"Event count: {count}")
        if count > 0:
            logger.info("✅ Ingestion OK - events found in last interval")
            return 0
        else:
            logger.error("❌ No events found in last interval")
            return 1

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
