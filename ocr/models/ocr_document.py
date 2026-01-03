from odoo import models, fields, api, _
import base64
import json
import io
import logging
from PIL import Image, ImageDraw

_logger = logging.getLogger(__name__)

class OcrDocument(models.Model):
    _name = 'ocr.document'
    _inherit = 'ocr.mixin'
    _description = 'OCR Document'
    _order = 'create_date desc'

    name = fields.Char(string="Document Name", required=True, default="New Scan")
    file = fields.Binary(string="File", required=True, attachment=True)
    filename = fields.Char(string="Filename")
    mimetype = fields.Char(string="Mime Type", compute='_compute_mimetype', store=True)
    annotated_file = fields.Binary(string="Annotated Image", attachment=True)

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

    def _draw_boxes(self, image_data, json_data):
        """
        Draw bounding boxes on the image based on OCR results.
        :param image_data: Raw bytes of the image
        :param json_data: JSON object (dict) from OCR API
        :return: Raw bytes of annotated image (JPEG) or None
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            # Ensure safe mode for drawing
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            draw = ImageDraw.Draw(image)
            
            # API Structure: { "pages": [ { "items": [ { "box": [[x,y]..], "text": ".." } ] } ] }
            pages = json_data.get('pages', [])
            for page in pages:
                items = page.get('items', [])
                for item in items:
                    box = item.get('box')
                    if box:
                        # Draw Polygon
                        # box is usually list of lists: [[x,y], [x,y], [x,y], [x,y]]
                        # flattening for polygon if needed, but list of tuples/lists works usually
                        points = [tuple(pt) for pt in box]
                        draw.polygon(points, outline="red", width=3)
        
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=95)
            return output.getvalue()
        except Exception as e:
            _logger.warning(f"Failed to draw boxes: {e}")
            return None

    def action_scan_ocr(self):
        """
        Override to force a view reload so the results appear immediately.
        Also triggers visual overlay generation.
        """
        # Call super to perform the scan
        super().action_scan_ocr()
        
        # Generate Overlay if image
        if self.ocr_json_response and self.mimetype == 'image':
            try:
                data = json.loads(self.ocr_json_response)
                # Decode file
                if self.file:
                    file_data = base64.b64decode(self.file)
                    annotated = self._draw_boxes(file_data, data)
                    if annotated:
                        self.annotated_file = base64.b64encode(annotated)
            except Exception as e:
                _logger.error(f"Error generating visual overlay: {e}")

        # Return reload action to refresh the form
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
