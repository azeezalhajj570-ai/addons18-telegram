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
    
    # Download Fields
    ocr_json_file = fields.Binary(string="JSON Output File", attachment=True)
    ocr_json_filename = fields.Char(string="JSON Filename")

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

    def _generate_interactive_overlay(self, image_data, json_data=None, include_boxes=True):
        """
        Generate HTML overlay for interactive text selection.
        """
        try:
            if json_data is None: json_data = {}
            
            image = Image.open(io.BytesIO(image_data))
            
            # Apply EXIF rotation to ensure PIL dimensions matches Visual dimensions
            image = ImageOps.exif_transpose(image)
            
            width, height = image.size
            if width == 0 or height == 0: return ""
            
            # Save the normalized/rotated image to buffer for display
            # This ensures the browser displays exactly what PIL measured
            out_buffer = io.BytesIO()
            image.save(out_buffer, format='PNG')
            b64_img = base64.b64encode(out_buffer.getvalue()).decode('utf-8')
            
            html_parts = []
            
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
                            
                            # Clean Span - No onclick, no inline JS. Data-text used by Widget.
                            html_parts.append(f'<span class="ocr_word_box" style="{style}" title="{safe_text}" data-text="{safe_text}">{safe_text}</span>')
            
            html_parts.append('</div>')
            return "".join(html_parts)
            
        except Exception as e:
            _logger.warning(f"Interactive overlay generation failed: {e}")
            return ""


    def _normalize_image(self, file_base64):
        """
        Decodes, fixes EXIF orientation, and returns (PNG bytes, Width, Height).
        Returns (None, 0, 0) on failure.
        """
        try:
            raw_data = base64.b64decode(file_base64)
            img = Image.open(io.BytesIO(raw_data))
            img = ImageOps.exif_transpose(img)
            
            out_buffer = io.BytesIO()
            img.save(out_buffer, format='PNG')
            return out_buffer.getvalue(), img.width, img.height
        except Exception as e:
            _logger.warning(f"Image normalization failed: {e}")
            return None, 0, 0

    @api.onchange('file')
    def _onchange_file_preview(self):
        """
        Immediately update the Source HTML preview when a file is selected.
        """
        if self.file and self.mimetype == 'image':
            # Normalize and Generate View (No boxes)
            norm_data, w, h = self._normalize_image(self.file)
            if norm_data:
                self.ocr_source_html = self._generate_interactive_overlay(
                    norm_data, 
                    json_data=None, 
                    include_boxes=False
                )
        else:
            self.ocr_source_html = ""

    def action_scan_ocr(self):
        """
        Generic action to scan the current record's attachment.
        """
        self.ensure_one()
        
        endpoint = self.env['ir.config_parameter'].sudo().get_param('ocr.ocr_api_endpoint')
        if not endpoint:
            endpoint = self.env['ir.config_parameter'].sudo().get_param('ocr.endpoint')

        if not endpoint:
             raise UserError(_("Please configure the OCR API Endpoint in Settings (OCR > Configuration > Settings)."))

        # Normalize Image First
        file_b64_str = ""
        if self.mimetype == 'image':
            norm_bytes, w, h = self._normalize_image(self.file)
            if norm_bytes:
                file_b64_str = base64.b64encode(norm_bytes).decode('utf-8')
            else:
                # Fallback to raw if norm fails
                file_b64_str = self.file.decode('utf-8') if isinstance(self.file, bytes) else self.file
        else:
             file_b64_str = self.file.decode('utf-8') if isinstance(self.file, bytes) else self.file

        try:
            file_type_val = 'pdf' if self.mimetype == 'application/pdf' else 'image'
            
            # Use Layout Detection?
            use_layout_detection = (self.scan_mode == 'document')
            
            payload = {
                "file_base64": file_b64_str,
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

            # JSON File Generation
            json_str = json.dumps(result, indent=2, ensure_ascii=False)
            json_bytes = json_str.encode('utf-8')
            json_b64 = base64.b64encode(json_bytes)

            self.write({
                'ocr_raw_text': md_text,
                'ocr_markdown': md_text,
                'ocr_json_response': json_str,
                'ocr_json_file': json_b64,
                'ocr_json_filename': f"{self.filename or 'ocr_result'}.json",
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

