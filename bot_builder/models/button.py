from odoo import models, fields

class TelegramButton(models.Model):
    _name = "telegram.button"
    _description = "Telegram Button"

    flow_id = fields.Many2one("telegram.flow", required=True)
    text = fields.Char(required=True)
    callback_data = fields.Char(string="Callback Data")
