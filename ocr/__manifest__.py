{
    'name': 'OCR Base',
    'version': '1.0',
    'summary': 'Base OCR Module & Tools',
    'description': 'Provides a generic OCR App with persistent document history and a GPU-accelerated Arabic OCR API.',
    'category': 'Tools',
    'author': 'Antigravity',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/ocr_menus.xml',
        'views/ocr_document_views.xml',
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'ocr/static/src/css/ocr_field.css',
            'ocr/static/src/xml/ocr_field.xml',
            'ocr/static/src/js/ocr_field.js',
        ],
    },
    'license': 'LGPL-3',
}
