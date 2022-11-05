
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError


class SellOrderDetailWizard(models.TransientModel):
    _name = 'sell.order.detail.wizard'
    _description = '销售明细表向导'

    @api.model
    def _default_date_start(self):
        return self.env.user.company_id.start_date

    @api.model
    def _default_date_end(self):
        return date.today()

    date_start = fields.Date('开始日期', default=_default_date_start,
                             help='报表汇总的开始日期，默认为公司启用日期')
    date_end = fields.Date('结束日期', default=_default_date_end,
                           help='报表汇总的结束日期，默认为当前日期')
    partner_id = fields.Many2one('partner', '客户',
                                 help='只统计选定的客户')
    goods_id = fields.Many2one('goods', '商品',
                               help='只统计选定的商品')
    user_id = fields.Many2one('res.users', '销售员',
                              help='只统计选定的销售员')
    warehouse_id = fields.Many2one('warehouse', '仓库',
                                   help='只统计选定的仓库')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def button_ok(self):
        '''向导上的确定按钮'''
        self.ensure_one()
        if self.date_end < self.date_start:
            raise UserError('开始日期不能大于结束日期！\n所选开始日期:%s所选结束日期:%s' %
                            (self.date_start, self.date_end))

        domain = [('date', '>=', self.date_start),
                  ('date', '<=', self.date_end),
                  ]

        if self.goods_id:
            domain.append(('goods_id', '=', self.goods_id.id))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.warehouse_id:
            domain.append(('warehouse_id', '=', self.warehouse_id.id))

        view = self.env.ref('sell.sell_order_detail_tree')
        graph_view = self.env.ref('sell.sell_order_detail_graph')
        return {
            'name': '销售发货明细表',

            'view_mode': 'tree,pivot',
            'view_id': False,
            'views': [(view.id, 'tree'), (graph_view.id, 'graph'), (graph_view.id, 'pivot')],
            'res_model': 'sell.order.detail',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'domain': domain,
            'limit': 65535,
        }
