"""
Telegram Webhook Setup and Diagnostic Utility.

Configures or inspects the Telegram Bot webhook for cloud deployments (e.g. Render).
Uses httpx to interact with https://api.telegram.org/bot<TOKEN>/

Usage:
  python scripts/setup_telegram_webhook.py info
  python scripts/setup_telegram_webhook.py set [--url https://your-app.onrender.com]
  python scripts/setup_telegram_webhook.py delete
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import httpx

# Load environment variables from backend/.env if available
backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")


def get_required_env(name: str, fallback_name: str | None = None) -> str:
    val = os.getenv(name)
    if not val and fallback_name:
        val = os.getenv(fallback_name)
    if not val:
        print(f"ERROR: Missing required environment variable '{name}'.", file=sys.stderr)
        if fallback_name:
            print(f"       (or fallback '{fallback_name}')", file=sys.stderr)
        print("Please set it in backend/.env or your shell environment.", file=sys.stderr)
        sys.exit(1)
    return val


def get_base_api_url(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"


def get_webhook_info(token: str) -> dict:
    url = f"{get_base_api_url(token)}/getWebhookInfo"
    resp = httpx.get(url, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data.get('description')}")
    return data.get("result", {})


def set_webhook(token: str, public_url: str, secret_token: str) -> dict:
    webhook_endpoint = f"{public_url.rstrip('/')}/api/telegram/webhook"
    url = f"{get_base_api_url(token)}/setWebhook"
    payload = {
        "url": webhook_endpoint,
        "secret_token": secret_token,
        "allowed_updates": ["message"],
        "drop_pending_updates": False,
    }
    resp = httpx.post(url, json=payload, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data.get('description')}")
    return data


def delete_webhook(token: str, drop_pending: bool = False) -> dict:
    url = f"{get_base_api_url(token)}/deleteWebhook"
    payload = {"drop_pending_updates": drop_pending}
    resp = httpx.post(url, json=payload, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data.get('description')}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Telegram webhook for Sophie.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # info command
    subparsers.add_parser("info", help="Get current Telegram webhook status")

    # set command
    set_parser = subparsers.add_parser("set", help="Register webhook URL with Telegram")
    set_parser.add_argument(
        "--url",
        help="Public base URL (e.g. https://ecofix-sophie.onrender.com). Defaults to PUBLIC_BASE_URL env var.",
    )

    # delete command
    del_parser = subparsers.add_parser("delete", help="Delete Telegram webhook")
    del_parser.add_argument(
        "--drop-pending",
        action="store_true",
        help="Drop any pending updates queued on Telegram servers",
    )

    args = parser.parse_args()
    bot_token = get_required_env("TELEGRAM_BOT_TOKEN")

    if args.command == "info":
        print("Checking Telegram webhook status...")
        info = get_webhook_info(bot_token)
        print("\n--- Current Telegram Webhook Info ---")
        print(json.dumps(info, indent=2))
        url = info.get("url")
        if url:
            print(f"\nStatus: Webhook is ACTIVE -> {url}")
            if info.get("last_error_message"):
                print(f"Warning: Last delivery error: {info.get('last_error_message')}")
        else:
            print("\nStatus: No webhook registered (bot is currently not receiving updates via webhook).")

    elif args.command == "set":
        public_url = args.url or os.getenv("PUBLIC_BASE_URL")
        if not public_url:
            print("ERROR: Public base URL must be provided via --url or PUBLIC_BASE_URL env var.", file=sys.stderr)
            sys.exit(1)

        secret_token = get_required_env("TELEGRAM_WEBHOOK_SECRET", "WEBHOOK_SECRET")
        print(f"Registering webhook at: {public_url.rstrip('/')}/api/telegram/webhook")
        res = set_webhook(bot_token, public_url, secret_token)
        print(f"Result: {res.get('description', 'OK')}")

    elif args.command == "delete":
        print(f"Deleting Telegram webhook (drop_pending_updates={args.drop_pending})...")
        res = delete_webhook(bot_token, drop_pending=args.drop_pending)
        print(f"Result: {res.get('description', 'OK')}")


if __name__ == "__main__":
    main()
