from odoo import models, fields
from odoo.tools.safe_eval import safe_eval
import datetime, dateutil

class DiscoveryWizard(models.TransientModel):
    _name = 'discovery.wizard'
    _description = '洞察向导'

    channel_ids = fields.Many2many('discovery.channel', string='异常', required=True)

    def button_ok(self):
        res_ids = []
        for channel in self.channel_ids:
            records = self.env[channel.model_id.model].search([])
            todo_ids = []
            for rec in records:
                eval_context = {
                    'record': rec,
		    'user': self.env.user,
                    'datetime':datetime,
                    'dateutil': dateutil,
                }
                if safe_eval(channel.sudo().condition.strip(), eval_context, nocopy=True):
                    todo_ids.append(rec.id)
            res_ids.append(
                self.env['discovery.result'].create({
                    'channel_id': channel.id,
                    'id_list': todo_ids,
                    'id_count': len(todo_ids),
                }).id
            )
        return {
            'name': '今日洞察报告',
            'view_mode': 'tree',
            'view_id': False,
            'views': [(self.env.ref('hmERP_discovery.discovery_result_view_tree').id, 'tree')],
            'res_model': 'discovery.result',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'domain': [('id', 'in', res_ids)],
        }
