from odoo import models, fields
from odoo.exceptions import UserError
from datetime import datetime
import requests

class TelegramWebhook(models.Model):
    _name = "telegram.webhook"
    _description = "Telegram Webhook Configuration"

    bot_id = fields.Many2one("telegram.bot", string="Bot", required=True, ondelete="cascade")
    
    _sql_constraints = [
        ('bot_id_uniq', 'unique (bot_id)', 'A bot can only have one webhook configuration.')
    ]

    # === SETTINGS FIELDS ===
    url = fields.Char(
        string="Webhook URL",
        compute="_compute_url",
        store=False
    )
    secret_token = fields.Char(string="Secret Token")
    max_connections = fields.Integer(string="Max Connections", default=40)
    allowed_updates = fields.Char(string="Allowed Updates")
    drop_pending_updates = fields.Boolean(string="Drop Pending Updates")

    # === INFO FIELDS (readonly) ===
    info_url = fields.Char(string="Webhook URL", readonly=True)
    info_has_custom_cert = fields.Boolean(string="Has Custom Certificate", readonly=True)
    info_pending_count = fields.Integer(string="Pending Updates", readonly=True)
    info_max_connections = fields.Integer(string="Max Connections", readonly=True)
    info_last_error_date = fields.Datetime(string="Last Error Date", readonly=True)
    info_last_error = fields.Text(string="Last Error Message", readonly=True)

    def _compute_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        if base_url and base_url.startswith('http://'):
             base_url = base_url.replace('http://', 'https://', 1)

        for webhook in self:
            if webhook.bot_id:
                webhook.url = f"{base_url}/telegram/webhook/{webhook.bot_id.id}"
            else:
                webhook.url = f"{base_url}/telegram/webhook"

    def action_set(self):
        self.ensure_one()
        if not self.bot_id.token:
            raise UserError("Please set the bot token first.")

        params = {"url": self.url}
        if self.max_connections:
            params['max_connections'] = self.max_connections
        if self.secret_token:
            params['secret_token'] = self.secret_token
        if self.allowed_updates:
            # Ensure we don't send an empty list from just whitespace/commas
            allowed = [u.strip() for u in self.allowed_updates.split(',') if u.strip()]
            if allowed:
                params['allowed_updates'] = allowed
        if self.drop_pending_updates:
            params['drop_pending_updates'] = True

        api_url = f"https://api.telegram.org/bot{self.bot_id.token}/setWebhook"
        try:
            response = requests.post(api_url, json=params, timeout=10)
            # Check for a detailed error message from Telegram in the JSON response
            if not response.ok:
                error_info = response.json()
                raise UserError(f"Telegram API Error: {error_info.get('description', 'Unknown error')}\n(Code: {error_info.get('error_code', 'N/A')})")
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Failed to set webhook with Telegram: {e}")

        result = response.json()
        if not result.get("ok"):
            raise UserError(result.get("description", "Telegram API error"))

        # Refresh the info after setting
        self.action_get_info()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Webhook Set",
                "message": "Telegram webhook configured successfully.",
                "type": "success",
                "sticky": False,
            }
        }

    def action_get_info(self):
        self.ensure_one()
        if not self.bot_id.token:
            raise UserError("Please set the bot token first.")

        api_url = f"https://api.telegram.org/bot{self.bot_id.token}/getWebhookInfo"
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Failed to get webhook info from Telegram: {e}")

        result = response.json()
        if not result.get("ok"):
            raise UserError(result.get("description", "Telegram API error"))

        webhook_info = result.get("result", {})
        self.write({
            'info_url': webhook_info.get('url'),
            'info_has_custom_cert': webhook_info.get('has_custom_certificate'),
            'info_pending_count': webhook_info.get('pending_update_count'),
            'info_max_connections': webhook_info.get('max_connections'),
            'info_last_error_date': datetime.fromtimestamp(webhook_info['last_error_date']) if webhook_info.get('last_error_date') else False,
            'info_last_error': webhook_info.get('last_error_message'),
        })
        
        # Return an action to reload the view and show a notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Webhook Info Synced",
                "message": "Successfully fetched the latest webhook information.",
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_delete(self):
        self.ensure_one()
        if not self.bot_id.token:
            raise UserError("Please set the bot token first.")

        api_url = f"https://api.telegram.org/bot{self.bot_id.token}/deleteWebhook"
        try:
            response = requests.post(api_url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Failed to delete webhook: {e}")

        result = response.json()
        if not result.get("ok"):
            raise UserError(result.get("description", "Telegram API error"))

        # Clear the info fields
        self.write({
            'info_url': False,
            'info_has_custom_cert': False,
            'info_pending_count': 0,
            'info_max_connections': False,
            'info_last_error_date': False,
            'info_last_error': False,
        })
        return True