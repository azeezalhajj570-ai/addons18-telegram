from odoo import models, fields, api, _
import base64

class OcrTestWizard(models.TransientModel):
    _name = 'ocr.test.wizard'
    _inherit = 'ocr.mixin'
    _description = 'OCR Test Wizard'

    file = fields.Binary(string="File", required=True, attachment=True)
    filename = fields.Char(string="Filename")

    def _get_ocr_attachment(self):
        """
        Override to use the binary field 'file' as the attachment.
        """
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', 'file')
        ], limit=1)
        return attachment
