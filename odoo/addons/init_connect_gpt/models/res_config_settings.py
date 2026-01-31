# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    init_connect_gpt_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='init_connect_gpt.api_key',
    )
    init_connect_gpt_base_url = fields.Char(
        string='OpenAI Base URL',
        default='https://api.openai.com',
        config_parameter='init_connect_gpt.base_url',
    )
    init_connect_gpt_model = fields.Char(
        string='OpenAI Model',
        default='gpt-4o-mini',
        config_parameter='init_connect_gpt.model',
    )
    init_connect_gpt_timeout = fields.Integer(
        string='OpenAI Timeout (s)',
        default=60,
        config_parameter='init_connect_gpt.timeout',
    )

    init_connect_gpt_api_token = fields.Char(
        string='API Token (for React/External Apps)',
        config_parameter='init_connect_gpt.api_token',
        help='Bearer token used by external apps to call /api/v1/* endpoints.',
    )

    def action_init_connect_gpt_test_connection(self):
        self.ensure_one()
        service = self.env['init_connect_gpt.service']
        try:
            res = service.prompt(
                "Say 'OK' if you can read this.",
                system="You are a connectivity test.",
            )
        except UserError:
            raise
        except Exception as exc:
            raise UserError(_("Test connection failed: %s") % exc) from exc

        content = (res or {}).get('content') or ''
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('GPT Connection'),
                'message': _('Success. Response: %s') % (content[:200] or 'OK'),
                'type': 'success',
                'sticky': False,
            }
        }
