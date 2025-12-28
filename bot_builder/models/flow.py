from odoo import models, fields

class TelegramFlow(models.Model):
    _name = "telegram.flow"
    _description = "Telegram Bot Flow"

    name = fields.Char(required=True)
    bot_id = fields.Many2one("telegram.bot", required=True)
    trigger = fields.Char(required=True, help="Message or callback trigger")
    message = fields.Text(required=True)
    keyboard_type = fields.Selection(
        [('inline', 'Inline Keyboard'), ('reply', 'Reply Keyboard')],
        string="Keyboard Type",
        default='inline',
        required=True
    )

    button_ids = fields.One2many(
        "telegram.button",
        "flow_id",
        string="Buttons"
    )
