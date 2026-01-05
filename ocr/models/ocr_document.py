from odoo import models, fields, api, _
import base64
import json
import io
import logging
import requests
from PIL import Image, ImageDraw, ImageOps
from odoo.exceptions import UserError

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
    ocr_source_html = fields.Html(string="Source HTML", sanitize=False) # For identical left-side rendering
    ocr_visualization_html = fields.Html(string="Visualization HTML", sanitize=False)  # For interactive overlay


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

    def _generate_interactive_overlay(self, image_data, json_data, include_boxes=True):
        """
        Generate HTML overlay for interactive text selection.
        If include_boxes is False, returns only the image container (for Source View).
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            # Fix Orientation first if needed (keep consistent with server results)
            
            width, height = image.size
            if width == 0 or height == 0: return ""
            
            # Base64 for the image tag
            b64_img = base64.b64encode(image_data).decode('utf-8')
            
            html_parts = []
            
            # Common Style Block (ensure it's present in both to keep DOM weight similar, though mostly for boxes)
            html_parts.append("""
            <style>
                .ocr_container {
                    position: relative; 
                    display: inline-block; 
                    width: 100%; 
                    min-width: 100%;
                    line-height: 0;
                    user-select: none; /* Prevent selecting the image itself */
                }
                .ocr_image {
                    width: 100%; 
                    height: auto; 
                    display: block;
                }
                .ocr_word_box {
                    position: absolute;
                    z-index: 10;
                    cursor: text;
                    box-sizing: border-box;
                    color: transparent;
                    font-size: 14px; 
                    font-family: monospace;
                    overflow: hidden;
                    user-select: text; /* Allow text within box to be selected */
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border: 1px solid rgba(0, 0, 0, 0.0); /* Invisible border usually */
                    transition: border-color 0.1s ease, background-color 0.1s ease;
                }
                .ocr_word_box:hover {
                    background-color: rgba(255, 235, 59, 0.4); /* Yellow tint */
                    border: 1px solid rgba(255, 0, 0, 0.8);
                }
                .ocr_word_box::selection {
                    background: rgba(0, 100, 255, 0.3);
                    color: transparent; 
                }
            </style>
            """)

            # Wrapper
            html_parts.append(f'<div class="ocr_container" style="max-width: {width}px;">')
            html_parts.append(f'<img class="ocr_image" src="data:image/png;base64,{b64_img}" />')
            
            if include_boxes:
                pages = json_data.get('pages', [])
                for page in pages:
                    items = page.get('items', [])
                    for item in items:
                        box = item.get('box')
                        text = item.get('text', '')
                        if box and text:
                            # Box is [[x,y], ...]. 
                            xs = [pt[0] for pt in box]
                            ys = [pt[1] for pt in box]
                            # Simple bounding box
                            min_x = max(0, min(xs))
                            min_y = max(0, min(ys))
                            max_x = min(width, max(xs))
                            max_y = min(height, max(ys))
                            
                            w = max_x - min_x
                            h = max_y - min_y
                            
                            if w <= 0 or h <= 0: continue

                            # Calculate Percentages
                            left_pct = (min_x / width) * 100
                            top_pct = (min_y / height) * 100
                            width_pct = (w / width) * 100
                            height_pct = (h / height) * 100
                            
                            safe_text = text.replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                            
                            style = (
                                f"left: {left_pct:.3f}%; "
                                f"top: {top_pct:.3f}%; "
                                f"width: {width_pct:.3f}%; "
                                f"height: {height_pct:.3f}%; "
                            )
                            
                            html_parts.append(f'<span class="ocr_word_box" style="{style}" title="{safe_text}">{safe_text}</span>')
            
            html_parts.append('</div>')
            return "".join(html_parts)
            
        except Exception as e:
            _logger.warning(f"Interactive overlay generation failed: {e}")
            return ""

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
            
            # Generate Interactive Overlay
            if self.mimetype == 'image':
                try:
                    file_data = base64.b64decode(self.file)
                    
                    # 1. Generate Result (Right Side)
                    overlay_html = self._generate_interactive_overlay(file_data, result, include_boxes=True)
                    
                    # 2. Generate Source (Left Side) - identical container/image but no boxes
                    source_html = self._generate_interactive_overlay(file_data, result, include_boxes=False)
                    
                    self.write({
                        'ocr_visualization_html': overlay_html,
                        'ocr_source_html': source_html
                    })
                        
                except Exception as e:
                     _logger.warning(f"Overlay generation skipped or failed: {e}")
            
        except Exception as e:
            _logger.error(f"OCR Advanced Scan Failed: {e}")
            raise UserError(_(f"OCR Scan Failed: {e}"))
            
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

