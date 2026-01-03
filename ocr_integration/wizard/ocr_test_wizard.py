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
        We need to create a temporary attachment or just point to the field content.
        Since the mixin expects an attachment record to read 'datas', let's create one on the fly
        or override action_scan_ocr to handle direct binary data.
        
        Actually, simpler: The mixin uses `_get_ocr_attachment`.
        Let's just ensure we have an attachment record for the mixin to usage.
        The `attachment=True` on Binary field automatically creates an ir.attachment.
        We just need to find it.
        """
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', 'file')
        ], limit=1)
        return attachment
