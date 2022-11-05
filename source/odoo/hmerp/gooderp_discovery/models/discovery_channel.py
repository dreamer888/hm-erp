from odoo import models, fields


class DiscoveryChannel(models.Model):
    _name = 'discovery.channel'
    _description = '异常定义'

    name = fields.Char('名称', required=True)
    model_id = fields.Many2one('ir.model', '模型', required=True)
    condition = fields.Text('过滤条件', required=True)
    action_id = fields.Many2one('ir.actions.act_window', '处理界面', required=True)
