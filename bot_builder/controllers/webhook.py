import logging
import requests
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class TelegramWebhook(http.Controller):

    @http.route("/telegram/webhook/<int:bot_id>", type="json", auth="public", csrf=False)
    def telegram_webhook(self, bot_id):
        data = request.httprequest.get_json()
        _logger.info("Received webhook data: %s", data)

        bot = request.env["telegram.bot"].sudo().search([
            ("id", "=", bot_id),
            ("active", "=", True),
        ], limit=1)

        if not bot:
            _logger.warning("No active bot found to handle webhook.")
            return {"error": "No active bot"}

        chat_id = None
        trigger = None

        # --- MESSAGE HANDLING ---
        if data.get("message"):
            chat_id = data["message"]["chat"]["id"]
            trigger = data["message"].get("text")
            _logger.info(
                "Processing message from chat_id %s with trigger '%s'",
                chat_id, trigger
            )

        # --- CALLBACK HANDLING (BUTTON CLICK) ---
        if data.get("callback_query"):
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            trigger = callback["data"]
            callback_id = callback["id"]

            _logger.info(
                "Processing callback_query from chat_id %s with trigger '%s'",
                chat_id, trigger
            )

            # 🔥 REQUIRED: acknowledge the button click
            self.answer_callback(bot.token, callback_id)

        if not trigger:
            _logger.info("No trigger found in the payload. Acknowledging request.")
            return {"ok": True}

        flow = request.env["telegram.flow"].sudo().search([
            ("bot_id", "=", bot.id),
            ("trigger", "=", trigger)
        ], limit=1)

        if flow:
            _logger.info("Found flow '%s' for trigger '%s'.", flow.name, trigger)
            self.send_message(bot.token, chat_id, flow)
        else:
            _logger.info("No flow found for trigger '%s'.", trigger)

        return {"ok": True}

    # --- SEND MESSAGE WITH INLINE BUTTONS ---
    def send_message(self, token, chat_id, flow):
        reply_markup = None
        if flow.keyboard_type == 'inline':
            keyboard = []
            for btn in flow.button_ids:
                keyboard.append([{
                    "text": btn.text,
                    "callback_data": btn.callback_data
                }])
            if keyboard:
                reply_markup = {"inline_keyboard": keyboard}

        elif flow.keyboard_type == 'reply':
            keyboard = []
            row = []
            for btn in flow.button_ids:
                row.append({"text": btn.text})
                # Max 2 buttons per row for better layout, or customizable?
                # For now, let's just make it a grid or single column?
                # Let's do 2 per row logic or just simple 1 per row for now.
                # Actually, standard grid is often preferred. Let's do 2 per row.
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            if keyboard:
                reply_markup = {
                    "keyboard": keyboard,
                    "resize_keyboard": True,
                    "one_time_keyboard": False
                }

        payload = {
            "chat_id": chat_id,
            "text": flow.message,
            "reply_markup": reply_markup
        }

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10
        )

    # --- REQUIRED FOR INLINE BUTTONS ---
    def answer_callback(self, token, callback_id):
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id
            },
            timeout=5
        )
