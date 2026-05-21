#!/usr/bin/env python3
"""Small read-only MCP server for Shopify Admin REST API access."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_FILE = PLUGIN_ROOT / ".env.local"


def load_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not LOCAL_ENV_FILE.exists():
        return values
    for line in LOCAL_ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


LOCAL_ENV = load_local_env()


def config_value(name: str, default: str = "") -> str:
    return os.getenv(name) or LOCAL_ENV.get(name, default)


API_VERSION = config_value("SHOPIFY_API_VERSION", "2025-10")
RAW_STORE_DOMAIN = config_value("SHOPIFY_STORE_DOMAIN")
ACCESS_TOKEN = config_value("SHOPIFY_ADMIN_ACCESS_TOKEN")
CLIENT_ID = config_value("SHOPIFY_CLIENT_ID")
CLIENT_SECRET = config_value("SHOPIFY_CLIENT_SECRET")
TOKEN_CACHE: dict[str, Any] = {"access_token": ACCESS_TOKEN, "expires_at": 0}


def normalize_store_domain(raw_domain: str) -> str:
    value = raw_domain.strip()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    host = (parsed.netloc or parsed.path).split("/")[0].strip().lower()
    if host == "admin.shopify.com" and parsed.path.startswith("/store/"):
        store_handle = parsed.path.split("/store/", 1)[1].split("/", 1)[0]
        return f"{store_handle}.myshopify.com"
    if "." not in host:
        return f"{host}.myshopify.com"
    return host


STORE_DOMAIN = normalize_store_domain(RAW_STORE_DOMAIN)


def send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def result(request_id: Any, content: Any) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": content})


def error(request_id: Any, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def require_config() -> None:
    missing = []
    if not STORE_DOMAIN:
        missing.append("SHOPIFY_STORE_DOMAIN")
    if not ACCESS_TOKEN and not (CLIENT_ID and CLIENT_SECRET):
        missing.append("SHOPIFY_CLIENT_ID")
        missing.append("SHOPIFY_CLIENT_SECRET")
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
    if not STORE_DOMAIN.endswith(".myshopify.com"):
        raise RuntimeError(
            "SHOPIFY_STORE_DOMAIN must be your canonical *.myshopify.com domain, "
            "not a custom storefront domain. Example: your-store.myshopify.com"
        )


def get_access_token() -> str:
    require_config()
    if ACCESS_TOKEN:
        return ACCESS_TOKEN

    cached_token = TOKEN_CACHE.get("access_token")
    expires_at = int(TOKEN_CACHE.get("expires_at") or 0)
    if cached_token and time.time() < expires_at - 60:
        return str(cached_token)

    body = urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode("utf-8")
    request = Request(
        f"https://{STORE_DOMAIN}/admin/oauth/access_token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "codex-shopify-plugin/0.1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise RuntimeError(
                "Shopify token exchange returned HTTP 404. Check SHOPIFY_STORE_DOMAIN: "
                f"the plugin is calling https://{STORE_DOMAIN}/admin/oauth/access_token. "
                "Use your canonical *.myshopify.com store domain, make sure the app is "
                "installed on that exact store, and confirm the Client ID belongs to that app."
            ) from exc
        raise RuntimeError(f"Shopify token exchange returned HTTP {exc.code}: {response_body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Shopify token endpoint: {exc.reason}") from exc

    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Shopify token exchange did not return an access_token.")

    expires_in = int(payload.get("expires_in") or 86400)
    TOKEN_CACHE["access_token"] = token
    TOKEN_CACHE["expires_at"] = int(time.time()) + expires_in
    return str(token)


def shopify_get(path: str, params: dict[str, Any] | None = None) -> Any:
    access_token = get_access_token()
    if not path.startswith("/"):
        path = "/" + path
    if not path.startswith(f"/admin/api/{API_VERSION}/"):
        path = f"/admin/api/{API_VERSION}{path}"
    query = ""
    if params:
        clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean_params:
            query = "?" + urlencode(clean_params)
    url = f"https://{STORE_DOMAIN}{path}{query}"
    request = Request(url, headers={
        "X-Shopify-Access-Token": access_token,
        "Accept": "application/json",
        "User-Agent": "codex-shopify-plugin/0.1.0",
    })
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Shopify API returned HTTP {exc.code}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Shopify API: {exc.reason}") from exc


def text_payload(data: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2, sort_keys=True)}]}


TOOLS = [
    {
        "name": "shopify_get_shop",
        "description": "Get basic metadata for the connected Shopify shop.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shopify_list_products",
        "description": "List products from the connected Shopify store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 250, "default": 50},
                "status": {"type": "string", "enum": ["active", "archived", "draft"]},
                "vendor": {"type": "string"},
                "product_type": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "shopify_list_orders",
        "description": "List recent orders from the connected Shopify store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 250, "default": 50},
                "status": {"type": "string", "default": "any"},
                "financial_status": {"type": "string"},
                "fulfillment_status": {"type": "string"},
                "created_at_min": {"type": "string", "description": "ISO 8601 lower bound."},
                "created_at_max": {"type": "string", "description": "ISO 8601 upper bound."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "shopify_list_customers",
        "description": "List customers from the connected Shopify store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 250, "default": 50},
                "created_at_min": {"type": "string", "description": "ISO 8601 lower bound."},
                "created_at_max": {"type": "string", "description": "ISO 8601 upper bound."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "shopify_request",
        "description": "Make a read-only GET request to a Shopify Admin REST endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Endpoint path, for example /products/count.json."},
                "params": {"type": "object", "additionalProperties": True},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    args = arguments or {}
    if name == "shopify_get_shop":
        return text_payload(shopify_get("/shop.json"))
    if name == "shopify_list_products":
        return text_payload(shopify_get("/products.json", {
            "limit": args.get("limit", 50),
            "status": args.get("status"),
            "vendor": args.get("vendor"),
            "product_type": args.get("product_type"),
        }))
    if name == "shopify_list_orders":
        return text_payload(shopify_get("/orders.json", {
            "limit": args.get("limit", 50),
            "status": args.get("status", "any"),
            "financial_status": args.get("financial_status"),
            "fulfillment_status": args.get("fulfillment_status"),
            "created_at_min": args.get("created_at_min"),
            "created_at_max": args.get("created_at_max"),
        }))
    if name == "shopify_list_customers":
        return text_payload(shopify_get("/customers.json", {
            "limit": args.get("limit", 50),
            "created_at_min": args.get("created_at_min"),
            "created_at_max": args.get("created_at_max"),
        }))
    if name == "shopify_request":
        path = str(args.get("path", ""))
        if not path:
            raise ValueError("path is required")
        return text_payload(shopify_get(path, args.get("params") or {}))
    raise ValueError(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        result(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "shopify", "version": "0.1.0"},
        })
    elif method == "notifications/initialized":
        return
    elif method == "tools/list":
        result(request_id, {"tools": TOOLS})
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        result(request_id, call_tool(tool_name, arguments))
    else:
        error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            handle(json.loads(line))
        except Exception as exc:
            request_id = None
            try:
                request_id = json.loads(line).get("id")
            except Exception:
                pass
            error(request_id, -32000, f"{exc}\n{traceback.format_exc(limit=2)}")


if __name__ == "__main__":
    main()
