from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ocr_api_endpoint = fields.Char(string='OCR API Endpoint', config_parameter='ocr_integration.ocr_api_endpoint', help="URL of the specific OCR endpoint (e.g. http://localhost:8000/ocr_file_upload)")
