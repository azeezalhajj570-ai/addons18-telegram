from odoo import models, fields, api, _

class OcrDocument(models.Model):
    _name = 'ocr.document'
    _inherit = 'ocr.mixin'
    _description = 'OCR Document'
    _order = 'create_date desc'

    name = fields.Char(string="Document Name", required=True, default="New Scan")
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

    def action_scan_ocr(self):
        """
        Override to mostly just call super, but ensure we save first if needed.
        """
        return super().action_scan_ocr()
