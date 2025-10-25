import argparse
import logging 
import requests 
import sys

# CLI flags
parser = argparse.ArgumentParser()
parser.add_argument("--query", help="What you want to query from the API")
parser.add_argument("--host", help="Base URL of the API, for example https://api.example.com")
parser.add_argument("--user", help="Username for authentication, if required")
parser.add_argument("--password", help="Password or API token for authentication, if required")
parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification (not recommended)")
parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output")
parser.add_argument("--out", help="File to save output instead of printing it")
parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds (default: 10)")
parser = argparse.ArgumentParser(
    description="Tiny API CLI: GET from a host with optional path, auth, logging and TLS controls.",
    epilog="Examples:\n  %(prog)s --host https://httpbin.org --query get\n  %(prog)s --host https://httpbin.org --query status/404 --verbose\n  %(prog)s --host https://expired.badssl.com --insecure --verbose\n  %(prog)s --host https://httpbin.org --query basic-auth/user/pass --user user --password pass --verbose\n  %(prog)s --host https://httpbin.org/get --out out.json",
    formatter_class=argparse.RawTextHelpFormatter

logger.debug(f"args: host={args.host} query={args.query} user={args.user} insecure={args.insecure} out={args.out} verbose={args.verbose}")

level = logging.DEBUG if args.verbose else logging.INFO
logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.info("CLI setup complete. Ready to connect to API.")

# Http session to connect to the API
session = requests.Session()
if args.insecure:
    session.verify = False
    logger.warning("TLS verification is DISABLED (--insecure). Use only with trusted servers.")
if args.user and args.password:
    session.auth = (args.user, args.password)
    logger.info("Using HTTP Basic Auth (user provided).")
if not args.host:
    logger.error("Missing --host (e.g., https://api.example.com)")
    sys.exit(2)
base = args.host.rstrip("/")
url = f"{base}/{args.query.lstrip('/')}" if args.query else base
logger.info(f"GET {url}")

# API request
try:
    resp = session.get(url, timeout=args.timeout)
    resp.raise_for_status()
# Error handling 
except requests.exceptions.SSLError:
    logger.error("TLS/SSL error. If this is a trusted server with a self-signed cert, re-run with --insecure. Otherwise, fix the certificate.")
    sys.exit(1)
except requests.exceptions.Timeout:
    logger.error("Request timed out. Check your network or try increasing the timeout.")
    sys.exit(1)
except requests.exceptions.ConnectionError as e:
    logger.error(f"Connection error: {e}. Check --host or your network.")
    sys.exit(1)
except requests.exceptions.HTTPError as e:
    status = getattr(getattr(e, "response", None), "status_code", None)
    text = getattr(getattr(e, "response", None), "text", "")
    snippet = text[:200] if text else ""
    logger.error(f"HTTP {status if status is not None else 'error'} received. Body: {snippet or '(empty)'}")
    sys.exit(1)

#Output needed
if args.out:
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(resp.text)
        logger.info(f"Wrote {len(resp.content)} bytes to {args.out}")
else:
    print(resp.text)

