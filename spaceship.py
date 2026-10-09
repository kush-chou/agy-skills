#!/usr/bin/env python3
"""Spaceship.com / Spaceship.dev DNS & Domain Automation Tool.

Manages DNS resource records for domains registered on Spaceship using the
official REST API (https://docs.spaceship.dev).
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

API_BASE_URL = "https://spaceship.dev/api/v1"

# Standard Vercel Anycast IP addresses and CNAME target
VERCEL_A_RECORDS = ["76.76.21.21", "216.198.79.1", "64.29.17.1"]
VERCEL_CNAME_TARGET = "cname.vercel-dns.com"


class SpaceshipClient:
    """Client for the Spaceship.dev DNS API."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or os.getenv("SPACESHIP_API_KEY")
        self.api_secret = api_secret or os.getenv("SPACESHIP_API_SECRET")

        if not self.api_key or not self.api_secret:
            print("Error: SPACESHIP_API_KEY and SPACESHIP_API_SECRET must be set in your environment.", file=sys.stderr)
            sys.exit(1)

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    def list_records(self, domain: str, take: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """List all DNS resource records for a given domain."""
        url = f"{API_BASE_URL}/dns/records/{domain}?take={take}&skip={skip}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                return data.get("items", [])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"Error listing records for {domain} (HTTP {e.code}): {err_body}", file=sys.stderr)
            return []

    def set_records(self, domain: str, items: List[Dict[str, Any]], force: bool = True) -> bool:
        """Create or update DNS records for a domain."""
        url = f"{API_BASE_URL}/dns/records/{domain}"
        payload = json.dumps({"force": force, "items": items}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=self._headers(), method="PUT")

        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status in (200, 204)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"Error updating records for {domain} (HTTP {e.code}): {err_body}", file=sys.stderr)
            return False

    def delete_records(self, domain: str, records: List[Dict[str, Any]]) -> bool:
        """Delete specific DNS records for a domain."""
        url = f"{API_BASE_URL}/dns/records/{domain}"
        payload = json.dumps({"records": records}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=self._headers(), method="DELETE")

        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status in (200, 204)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"Error deleting records for {domain} (HTTP {e.code}): {err_body}", file=sys.stderr)
            return False

    def configure_vercel(self, domain: str, ttl: int = 300) -> bool:
        """Turnkey helper to point domain apex and www to Vercel."""
        items: List[Dict[str, Any]] = []

        # Apex A records
        for ip in VERCEL_A_RECORDS:
            items.append({"type": "A", "name": "@", "address": ip, "ttl": ttl})

        # Subdomain www CNAME record
        items.append({"type": "CNAME", "name": "www", "cname": VERCEL_CNAME_TARGET, "ttl": ttl})

        print(f"==> Configuring {domain} for Vercel...")
        for item in items:
            target = item.get("address") or item.get("cname")
            print(f"    • {item['type']:<5} {item['name']:<5} -> {target} (TTL {item['ttl']}s)")

        success = self.set_records(domain, items, force=True)
        if success:
            print(f"✔ Successfully configured {domain} for Vercel on Spaceship!\n")
        else:
            print(f"✖ Failed to configure {domain} on Spaceship.\n", file=sys.stderr)
        return success


def cmd_list(args: argparse.Namespace, client: SpaceshipClient) -> None:
    records = client.list_records(args.domain)
    print(f"\n=== DNS Records for {args.domain} ({len(records)} found) ===")
    if not records:
        print("  (No custom DNS records set)")
    else:
        for r in records:
            rtype = r.get("type", "")
            name = r.get("name", "")
            target = r.get("address") or r.get("cname") or r.get("value") or ""
            ttl = r.get("ttl", 300)
            group = r.get("group", {}).get("type", "")
            print(f"  • {rtype:<6} {name:<8} -> {target:<30} (TTL {ttl}s) [{group}]")
    print("")


def cmd_vercel(args: argparse.Namespace, client: SpaceshipClient) -> None:
    domains = [args.domain] if args.domain else ["agy-skills.sh", "agy-skills.com"]
    for d in domains:
        client.configure_vercel(d, ttl=args.ttl)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spaceship.py",
        description="Automate Spaceship.dev DNS records and domain routing.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    p_list = subparsers.add_parser("list", help="List DNS records for a domain.")
    p_list.add_argument("domain", help="Target domain (e.g. agy-skills.sh)")

    # vercel command
    p_vercel = subparsers.add_parser("vercel", help="Point domain(s) to Vercel (apex + www).")
    p_vercel.add_argument("domain", nargs="?", default=None, help="Target domain (defaults to agy-skills.sh and agy-skills.com)")
    p_vercel.add_argument("--ttl", type=int, default=300, help="DNS TTL in seconds (default: 300)")

    args = parser.parse_args()

    client = SpaceshipClient()

    if args.command == "list":
        cmd_list(args, client)
    elif args.command == "vercel":
        cmd_vercel(args, client)
    else:
        # Default action: list records for agy-skills.sh and agy-skills.com
        for d in ["agy-skills.sh", "agy-skills.com"]:
            records = client.list_records(d)
            print(f"\n🌐 {d}: {len(records)} record(s)")
            for r in records:
                rtype = r.get("type", "")
                name = r.get("name", "")
                target = r.get("address") or r.get("cname") or r.get("value") or ""
                ttl = r.get("ttl", 300)
                print(f"   {rtype:<6} {name:<6} -> {target} (TTL {ttl}s)")
        print("\nUse `python3 spaceship.py --help` for available subcommands.")


if __name__ == "__main__":
    main()
