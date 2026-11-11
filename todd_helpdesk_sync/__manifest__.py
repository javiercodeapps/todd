{
    'name': "Todd Helpdesk Sync",
    'version': '19.0.1.0.0',
    'depends': ['helpdesk_mgmt', 'queue_job'],
    'author': "Todd",
    'category': 'After-Sales',
    'summary': 'Replica los tickets nuevos en otro servidor Odoo via XML-RPC',
    'license': 'LGPL-3',
    'data': [
        'views/res_config_settings_views.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
    'application': False,
}
