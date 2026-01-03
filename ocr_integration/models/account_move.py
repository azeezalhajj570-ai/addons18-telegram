from odoo import models, fields, api, _

class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'ocr.mixin']

    def _parse_ocr_data(self, data):
        """ 
        Specific extraction logic for Invoices (account.move)
        """
        # Example: Try to match Total Amount
        # This is a placeholder for the user's specific extraction needs later
        # text = data.get('text', '')
        # if 'total' in text.lower():
        #     pass
        return super()._parse_ocr_data(data)
