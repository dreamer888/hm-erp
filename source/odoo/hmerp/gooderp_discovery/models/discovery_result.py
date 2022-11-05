from odoo import models, fields


class DiscoveryResult(models.TransientModel):
    _name = 'discovery.result'
    _description = '洞察报告'

    channel_id = fields.Many2one('discovery.channel', '异常')
    id_list = fields.Char('id list')
    id_count = fields.Integer('记录数')

    def open_action(self):
        self.ensure_one()
        action = self.channel_id.action_id.read()[0]
        new_domain = [('id', 'in', list(eval(self.id_list)))]
        action.update({'domain': new_domain})
        return action
