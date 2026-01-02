from odoo import models, fields

class TelegramFlowMapping(models.Model):
    _name = "telegram.flow.mapping"
    _description = "Telegram Flow Field Mapping"

    flow_id = fields.Many2one("telegram.flow", required=True, ondelete="cascade")
    model_id = fields.Many2one(related="flow_id.model_id", string="Model")
    field_id = fields.Many2one(
        "ir.model.fields", 
        string="Field",
        domain="[('model_id', '=', model_id)]",
        required=True,
        ondelete="cascade"
    )
    value_type = fields.Selection(
        [('fixed', 'Fixed Value'), ('dynamic', 'From Command'), ('ask', 'Ask User')],
        default='fixed',
        required=True
    )
    fixed_value = fields.Char(string="Fixed Value")
    dynamic_key = fields.Char(string="Command Index", help="e.g. 1 for the first argument after command")
    question = fields.Char(string="Question", help="Question to ask the user if value_type is 'ask'")
    sequence = fields.Integer(string="Sequence", default=10)
