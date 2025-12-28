from odoo import models, fields, api
from odoo.exceptions import UserError
import requests

class TelegramBot(models.Model):
    _name = "telegram.bot"
    _description = "Telegram Bot"

    name = fields.Char(required=True)
    token = fields.Char(required=True)
    active = fields.Boolean(default=True)
    flow_ids = fields.One2many(
        "telegram.flow",
        "bot_id",
        string="Flows"
    )
    webhook_config_id = fields.Many2one(
        "telegram.webhook",
        string="Webhook Config",
        compute="_compute_webhook_config_id",
        store=True,
        readonly=False
    )

    @api.depends('name')
    def _compute_webhook_config_id(self):
        for bot in self:
            if not bot.id:
                bot.webhook_config_id = False
                continue
            config = self.env['telegram.webhook'].search([('bot_id', '=', bot.id)], limit=1)
            if not config:
                config = self.env['telegram.webhook'].create({'bot_id': bot.id})
            bot.webhook_config_id = config

    def action_set_webhook(self):
        self.ensure_one()
        return self.webhook_config_id.action_set()

    def action_get_webhook_info(self):
        self.ensure_one()
        return self.webhook_config_id.action_get_info()

    def action_delete_webhook(self):
        self.ensure_one()
        result = self.webhook_config_id.action_delete()
        # After deleting, we can also refresh the info to show it's cleared.
        self.action_get_webhook_info()
        return { # Return a notification
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Webhook Deleted",
                "message": "The webhook was successfully deleted.",
                "type": "success",
                "sticky": False,
            },
        }
