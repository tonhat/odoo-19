# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    deepseek_key_enabled = fields.Boolean(
        string="Enable Custom DeepSeek API Key",
        compute='_compute_deepseek_key_enabled',
        readonly=False,
        groups='base.group_system',
    )
    deepseek_key = fields.Char(
        string="DeepSeek API key",
        config_parameter='ai.deepseek_key',
        readonly=False,
        groups='base.group_system',
    )

    def _compute_deepseek_key_enabled(self):
        for record in self:
            record.deepseek_key_enabled = bool(record.deepseek_key)

