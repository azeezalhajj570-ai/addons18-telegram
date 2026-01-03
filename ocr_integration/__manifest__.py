{
    'name': 'OCR Integration',
    'version': '1.0',
    'summary': 'Integrate External OCR API for Invoices',
    'description': 'Allows scanning of invoice attachments using a GPU-accelerated Arabic OCR API.',
    'category': 'Accounting',
    'author': 'Antigravity',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/ocr_test_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
