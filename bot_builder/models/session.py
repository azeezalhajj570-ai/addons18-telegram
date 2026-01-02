from odoo import models, fields

class TelegramSession(models.Model):
    _name = "telegram.session"
    _description = "Telegram Interactive Session"

    name = fields.Char(string="Session Name", compute="_compute_name")
    chat_id = fields.Char(required=True, index=True)
    flow_id = fields.Many2one("telegram.flow", required=True, ondelete="cascade")
    current_step = fields.Integer(default=0, help="Index of the mapping being processed")
    collected_values = fields.Text(default="{}", help="JSON string of collected values")
    is_active = fields.Boolean(default=True)

    def _compute_name(self):
        for record in self:
            record.name = f"Session {record.flow_id.name} - {record.chat_id}"
