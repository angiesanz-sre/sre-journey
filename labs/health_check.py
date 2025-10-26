#!/usr/bin/env python3
import os
import sys
import logging
import argparse
import requests

# ---------- CLI + Logging ----------

def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Check Splunk server health via /services/server/health.",
        epilog=(
            "Example:\n"
            "  %(prog)s --host https://stack.splunkcloud.com "
            "--user $SPLUNK_USER --password $SPLUNK_PASSWORD --verbose\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default=os.getenv("SPLUNK_HOST"),
                   help="Base URL (or $SPLUNK_HOST), e.g. https://stack.splunkcloud.com")
    p.add_argument("--user", default=os.getenv("SPLUNK_USER"),
                   help="Username for auth (or $SPLUNK_USER)")
    p.add_argument("--password", default=os.getenv("SPLUNK_PASSWORD"),
                   help="Password or token (or $SPLUNK_PASSWORD)")
    p.add_argument("--timeout", type=float, default=10.0,
                   help="Request timeout in seconds (default: 10)")
    p.add_argument("--insecure", action="store_true",
                   help="Skip TLS certificate verification (NOT recommended)")
    p.add_argument("--verbose", action="store_true",
                   help="Enable debug logging")

def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger("health-check")

# ---------- HTTP Session ----------

def make_session(args, logger: logging.Logger) -> requests.Session:
    if not args.host or not args.user or not args.password:
        logger.error("Missing host/user/password. Use flags or env vars: SPLUNK_HOST, SPLUNK_USER, SPLUNK_PASSWORD.")
        sys.exit(2)

    s = requests.Session()
    s.auth = (args.user, args.password)
    s.headers.update({"Accept": "application/json"})
    s.verify = not args.insecure
    if args.insecure:
        logger.warning("TLS verification DISABLED (--insecure). Use only with trusted servers.")
    return s

# ---------- Main ----------

def main(argv=None) -> int:
    parser = build_parser()
    add_common_args(parser)
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbose)

    base = (args.host or "").rstrip("/")
    session = make_session(args, logger)

    # Health-check: GET /services/server/health?output_mode=json
    try:
        url = f"{base}/services/server/health"
        logger.info("GET %s", url)
        resp = session.get(url, params={"output_mode": "json"}, timeout=args.timeout)
        resp.raise_for_status()
        data = resp.json()

        overall = data["entry"][0]["content"]["overall_status"]
        print(f"overall_status: {overall}")

        if overall.lower() == "green":
            logger.info("Healthy")
            return 0
        else:
            logger.error("Unhealthy status: %s", overall)
            return 1

    except requests.exceptions.SSLError:
        logger.error("TLS/SSL error. If using a self-signed cert, try --insecure.")
        return 1
    except requests.exceptions.Timeout:
        logger.error("Request timed out. Check your network or increase --timeout.")
        return 1
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection error: %s. Verify --host and network reachability.", e)
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

if __name__ == "__main__":
    sys.exit(main())
