---
name: shopify-store
description: Use when the user wants to chat with connected Shopify store data such as shop profile, orders, products, inventory, or customers through the Shopify MCP server.
---

# Shopify Store

Use the `shopify` MCP tools for read-only questions about the connected store.

## Required Environment

- `SHOPIFY_STORE_DOMAIN`: the shop domain, for example `example.myshopify.com`.
- `SHOPIFY_CLIENT_ID`: the Client ID for a Shopify Dev Dashboard app.
- `SHOPIFY_CLIENT_SECRET`: the Client Secret for a Shopify Dev Dashboard app.
- `SHOPIFY_API_VERSION`: optional; defaults to `2025-10`.

Legacy admin-created custom apps can use `SHOPIFY_ADMIN_ACCESS_TOKEN` instead of client credentials.

## Safety

- Treat store data as private business data.
- Do not reveal access tokens or environment variable values.
- Prefer aggregate summaries before showing raw customer or order details.
- The starter MCP server is read-only; do not claim to update Shopify data.

## Common Workflows

- Use `shopify_get_shop` to confirm the connection and retrieve shop metadata.
- Use `shopify_list_orders` for recent order summaries, revenue checks, fulfillment review, and customer service context.
- Use `shopify_list_products` for product catalogs, inventory, variants, and publishing status.
- Use `shopify_list_customers` when the user asks about customer records.

When a user asks a broad question, fetch a small recent sample first, explain the scope, then ask whether they want a deeper pull.
