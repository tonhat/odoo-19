# init_connect_gpt

Connect Odoo 19 with GPT via the OpenAI HTTP API.

## Configure

In Odoo:
- **Settings → General Settings**
- Set:
  - **OpenAI API Key**
  - **OpenAI Base URL** (default `https://api.openai.com`)
  - **OpenAI Model** (default `gpt-4o-mini`)
  - **OpenAI Timeout (s)**
  - **API Token (for React/External Apps)** (Bearer token for `/api/v1/*`)

## REST API for React (JSON + CORS)

These endpoints accept either:
- A logged-in Odoo session (`auth=none` but uses `request.session.uid` if present), or
- A Bearer token header: `Authorization: Bearer <API_TOKEN>`.

Base prefix: `/api/v1`

### Partners

- `GET /api/v1/partners?limit=50&offset=0&q=abc`
- `POST /api/v1/partners` (JSON body)
- `GET /api/v1/partners/<id>`
- `PATCH /api/v1/partners/<id>` (JSON body)
- `DELETE /api/v1/partners/<id>` (archives when `active` exists)

### Products

- `GET /api/v1/products?limit=50&offset=0&q=abc`
- `POST /api/v1/products`
- `GET /api/v1/products/<id>`
- `PATCH /api/v1/products/<id>`
- `DELETE /api/v1/products/<id>` (archives when `active` exists)

### Sale Orders

- `GET /api/v1/sale-orders?limit=50&offset=0&q=SO`
- `POST /api/v1/sale-orders` (supports `order_line: [{product_id, product_uom_qty, price_unit, name, ...}]`)
- `GET /api/v1/sale-orders/<id>?include_lines=true`
- `PATCH /api/v1/sale-orders/<id>`
- `DELETE /api/v1/sale-orders/<id>`
- `GET /api/v1/sale-orders/<id>/lines`

### Sale Order Lines

- `GET /api/v1/sale-order-lines/<id>`
- `PATCH /api/v1/sale-order-lines/<id>`
- `DELETE /api/v1/sale-order-lines/<id>`

### Reports

- `GET /api/v1/reports/revenue-by-partner?date_from=2026-01-01&date_to=2026-01-31&states=sale,done&group_by_currency=1`
  - Returns revenue totals grouped by `partner_id` (and `currency_id` by default)

Example curl:

```bash
curl -s \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8069/api/v1/partners?limit=5
```

## Use in code

Call the service model:

- Model: `init_connect_gpt.service`
- Methods:
  - `chat(messages, **kwargs)`
  - `prompt(prompt, system=None, **kwargs)`

Example:

```python
result = self.env['init_connect_gpt.service'].prompt(
    "Write a short reply.",
    system="You are a helpful assistant."
)
text = result['content']
```
