{
    'name': 'OCR Base',
    'version': '1.0',
    'summary': 'Base OCR Module & Tools',
    'description': 'Provides a generic OCR Mixin and Test Wizard using a GPU-accelerated Arabic OCR API.',
    'category': 'Tools',
    'author': 'Antigravity',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/ocr_menus.xml',
        'views/res_config_settings_views.xml',
        'wizard/ocr_test_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
