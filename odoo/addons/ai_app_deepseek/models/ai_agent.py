# -*- coding: utf-8 -*-
from odoo import _, api, Command, fields, models
from odoo.tools.misc import mute_logger, submap
from odoo.tools import file_open, html_sanitize, SQL, is_html_empty, ormcache


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    def _build_extra_system_context(self, discuss_channel):
        """
            The original method <_build_extra_system_context> fixed this value <ai.ai_agent_natural_language_search> directly,
             which makes it difficult to extend.
        """
        self.ensure_one()
        if self.llm_model in ['deepseek-chat', 'deepseek-reasoner']:
            extra_context = []
            topic_xml_ids = self.topic_ids.get_external_id().values()
            if any(topic in ["ai.ai_topic_natural_language_query", "ai.ai_topic_information_retrieval_query"] for topic in topic_xml_ids):
                extra_context.append(self._get_available_models())
            if self.get_external_id()[self.id] == "ai_app_deepseek.ai_agent_natural_language_search":
                extra_context.append(self._get_available_menus())
                extra_context.append(self._get_date_calculation_reference())
            elif env_context := discuss_channel.ai_env_context:
                extra_context += env_context
            return "\n".join(extra_context) if extra_context else ""
        else:
            return super()._build_extra_system_context(discuss_channel)

    def _create_ai_chat_channel(self, channel_name=None):
        guest = self.env["mail.guest"]._get_guest_from_context()
        with mute_logger("odoo.sql_db"):
            # self.env.cr.execute(SQL(
            #     "SELECT pg_advisory_xact_lock(%s, %s) NOWAIT;",
            #     guest.id if self.env.user._is_public() else self.env.user.partner_id.id,
            #     self.id
            # ))
            self.env.cr.execute(SQL(
                "SELECT pg_try_advisory_xact_lock(%s, %s);",  # <-- pg_try_advisory_xact_lock
                guest.id if self.env.user._is_public() else self.env.user.partner_id.id,
                self.id
            ))
        channel = self.env['discuss.channel'].sudo().create({
            "ai_agent_id": self.id,
            "channel_member_ids": [
                Command.create({"guest_id": guest.id} if self.env.user._is_public() else {"partner_id": self.env.user.partner_id.id}),
                Command.create({"partner_id": self.partner_id.id}),
            ],
            "channel_type": "ai_chat",
            # sudo() => visitor can set the name of the channel
            "name": channel_name if channel_name else self.partner_id.sudo().name,
        })
        return channel