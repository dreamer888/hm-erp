# -*- coding: utf-8 -*-
##############################################################################

from odoo import api, fields, models, _


class wizard_workflow_message(models.TransientModel):
    _name = 'wizard.workflow.message'
    _description = 'workflow Message'
    name = fields.Char('审批意见')

    def apply(self):
        self.ensure_one()
        ctx = self.env.context
        order = self.env[ctx.get('active_model')].browse(ctx.get('active_id'))
        order.with_context(ctx).workflow_action(self.name)
        return True
