{
    'name': 'BPMN Widget',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'BPMN 2.0 Web Modeler for Odoo',
    'description': """
BPMN Widget
===========
Embeds a BPMN editor in Odoo forms using bpmn-js.
    """,
    'author': 'Antigravity',
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'views/workflow_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bpmn_widget/static/src/js/bpmn_field.js',
            'bpmn_widget/static/src/xml/bpmn_field.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
