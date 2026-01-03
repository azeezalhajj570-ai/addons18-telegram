{
    'name': 'OCR Integration',
    'version': '1.0',
    'summary': 'Integrate External OCR API with Accounting',
    'description': 'Integration bridge between OCR Base App and Odoo Accounting.',
    'category': 'Accounting',
    'author': 'Antigravity',
    'depends': ['account', 'ocr'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
