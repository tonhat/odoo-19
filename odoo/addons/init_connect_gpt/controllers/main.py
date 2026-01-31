# -*- coding: utf-8 -*-

import hmac
import json
import logging
import re
from datetime import datetime, time

from odoo import http, _, fields
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.auth_signup.models.res_partner import SignupError

_logger = logging.getLogger(__name__)


class InitConnectGPTController(http.Controller):
    @http.route(
        "/init_connect_gpt/chat",
        type="jsonrpc",
        auth="none",
    )
    def chat(self, prompt=None, system=None, model=None, temperature=None, **_kwargs):
        if not prompt:
            raise UserError(_("Missing 'prompt'."))
        service = request.env["init_connect_gpt.service"].sudo()
        return service.prompt(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
        )

    @http.route(
        "/init_connect_gpt/signup",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
        readonly=False,
    )
    def signup(self, login=None, password=None, name=None, email=None, token=None, **kwargs):

        """Public signup endpoint.

        Expected JSON-RPC params:
          - login (required if email not provided)
          - email (optional; defaults to login)
          - password (required)
          - name (optional)
          - token (optional invitation token)
        """

        # Ensure auth_signup is installed (we rely on its user template + rules).
        module = (
            request.env["ir.module.module"]
            .sudo()
            .search([("name", "=", "auth_signup"), ("state", "=", "installed")], limit=1)
        )
        if not module:
            raise UserError(_("Module 'auth_signup' must be installed to use this endpoint."))

        login = (login or "").strip()
        email = (email or "").strip()
        password = password or ""
        name = (name or "").strip()

        if not password:
            raise UserError(_("Missing 'password'."))

        if not login and email:
            login = email
        if not login:
            raise UserError(_("Missing 'login' (or provide 'email')."))

        if not email:
            email = login

        values = {
            "login": login,
            "password": password,
            "name": name or login,
            "email": email,
        }

        # Allow setting optional safe fields if provided
        for optional_field in ("lang", "tz", "country_id"):
            if optional_field in kwargs and kwargs[optional_field] not in (None, ""):
                values[optional_field] = kwargs[optional_field]

        try:
            created_login, _created_password = request.env["res.users"].sudo().signup(values, token=token)
        except SignupError as e:
            # Business error (e.g. signup not allowed, duplicate login, etc.)
            raise UserError(str(e))

        user = request.env["res.users"].sudo().search([("login", "=", created_login)], limit=1)
        return {
            "ok": True,
            "login": created_login,
            "user_id": user.id or False,
        }


class InitConnectGPTApiController(http.Controller):
    _API_PREFIX = "/api/v1"

    _PARTNER_FIELDS = (
        "name",
        "email",
        "phone",
        "mobile",
        "street",
        "street2",
        "city",
        "zip",
        "state_id",
        "country_id",
        "vat",
        "company_type",
        "is_company",
        "active",
    )
    _PRODUCT_FIELDS = (
        "name",
        "default_code",
        "barcode",
        "type",
        "categ_id",
        "uom_id",
        "uom_po_id",
        "list_price",
        "active",
    )
    _SALE_ORDER_FIELDS = (
        "name",
        "partner_id",
        "date_order",
        "state",
        "amount_untaxed",
        "amount_tax",
        "amount_total",
        "currency_id",
        "company_id",
        "user_id",
        "client_order_ref",
        "note",
        "order_line",
    )
    _SALE_ORDER_LINE_FIELDS = (
        "order_id",
        "product_id",
        "name",
        "product_uom_qty",
        "product_uom",
        "price_unit",
        "discount",
        "tax_id",
        "price_subtotal",
        "price_total",
        "currency_id",
    )

    def _cors_headers(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        }

    def _json_response(self, payload, status=200):
        resp = request.make_json_response(payload, headers=list(self._cors_headers().items()), status=status)
        return resp

    def _json_error(self, code, message, status=400, details=None):
        error = {"code": code, "message": message}
        if details:
            error["details"] = details
        return self._json_response({"ok": False, "error": error}, status=status)

    def _handle(self, fn):
        try:
            return fn()
        except UserError as exc:
            return self._json_error("bad_request", str(exc), status=400)
        except Exception as exc:
            _logger.exception("API error")
            return self._json_error("server_error", "Internal server error", status=500)

    def _options(self):
        resp = request.make_response("", headers=list(self._cors_headers().items()), status=204)
        return resp

    def _get_json_body(self):
        jsonrequest = getattr(request, "jsonrequest", None)
        if jsonrequest is not None:
            return jsonrequest

        # Werkzeug helpers (works for type='http' routes)
        try:
            parsed = request.httprequest.get_json(silent=True)
        except Exception:
            parsed = None
        if parsed is not None:
            return parsed
        data = request.httprequest.data or b""
        if not data:
            return {}
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise UserError(_("Invalid JSON body: %s") % exc) from exc

    def _to_snake_key(self, key):
        key = (key or "").strip()
        if not key:
            return key
        key = key.replace("-", "_").replace(" ", "_")
        key = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", key)
        key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
        return key.lower()

    def _normalize_payload(self, payload):
        if isinstance(payload, list):
            return [self._normalize_payload(v) for v in payload]
        if not isinstance(payload, dict):
            return payload

        normalized = {}
        for k, v in payload.items():
            nk = self._to_snake_key(str(k))
            normalized[nk] = self._normalize_payload(v)
        return normalized

    def _unwrap_payload(self, body, keys):
        """Unwrap common client-side envelopes.

        Many front-ends send `{data: {...}}` or `{payload: {...}}`.
        """
        if not isinstance(body, dict):
            return body
        for key in keys:
            value = body.get(key)
            if isinstance(value, dict):
                return value
        return body

    def _get_bearer_token(self):
        auth = request.httprequest.headers.get("Authorization") or ""
        match = re.match(r"^Bearer\s+(.+)$", auth.strip(), flags=re.IGNORECASE)
        return (match.group(1) if match else "").strip()

    def _api_env(self):
        """Return an env for API access.

        - If a user session exists, use that user.
        - Otherwise require a Bearer token (single system token) and use sudo.
        """

        if request.session.uid:
            return request.env(user=request.session.uid)

        expected = request.env["ir.config_parameter"].sudo().get_param("init_connect_gpt.api_token") or ""
        expected = expected.strip()
        if not expected:
            raise UserError(_("API token is not configured. Set it in Settings."))

        provided = self._get_bearer_token()
        if not provided or not hmac.compare_digest(provided, expected):
            return self._json_response(
                {"ok": False, "error": {"code": "unauthorized", "message": "Missing/invalid API token"}},
                status=401,
            )
        return request.env.sudo()

    def _serialize_record(self, record, field_names):
        data = {"id": record.id, "display_name": record.display_name}
        for name in field_names:
            if name not in record._fields:
                continue
            field = record._fields[name]
            value = record[name]
            if field.type == "many2one":
                data[name] = value.id if value else False
                data[f"{name}_display_name"] = value.display_name if value else False
            elif field.type in ("one2many", "many2many"):
                data[name] = value.ids
            else:
                data[name] = value
        return data

    def _parse_pagination(self):
        args = request.httprequest.args
        try:
            limit = int(args.get("limit", 50))
            offset = int(args.get("offset", 0))
        except ValueError:
            raise UserError(_("Invalid limit/offset"))
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return limit, offset

    def _parse_date_range(self):
        """Parse date_from/date_to (YYYY-MM-DD) from query params.

        Returns a domain fragment on sale.order.date_order.
        """
        args = request.httprequest.args
        date_from = (args.get("date_from") or "").strip()
        date_to = (args.get("date_to") or "").strip()

        domain = []
        if date_from:
            try:
                dt_from = datetime.combine(datetime.strptime(date_from, "%Y-%m-%d").date(), time.min)
            except ValueError:
                raise UserError(_("Invalid date_from. Expected YYYY-MM-DD"))
            domain.append(("date_order", ">=", fields.Datetime.to_string(dt_from)))

        if date_to:
            try:
                dt_to = datetime.combine(datetime.strptime(date_to, "%Y-%m-%d").date(), time.max)
            except ValueError:
                raise UserError(_("Invalid date_to. Expected YYYY-MM-DD"))
            domain.append(("date_order", "<=", fields.Datetime.to_string(dt_to)))

        return domain

    def _list(self, env, model_name, domain, fields, order=None):
        limit, offset = self._parse_pagination()
        recs = env[model_name].search(domain, limit=limit, offset=offset, order=order)
        total = env[model_name].search_count(domain)
        return {
            "ok": True,
            "result": {
                "total": total,
                "offset": offset,
                "limit": limit,
                "items": [self._serialize_record(r, fields) for r in recs],
            },
        }

    @http.route(
        f"{_API_PREFIX}/reports/revenue-by-partner",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["POST", "GET", "OPTIONS"],
    )
    def api_report_revenue_by_partner(self, **_kw):
        """Revenue summary by partner based on sale orders.

        Query params:
          - date_from=YYYY-MM-DD (optional)
          - date_to=YYYY-MM-DD (optional)
          - states=sale,done (optional; default: sale,done)
          - company_id=<id> (optional)
          - group_by_currency=1|0 (optional; default 1)
          - limit, offset
        """
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            args = request.httprequest.args

            states_raw = (args.get("states") or "sale,done").strip()
            states = [s.strip() for s in states_raw.split(",") if s.strip()]
            domain = [("state", "in", states)]
            domain += self._parse_date_range()

            company_id = (args.get("company_id") or "").strip()
            if company_id:
                try:
                    company_id_int = int(company_id)
                except ValueError:
                    raise UserError(_("Invalid company_id"))
                domain.append(("company_id", "=", company_id_int))

            group_by_currency = (args.get("group_by_currency") or "1").strip().lower() not in ("0", "false", "no")

            groupby = ["partner_id"]
            if group_by_currency:
                groupby.append("currency_id")

            agg_fields = [
                "amount_total:sum",
                "amount_untaxed:sum",
                "amount_tax:sum",
                "__count",
            ]

            limit, offset = self._parse_pagination()
            groups = env["sale.order"].read_group(
                domain,
                agg_fields,
                groupby,
                offset=offset,
                limit=limit,
                orderby="amount_total desc",
                lazy=False,
            )

            # Total groups count for pagination: read_group doesn't provide it, so approximate with full grouping.
            # For typical dashboards this is OK; if you need exact + fast on huge DB, we can switch to SQL.
            total_groups = len(env["sale.order"].read_group(domain, ["__count"], groupby, lazy=False))

            items = []
            for g in groups:
                partner = g.get("partner_id")
                currency = g.get("currency_id")
                items.append(
                    {
                        "partner_id": partner[0] if isinstance(partner, (list, tuple)) and partner else False,
                        "partner_name": partner[1] if isinstance(partner, (list, tuple)) and partner else False,
                        "currency_id": currency[0] if isinstance(currency, (list, tuple)) and currency else False,
                        "currency_name": currency[1] if isinstance(currency, (list, tuple)) and currency else False,
                        "order_count": g.get("__count", 0),
                        "amount_untaxed_sum": g.get("amount_untaxed", 0.0),
                        "amount_tax_sum": g.get("amount_tax", 0.0),
                        "amount_total_sum": g.get("amount_total", 0.0),
                    }
                )

            return self._json_response(
                {
                    "ok": True,
                    "result": {
                        "total": total_groups,
                        "offset": offset,
                        "limit": limit,
                        "items": items,
                        "filters": {
                            "states": states,
                            "date_from": (args.get("date_from") or "") or False,
                            "date_to": (args.get("date_to") or "") or False,
                            "company_id": int(company_id) if company_id else False,
                            "group_by_currency": group_by_currency,
                        },
                    },
                }
            )

        return self._handle(_impl)

    # Partners
    @http.route(
        f"{_API_PREFIX}/partners",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "POST", "OPTIONS"],
    )
    def api_partners(self, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            if request.httprequest.method == "GET":
                q = (request.httprequest.args.get("q") or "").strip()
                domain = []
                if q:
                    domain = ["|", "|", ("name", "ilike", q), ("email", "ilike", q), ("phone", "ilike", q)]
                return self._json_response(self._list(env, "res.partner", domain, self._PARTNER_FIELDS, order="id desc"))

            body = self._normalize_payload(self._get_json_body() or {})
            body = self._unwrap_payload(body, keys=("data", "payload", "partner"))
            allowed = {k: v for k, v in body.items() if k in self._PARTNER_FIELDS and k != "active"}
            if not allowed.get("name"):
                return self._json_error("missing_field", "Missing required field: name", status=400)
            partner = env["res.partner"].create(allowed)
            return self._json_response({"ok": True, "result": self._serialize_record(partner, self._PARTNER_FIELDS)}, status=201)

        return self._handle(_impl)

    @http.route(
        f"{_API_PREFIX}/partners/<int:partner_id>",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "PATCH", "DELETE", "OPTIONS"],
    )
    def api_partner(self, partner_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            partner = env["res.partner"].browse(int(partner_id)).exists()
            if not partner:
                return self._json_error("not_found", "Partner not found", status=404)

            if request.httprequest.method == "GET":
                return self._json_response({"ok": True, "result": self._serialize_record(partner, self._PARTNER_FIELDS)})

            if request.httprequest.method == "PATCH":
                body = self._normalize_payload(self._get_json_body() or {})
                body = self._unwrap_payload(body, keys=("data", "payload", "partner"))
                vals = {k: v for k, v in body.items() if k in self._PARTNER_FIELDS and k != "active"}
                partner.write(vals)
                return self._json_response({"ok": True, "result": self._serialize_record(partner, self._PARTNER_FIELDS)})

            # DELETE
            if "active" in partner._fields:
                partner.write({"active": False})
            else:
                partner.unlink()
            return self._json_response({"ok": True, "result": True})

        return self._handle(_impl)

    # Products
    @http.route(
        f"{_API_PREFIX}/products",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "POST", "OPTIONS"],
    )
    def api_products(self, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            if request.httprequest.method == "GET":
                q = (request.httprequest.args.get("q") or "").strip()
                domain = []
                if q:
                    domain = ["|", "|", ("name", "ilike", q), ("default_code", "ilike", q), ("barcode", "ilike", q)]
                return self._json_response(self._list(env, "product.product", domain, self._PRODUCT_FIELDS, order="id desc"))

            body = self._normalize_payload(self._get_json_body() or {})
            body = self._unwrap_payload(body, keys=("data", "payload", "product"))
            allowed = {k: v for k, v in body.items() if k in self._PRODUCT_FIELDS and k != "active"}
            if not allowed.get("name"):
                return self._json_error("missing_field", "Missing required field: name", status=400)
            product = env["product.product"].create(allowed)
            return self._json_response({"ok": True, "result": self._serialize_record(product, self._PRODUCT_FIELDS)}, status=201)

        return self._handle(_impl)

    @http.route(
        f"{_API_PREFIX}/products/<int:product_id>",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "PATCH", "DELETE", "OPTIONS"],
    )
    def api_product(self, product_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            product = env["product.product"].browse(int(product_id)).exists()
            if not product:
                return self._json_error("not_found", "Product not found", status=404)

            if request.httprequest.method == "GET":
                return self._json_response({"ok": True, "result": self._serialize_record(product, self._PRODUCT_FIELDS)})

            if request.httprequest.method == "PATCH":
                body = self._normalize_payload(self._get_json_body() or {})
                body = self._unwrap_payload(body, keys=("data", "payload", "product"))
                vals = {k: v for k, v in body.items() if k in self._PRODUCT_FIELDS and k != "active"}
                product.write(vals)
                return self._json_response({"ok": True, "result": self._serialize_record(product, self._PRODUCT_FIELDS)})

            if "active" in product._fields:
                product.write({"active": False})
            else:
                product.unlink()
            return self._json_response({"ok": True, "result": True})

        return self._handle(_impl)

    # Sale Orders
    @http.route(
        f"{_API_PREFIX}/sale-orders",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "POST", "OPTIONS"],
    )
    def api_sale_orders(self, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            if request.httprequest.method == "GET":
                q = (request.httprequest.args.get("q") or "").strip()
                domain = []
                if q:
                    domain = ["|", ("name", "ilike", q), ("client_order_ref", "ilike", q)]
                return self._json_response(self._list(env, "sale.order", domain, self._SALE_ORDER_FIELDS, order="id desc"))

            body = self._normalize_payload(self._get_json_body() or {})
            body = self._unwrap_payload(body, keys=("data", "payload", "order", "sale_order"))
            vals = {k: v for k, v in body.items() if k in ("partner_id", "date_order", "client_order_ref", "note", "user_id", "company_id")}
            lines = body.get("order_line")
            if isinstance(lines, list):
                commands = []
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    line = self._normalize_payload(line)
                    line = self._unwrap_payload(line, keys=("data", "payload", "line"))
                    line_vals = {k: v for k, v in line.items() if k in ("product_id", "name", "product_uom_qty", "price_unit", "discount", "tax_id", "product_uom")}
                    if "tax_id" in line_vals and isinstance(line_vals["tax_id"], list):
                        line_vals["tax_id"] = [(6, 0, line_vals["tax_id"]) ]
                    commands.append((0, 0, line_vals))
                vals["order_line"] = commands

            if not vals.get("partner_id"):
                return self._json_error("missing_field", "Missing required field: partner_id", status=400)

            order = env["sale.order"].create(vals)
            result = self._serialize_record(order, self._SALE_ORDER_FIELDS)
            result["order_line_ids"] = order.order_line.ids
            return self._json_response({"ok": True, "result": result}, status=201)

        return self._handle(_impl)

    @http.route(
        f"{_API_PREFIX}/sale-orders/<int:order_id>",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "PATCH", "DELETE", "OPTIONS"],
    )
    def api_sale_order(self, order_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            order = env["sale.order"].browse(int(order_id)).exists()
            if not order:
                return self._json_error("not_found", "Sale order not found", status=404)

            if request.httprequest.method == "GET":
                include_lines = (request.httprequest.args.get("include_lines") or "").lower() in ("1", "true", "yes")
                result = self._serialize_record(order, self._SALE_ORDER_FIELDS)
                result["order_line_ids"] = order.order_line.ids
                if include_lines:
                    result["lines"] = [self._serialize_record(l, self._SALE_ORDER_LINE_FIELDS) for l in order.order_line]
                return self._json_response({"ok": True, "result": result})

            if request.httprequest.method == "PATCH":
                body = self._normalize_payload(self._get_json_body() or {})
                body = self._unwrap_payload(body, keys=("data", "payload", "order", "sale_order"))
                vals = {k: v for k, v in body.items() if k in ("partner_id", "date_order", "client_order_ref", "note", "user_id")}
                order.write(vals)
                result = self._serialize_record(order, self._SALE_ORDER_FIELDS)
                result["order_line_ids"] = order.order_line.ids
                return self._json_response({"ok": True, "result": result})

            # DELETE
            if "active" in order._fields:
                order.write({"active": False})
            else:
                order.unlink()
            return self._json_response({"ok": True, "result": True})

        return self._handle(_impl)

    @http.route(
        f"{_API_PREFIX}/sale-orders/<int:order_id>/lines",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "OPTIONS"],
    )
    def api_sale_order_lines_by_order(self, order_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            order = env["sale.order"].browse(int(order_id)).exists()
            if not order:
                return self._json_error("not_found", "Sale order not found", status=404)
            lines = order.order_line
            return self._json_response({"ok": True, "result": {"items": [self._serialize_record(l, self._SALE_ORDER_LINE_FIELDS) for l in lines]}})

        return self._handle(_impl)

    # Sale Order Lines (direct)
    @http.route(
        f"{_API_PREFIX}/sale-order-lines/<int:line_id>",
        type="http",
        auth="none",
        csrf=False,
        cors="*",
        methods=["GET", "PATCH", "DELETE", "OPTIONS"],
    )
    def api_sale_order_line(self, line_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return self._options()

        def _impl():
            env = self._api_env()
            if not hasattr(env, "registry"):
                return env

            line = env["sale.order.line"].browse(int(line_id)).exists()
            if not line:
                return self._json_error("not_found", "Sale order line not found", status=404)

            if request.httprequest.method == "GET":
                return self._json_response({"ok": True, "result": self._serialize_record(line, self._SALE_ORDER_LINE_FIELDS)})

            if request.httprequest.method == "PATCH":
                body = self._normalize_payload(self._get_json_body() or {})
                body = self._unwrap_payload(body, keys=("data", "payload", "line"))
                vals = {k: v for k, v in body.items() if k in ("name", "product_uom_qty", "price_unit", "discount")}
                line.write(vals)
                return self._json_response({"ok": True, "result": self._serialize_record(line, self._SALE_ORDER_LINE_FIELDS)})

            line.unlink()
            return self._json_response({"ok": True, "result": True})

        return self._handle(_impl)

