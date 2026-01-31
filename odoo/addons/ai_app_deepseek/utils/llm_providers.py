# -*- coding: utf-8 -*-
from odoo.addons.ai.utils.llm_providers import Provider, PROVIDERS


PROVIDERS.append(
    Provider(
        "deepseek",
        "DeepSeek",
        "deepseek-embedding",
        [
            ("deepseek-chat", "DeepSeek-Chat"),
            ("deepseek-reasoner", "DeepSeek-Reasoner"),
        ],
    ),
)

