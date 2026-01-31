# -*- coding: utf-8 -*-

{
    'name': 'Init Connect GPT (OpenAI)',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Connect Odoo 19 with GPT (OpenAI API)',
    'depends': ['base', 'auth_signup', 'product', 'sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/init_connect_gpt_prompt_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'init_connect_gpt/static/src/components/prompt_action/prompt_action.js',
            'init_connect_gpt/static/src/components/prompt_action/prompt_action.xml',
            'init_connect_gpt/static/src/components/prompt_action/prompt_action.scss',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
