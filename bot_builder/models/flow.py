from odoo import models, fields

class TelegramFlow(models.Model):
    _name = "telegram.flow"
    _description = "Telegram Bot Flow"

    name = fields.Char(required=True)
    bot_id = fields.Many2one("telegram.bot", required=True)
    trigger = fields.Char(required=True, help="Message or callback trigger")
    
    action_type = fields.Selection(
        [('text', 'Send Message'), ('query', 'Query Model'), ('create', 'Create Record')],
        default='text',
        required=True,
        string="Action Type"
    )

    # Message is required only if action is text, but we can make it optional or used as header for query
    message = fields.Text(string="Message / Header")

    # Fields for 'query' action
    model_id = fields.Many2one("ir.model", string="Model")
    model_field_id = fields.Many2one(
        "ir.model.fields", 
        string="Field to Display",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['char', 'text', 'selection'])]"
    )
    domain_filter = fields.Char(string="Domain Filter", default="[]", help="Odoo domain to filter records, e.g. [('sale_ok', '=', True)]")
    record_limit = fields.Integer(string="Limit", default=5)

    # Fields for 'create' action
    field_mapping_ids = fields.One2many(
        "telegram.flow.mapping",
        "flow_id",
        string="Field Mappings"
    )

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


