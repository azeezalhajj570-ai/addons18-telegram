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
    
    # Advanced Options
    scan_mode = fields.Selection([
        ('document', 'Document Parsing'),
        ('element', 'Element-level Recognition')
    ], string="Scan Mode", default='document', required=True)
    
    element_type = fields.Selection([
        ('ocr', 'Text Recognition'),
        ('formula', 'Formula Recognition'),
        ('table', 'Table Recognition'),
        ('chart', 'Chart Recognition')
    ], string="element Type", default='ocr')
    
    use_doc_unwarping = fields.Boolean(string="Enable document unwarping", default=False)
    use_doc_orientation_classify = fields.Boolean(string="Enable orientation classification", default=False)
    use_chart_recognition = fields.Boolean(string="Enable chart parsing", default=False)

    # Output Fields
    ocr_markdown = fields.Text(string="Markdown Source")
    ocr_visualization_html = fields.Html(string="Visualization HTML")  # For future use if server returns HTML


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
        Override to send advanced payload structure matching PaddleOCR-VL.
        Force a view reload so the results appear immediately.
        """
        self.ensure_one()
        endpoint = self.env['ir.config_parameter'].sudo().get_param('ocr.endpoint')
        if not endpoint:
             raise UserError(_("Please configure the OCR API Endpoint."))
             
        if not self.file:
             raise UserError(_("Please upload a file first."))

        try:
            # File Type logic
            file_type_val = 'image'
            if self.mimetype == 'pdf':
                file_type_val = 'pdf'
            
            # Use Layout Detection?
            use_layout_detection = (self.scan_mode == 'document')
            
            payload = {
                "file_base64": self.file.decode('utf-8') if isinstance(self.file, bytes) else self.file,
                "useLayoutDetection": use_layout_detection,
                "fileType": file_type_val,
                "useDocUnwarping": self.use_doc_unwarping,
                "useDocOrientationClassify": self.use_doc_orientation_classify
            }
            
            if not use_layout_detection:
                payload["promptLabel"] = self.element_type
            
            if use_layout_detection and self.use_chart_recognition:
                payload["useChartRecognition"] = True
                
            _logger.info(f"Sending OCR Request to {endpoint} with payload keys: {list(payload.keys())}")
            
            headers = {'Content-Type': 'application/json'}
            response = requests.post(endpoint, json=payload, headers=headers, timeout=600, verify=False)
            response.raise_for_status()
            
            result = response.json()
            
            # Parse Result
            md_text = ""
            res_data = result.get('result', {})
            layout_results = res_data.get('layoutParsingResults', [])
            
            if layout_results:
                page0 = layout_results[0]
                md_obj = page0.get('markdown', {})
                md_text = md_obj.get('text', "")
            
            # Fallback
            if not md_text:
                md_text = result.get('text') or result.get('content') or json.dumps(result, indent=2, ensure_ascii=False)

            self.write({
                'ocr_raw_text': md_text,
                'ocr_markdown': md_text,
                'ocr_json_response': json.dumps(result, indent=2, ensure_ascii=False),
                'ocr_confidence': 1.0
            })
            
            # Generate Overlay?
            # If backend logic allows returning boxes, standard overlay might work.
            # But with advanced layout parsing, structure changes.
            # Let's keep logic simple: try to draw boxes if possible, otherwise skip safely.
            if self.mimetype == 'image':
                try:
                    # Current overlay expects "pages" list derived from result.
                    # If result is complex structure {result: {layoutParsingResults: ...}}
                    # we might need to adapt. For now, catch exception and log.
                    if 'pages' in result:
                         file_data = base64.b64decode(self.file)
                         annotated = self._draw_boxes(file_data, result)
                         if annotated:
                             self.annotated_file = base64.b64encode(annotated)
                except Exception as e:
                    _logger.warning(f"Overlay generation skipped or failed: {e}")
            
        except Exception as e:
            _logger.error(f"OCR Advanced Scan Failed: {e}")
            raise UserError(_(f"OCR Scan Failed: {e}"))

        # Return reload action to refresh the form
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
