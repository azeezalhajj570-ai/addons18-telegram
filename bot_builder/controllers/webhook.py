import logging
import requests
import json
from odoo import http
from odoo.http import request
from odoo.tools.safe_eval import safe_eval

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

        # --- CHECK FOR ACTIVE SESSION ---
        session = request.env["telegram.session"].sudo().search([
            ("chat_id", "=", chat_id),
            ("is_active", "=", True)
        ], limit=1)

        if session:
            # Check if user wants to cancel
            if trigger.lower() in ['/cancel', 'cancel']:
                session.sudo().write({'is_active': False})
                self.send_message(bot.token, chat_id, session.flow_id, final_text="(Session Cancelled)")
                return {"ok": True}
            
            return self._handle_session_input(bot, chat_id, session, trigger)

        flow = request.env["telegram.flow"].sudo().search([
            ("bot_id", "=", bot.id)
        ])
        
        # Simple split matching for commands with arguments
        matched_flow = None
        for f in flow:
            if trigger == f.trigger:
                matched_flow = f
                break
            if f.trigger.startswith("/") and trigger.startswith(f.trigger + " "):
                matched_flow = f
                break
        
        if matched_flow:
            flow = matched_flow
            _logger.info("Found flow '%s' for trigger '%s'.", flow.name, trigger)
            
            final_text = flow.message or ""
            _logger.info("Flow Debug - Action: %s, Model: %s", flow.action_type, flow.model_id)
            
            if flow.action_type == 'query' and flow.model_id:
                try:
                    domain = safe_eval(flow.domain_filter or "[]")
                    records = request.env[flow.model_id.model].sudo().search(domain, limit=flow.record_limit)
                    field_name = flow.model_field_id.name
                    
                    items = []
                    for record in records:
                        val = record[field_name]
                        if val:
                             items.append(str(val))
                    
                    if items:
                        final_text += "\n" + "\n".join(items)
                    else:
                        final_text += "\n(No records found)"
                except Exception as e:
                    _logger.error("Error executing query for flow %s: %s", flow.name, e)
                    final_text += "\n(Error fetching data)"

            elif flow.action_type == 'create' and flow.model_id:
                # Check if we need to ask questions
                ask_mappings = flow.field_mapping_ids.filtered(lambda m: m.value_type == 'ask').sorted(key=lambda m: m.sequence)
                _logger.info("Found %d ask_mappings for flow %s. Mappings: %s", len(ask_mappings), flow.name, ask_mappings)
                
                if ask_mappings:
                    # START SESSION
                    try:
                        first_question = ask_mappings[0].question or f"Please provide {ask_mappings[0].field_id.name}"
                        _logger.info("Starting session with question: %s", first_question)
                        request.env["telegram.session"].sudo().create({
                            'chat_id': chat_id,
                            'flow_id': flow.id,
                            'current_step': 0,
                            'collected_values': '{}'
                        })
                        # Send first question
                        self.send_message(bot.token, chat_id, flow, final_text=first_question)
                        return {"ok": True}
                    except Exception as e:
                        _logger.error("Error starting session: %s", e)
                        final_text += "\n(Error starting interactive session)"

                else:
                    _logger.info("No ask_mappings found. Proceeding with one-shot creation.")
                    try:
                        vals = {}
                        
                        # Split trigger arguments: "/expense 100 Lunch" -> ["/expense", "100", "Lunch"]
                        parts = trigger.split()
                        
                        # Try to set employee_id for expenses automatically
                        if flow.model_id.model == 'hr.expense':
                             employee = self._get_employee(bot, chat_id)
                             if employee:
                                 vals['employee_id'] = employee.id
                        
                        for mapping in flow.field_mapping_ids:
                            if mapping.value_type == 'fixed':
                                vals[mapping.field_id.name] = mapping.fixed_value
                            elif mapping.value_type == 'dynamic' and mapping.dynamic_key:
                                try:
                                    idx = int(mapping.dynamic_key)
                                    if idx < len(parts):
                                        vals[mapping.field_id.name] = parts[idx]
                                except (ValueError, IndexError):
                                    _logger.warning("Invalid dynamic key or index out of range: %s", mapping.dynamic_key)

                        # Ensure 'name' (Description) is present for hr.expense
                        if flow.model_id.model == 'hr.expense' and 'name' not in vals:
                            vals['name'] = "Expense via Bot"

                        # Basic Validation for required fields
                        if not vals:
                             _logger.warning("No data provided for creation. Vals is empty.")
                             final_text += "\n(Error: No data provided for creation)"
                        else:
                            request.env[flow.model_id.model].sudo().create(vals)
                            final_text += "\n(Record Created Successfully)"
                    except Exception as e:
                        # IMPORTANT: Rollback to avoid transaction break issues when logging/sending response
                        request.env.cr.rollback()
                        _logger.error("Error creating record for flow %s: %s", flow.name, e)
                        final_text += f"\n(Error creating record: {e})"

            self.send_message(bot.token, chat_id, flow, final_text=final_text)
        else:
            _logger.info("No flow found for trigger '%s'.", trigger)

        return {"ok": True}

    # --- SEND MESSAGE WITH INLINE BUTTONS ---
    def send_message(self, token, chat_id, flow, final_text=None):
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
            "text": final_text or flow.message,
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

    def _handle_session_input(self, bot, chat_id, session, text):
        try:
            mappings = session.flow_id.field_mapping_ids.filtered(lambda m: m.value_type == 'ask').sorted(key=lambda m: m.sequence)
            
            if session.current_step < len(mappings):
                current_mapping = mappings[session.current_step]
                
                # Store value
                values = json.loads(session.collected_values or "{}")
                values[current_mapping.field_id.name] = text
                
                session.sudo().write({
                    'collected_values': json.dumps(values),
                    'current_step': session.current_step + 1
                })
                
                # Check if there is next step
                if session.current_step + 1 <= len(mappings):
                    # We just incremented, so `current_step` points to NEXT one
                    # Oops, I incremented `current_step` in write. So now `session.current_step` is the next one.
                    # Wait, `session` object in memory might not be updated immediately unless I re-browse or just use math.
                    # Let's use math.
                    
                    next_step_index = session.current_step # This is already incremented in DB? 
                    # If I didn't re-browse, `session.current_step` is still old val?
                    # No, write() doesn't update the recordset in memory usually, unless we rely on cache invalidation.
                    # Safest is to use local variable.
                    
                    next_step_index = values.get('__current_step_local__', 0) + 1 # nah
                    # Let's just trust re-reading or manual calculation.
                    next_step = session.current_step # This is the OLD value if not refreshed.
                    # Actually, let's just use the index logic:
                    
                    # session.current_step was X. We processed X.
                    # New step is X+1.
                    next_mapping_index = session.current_step # old value?
                    
                    # Use a fresh calculation
                    next_idx = len(values) # unique keys collected
                    # Or just rely on what we just wrote.
                    
                    if next_idx < len(mappings):
                         next_mapping = mappings[next_idx]
                         self.send_message(bot.token, chat_id, session.flow_id, final_text=next_mapping.question or f"Please provide {next_mapping.field_id.name}")
                         return {"ok": True}
            
            # All steps done, finalize
            return self._finalize_create_action(bot, chat_id, session)
            
        except Exception as e:
            _logger.error("Error handling session input: %s", e)
            return {"error": str(e)}

    def _finalize_create_action(self, bot, chat_id, session):
        flow = session.flow_id
        final_text = ""
        try:
            values = json.loads(session.collected_values or "{}")
            vals = {}
            
            # Process Fixed Mappings
            for mapping in flow.field_mapping_ids:
                if mapping.value_type == 'fixed':
                    vals[mapping.field_id.name] = mapping.fixed_value
                elif mapping.value_type == 'ask':
                    if mapping.field_id.name in values:
                         vals[mapping.field_id.name] = values[mapping.field_id.name]

            # Employee logic
            if flow.model_id.model == 'hr.expense':
                 employee = self._get_employee(bot, chat_id)
                 if employee:
                     vals['employee_id'] = employee.id
                 if 'name' not in vals:
                     vals['name'] = "Expense via Bot"

            if not vals:
                 final_text = "(Error: No data provided for creation)"
            else:
                request.env[flow.model_id.model].sudo().create(vals)
                final_text = "(Record Created Successfully)"
                
            # Close session
            session.sudo().write({'is_active': False})
            
        except Exception as e:
            request.env.cr.rollback()
            _logger.error("Error creating record from session: %s", e)
            final_text = f"(Error creating record: {e})"
            session.sudo().write({'is_active': False})

        self.send_message(bot.token, chat_id, flow, final_text=final_text)
        return {"ok": True}

    def _get_employee(self, bot, chat_id):
        # TODO: Implement a way to link Telegram ID to Odoo User/Employee
        # For now, let's assume the bot is used by the admin or try to find by some logic in future
        # In a real app, we'd look up a res.users with 'telegram_chat_id' = chat_id
        # For this demo, let's just pick the first employee or the admin's employee
        return request.env['hr.employee'].sudo().search([], limit=1)

