from odoo import models, fields


class SellOrder(models.Model):
    _inherit = 'sell.order'
    name = fields.Char(default='', required=True, help="请输入订单编号")
    _sql_constraints = [
        ('name_uniq', 'unique(name)', '销售订单编号不可重复!')
    ]
