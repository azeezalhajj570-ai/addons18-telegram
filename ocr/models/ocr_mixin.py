from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import base64
import json
import logging

_logger = logging.getLogger(__name__)

class OcrMixin(models.AbstractModel):
    _name = 'ocr.mixin'
    _description = 'OCR Mixin'

    ocr_raw_text = fields.Text(string="OCR Raw Text", copy=False)
    ocr_json_response = fields.Text(string="OCR JSON Response", copy=False)
    ocr_confidence = fields.Float(string="OCR Confidence", copy=False, help="Average confidence score from the OCR engine")

    def _get_ocr_attachment(self):
        """
        Hook to retrieve the attachment to scan.
        Should return an `ir.attachment` record.
        """
        # Default behavior: Search for the first PDF/Image attached to the record
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('mimetype', 'in', ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'])
        ], order='create_date desc', limit=1)
        
        if not attachment and hasattr(self, 'message_main_attachment_id'):
             # Fallback to mail fallback
             attachment = self.message_main_attachment_id
             
        return attachment

    def action_scan_ocr(self):
        """
        Generic action to scan the current record's attachment.
        """
        self.ensure_one()
        
        endpoint = self.env['ir.config_parameter'].sudo().get_param('ocr.ocr_api_endpoint')
        if not endpoint:
            # Fallback to old param name during migration if needed, but let's stick to new one or keep old one?
            # Let's keep 'ocr_integration.ocr_api_endpoint' for compatibility or rename to 'ocr.ocr_api_endpoint'?
            # Better to rename to `ocr.endpoint` but let's keep it simple and reuse the old key or update.
            # I will update the key to 'ocr.endpoint' in the new module settings.
            endpoint = self.env['ir.config_parameter'].sudo().get_param('ocr.endpoint')

        if not endpoint:
             raise UserError(_("Please configure the OCR API Endpoint in Settings (OCR > Configuration > Settings)."))

        attachment = self._get_ocr_attachment()
        
        if not attachment:
            raise UserError(_("No suitable attachment (PDF/Image) found to scan."))

        try:
            file_content = base64.b64decode(attachment.datas)
            files = {
                'file': (
                    attachment.name or "document", 
                    file_content, 
                    attachment.mimetype or "application/octet-stream"
                )
            }
            
            _logger.info(f"Sending attachment {attachment.id} from {self._name} to OCR Endpoint: {endpoint}")
            # verify=False for local dev/self-signed certs
            response = requests.post(endpoint, files=files, timeout=60, verify=False) 
            response.raise_for_status()
            
            result = response.json()
            
            # Helper to get text regardless of API response structure
            text_result = ""
            pages = result.get('pages', [])
            all_text_lines = []
            
            # Helper to extract text from pages/items structure
            if pages:
                for page in pages:
                     items = page.get('items', [])
                     for item in items:
                         if isinstance(item, dict) and item.get('text'):
                             all_text_lines.append(item.get('text'))
                text_result = "\n".join(all_text_lines)
            
            # Fallback
            if not text_result:
                text_result = result.get('text') or result.get('content') or str(result)
            
            self.write({
                'ocr_raw_text': text_result,
                'ocr_json_response': json.dumps(result, indent=2, ensure_ascii=False),
                'ocr_confidence': result.get('confidence', 0.0)
            })

            # Call parsing hook
            self._parse_ocr_data(result)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('OCR Scan Complete'),
                    'message': _('Document scanned successfully.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            try:
                # Try to parse JSON error from server (FastAPI returns 'detail')
                error_data = e.response.json()
                if 'detail' in error_data: 
                    error_msg = error_data['detail']
            except:
                # Fallback to text if JSON fails
                error_msg = e.response.text or str(e)
            
            _logger.error(f"OCR Server Error: {error_msg}")
            raise UserError(_("OCR Server Error: %s") % error_msg)

        except Exception as e:
            _logger.error(f"OCR Scan Failed: {e}")
            raise UserError(_(f"OCR Scan Failed: {e}"))

    def _parse_ocr_data(self, data):
        """
        Hook for models to implement specific field extraction.
        :param data: JSON Dict returned from API
        """
        pass
