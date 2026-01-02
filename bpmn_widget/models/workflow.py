from odoo import models, fields

class BpmnWorkflow(models.Model):
    _name = 'bpmn.workflow'
    _description = 'BPMN Workflow'

    name = fields.Char(string='Name', required=True)
    xml_content = fields.Text(string='BPMN XML')
