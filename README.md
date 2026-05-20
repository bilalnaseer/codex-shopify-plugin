# Shopify for Codex

Connect Codex to a Shopify store through the Shopify Admin REST API so you can chat with store data.

The plugin is read-only by default. It can fetch shop metadata, products, orders, customers, and other GET-only Admin REST endpoints without changing store data.

## Install

Clone the repository and run the installer:

```bash
git clone https://github.com/YOUR_USERNAME/codex-shopify-plugin.git ~/plugins/shopify
cd ~/plugins/shopify
./install.sh
```

Restart Codex, open Plugins, and enable **Shopify** from **Local Plugins**.

## Shopify Setup

1. Create an app in the Shopify Dev Dashboard.
2. Configure and release a version with the scopes you need, such as `read_products`, `read_orders`, and `read_customers`.
3. Install the app on your store.
4. Copy the Client ID and Client Secret from the app settings.

## Codex Environment

For Codex desktop on macOS, set environment variables with `launchctl` so GUI apps can read them:

```bash
launchctl setenv SHOPIFY_STORE_DOMAIN "your-store.myshopify.com"
launchctl setenv SHOPIFY_CLIENT_ID "your_client_id"
launchctl setenv SHOPIFY_CLIENT_SECRET "your_client_secret"
launchctl setenv SHOPIFY_API_VERSION "2025-10"
```

The MCP server exchanges the Client ID and Client Secret for a Shopify access token using the client credentials grant. If you have a legacy admin-created custom app with a long-lived token, you can still set `SHOPIFY_ADMIN_ACCESS_TOKEN` instead.

For terminal-only testing, regular shell exports also work:

```bash
export SHOPIFY_STORE_DOMAIN="your-store.myshopify.com"
export SHOPIFY_CLIENT_ID="your_client_id"
export SHOPIFY_CLIENT_SECRET="your_client_secret"
export SHOPIFY_API_VERSION="2025-10"
```

## Included MCP Tools

- `shopify_get_shop`: show store profile and metadata.
- `shopify_list_products`: list products and variants.
- `shopify_list_orders`: list recent orders.
- `shopify_list_customers`: list customers.
- `shopify_request`: make a read-only GET request to another Shopify Admin REST endpoint.

The starter server blocks non-GET requests so Codex can inspect store data without changing it.

## Test Locally

From the plugin directory:

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
| python3 scripts/shopify_mcp_server.py
```

With Shopify credentials configured:

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"shopify_get_shop","arguments":{}}}' \
| python3 scripts/shopify_mcp_server.py
```

## Security

- Do not commit Shopify credentials.
- Use the minimum Shopify scopes needed for your use case.
- Treat orders, customers, and revenue data as private store data.
- This starter connector is intentionally read-only.
