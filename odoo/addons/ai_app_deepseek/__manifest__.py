# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Ask DeepSeek',
    'version': '1.0',
    'website': "https://github.com/cd-feng",
    'summary': """
        Extending ASK AI to support DeepSeek models.""",
    'description': """   """,
    'depends': ['ai_app'],
    'data': [
        'data/ai_agent_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {

    },
    'application': False,
    'author': 'XueFeng.Su',
    "license": "Other proprietary",
    "auto_install": True,
}
