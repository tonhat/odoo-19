# -*- coding: utf-8 -*-

import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class InitConnectGPTService(models.AbstractModel):
    _name = 'init_connect_gpt.service'
    _description = 'Init Connect GPT (OpenAI API)'

    def _extract_code_block(self, content):
        if not content:
            return ''
        text = content.strip()
        if "```" not in text:
            return text
        # Extract first fenced code block
        parts = text.split("```")
        if len(parts) >= 3:
            code = parts[1]
            lines = code.splitlines()
            if lines and lines[0].strip().lower().startswith("python"):
                lines = lines[1:]
            return "\n".join(lines).strip()
        return text

    @api.model
    def _xmlrpc_safe(self, value):
        """Convert values to XML-RPC-marshallable types.

        XML-RPC cannot marshal None, so convert None -> False.
        """
        if value is None:
            return False
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [self._xmlrpc_safe(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._xmlrpc_safe(v) for k, v in value.items()}
        # Fallback for non-serializable types
        return str(value)

    @api.model
    def _get_param(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @api.model
    def _get_settings(self):
        api_key = self._get_param('init_connect_gpt.api_key')
        base_url = self._get_param('init_connect_gpt.base_url', 'https://api.openai.com')
        model = self._get_param('init_connect_gpt.model', 'gpt-4o-mini')
        timeout = int(self._get_param('init_connect_gpt.timeout', 60) or 60)
        return api_key, base_url.rstrip('/'), model, timeout

    @api.model
    def chat(self, messages, model=None, temperature=None, timeout=None, include_raw=False, **kwargs):
        """Call OpenAI Chat Completions API.

        :param messages:
            - list of dicts: [{'role': 'system|user|assistant', 'content': '...'}]
            - OR a plain string (treated as a single user message)
        :return: dict (XML-RPC safe): {'content': str, 'raw': dict (optional)}
        """
        api_key, base_url, default_model, default_timeout = self._get_settings()
        if not api_key:
            raise UserError(_("Missing OpenAI API Key. Set it in Settings."))

        if isinstance(messages, str):
            messages = [{'role': 'user', 'content': messages}]
        if not isinstance(messages, list):
            raise UserError(_("Invalid 'messages' argument. Expected a list of messages or a string."))

        payload = {
            'model': model or default_model,
            'messages': messages,
        }
        if temperature is not None:
            payload['temperature'] = temperature
        payload.update(kwargs)

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        request_timeout = timeout if timeout is not None else default_timeout
        url = f"{base_url}/v1/chat/completions"

        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=request_timeout)
        except requests.RequestException as exc:
            _logger.exception("OpenAI request failed")
            raise UserError(_("OpenAI request failed: %s") % exc) from exc

        if resp.status_code >= 400:
            # Avoid leaking API key (not in body); keep error text short.
            text = (resp.text or '').strip()
            raise UserError(_("OpenAI error (%s): %s") % (resp.status_code, text[:1000]))

        data = resp.json()
        content = ''
        try:
            content = data['choices'][0]['message']['content']
        except Exception:
            content = ''

        result = {'content': content}
        if include_raw:
            result['raw'] = data
        return self._xmlrpc_safe(result)

    @api.model
    def prompt(self, prompt, system=None, **kwargs):
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        return self.chat(messages, **kwargs)