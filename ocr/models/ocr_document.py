from odoo import models, fields, api, _

class OcrDocument(models.Model):
    _name = 'ocr.document'
    _inherit = 'ocr.mixin'
    _description = 'OCR Document'
    _order = 'create_date desc'

    name = fields.Char(string="Document Name", required=True, default="New Scan")
    file = fields.Binary(string="File", required=True, attachment=True)
    filename = fields.Char(string="Filename")
    mimetype = fields.Char(string="Mime Type", compute='_compute_mimetype', store=True)

    @api.depends('filename', 'file')
    def _compute_mimetype(self):
        for record in self:
            if record.filename:
                # Basic extension check or use mimetypes lib if needed.
                # Odoo's binary fields often store mimetype in attachment, but we need it on the record for the view.
                # Let's rely on simple extension check for the view logic.
                name = record.filename.lower()
                if name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                    record.mimetype = 'image'
                elif name.endswith('.pdf'):
                    record.mimetype = 'pdf'
                else:
                    record.mimetype = 'other'
            else:
                record.mimetype = 'other'
    
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
        Override to force a view reload so the results appear immediately.
        """
        # Call super to perform the scan
        super().action_scan_ocr()
        
        # Return reload action to refresh the form
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
