from . import models
from . import wizard
from odoo import api, fields, SUPERUSER_ID

def set_draft_invoice_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    companys = env['res.company'].search([('draft_invoice', '=', False)])
    for company in companys:
        company.write({
            'draft_invoice': True
        })