
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError


class BuyOrderDetailWizard(models.TransientModel):
    _name = 'buy.order.detail.wizard'
    _description = '采购入库明细表向导'

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
    partner_id = fields.Many2one('partner', '供应商',
                                 help='只统计选定的供应商')
    goods_id = fields.Many2one('goods', '商品',
                               help='只统计选定的商品')
    order_id = fields.Many2one('buy.receipt', '单据编号',
                               help='只统计选定的单据编号')
    warehouse_dest_id = fields.Many2one('warehouse', '仓库',
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
            raise UserError('开始日期不能大于结束日期！')

        domain = [('date', '>=', self.date_start),
                  ('date', '<=', self.date_end),
                  ]

        if self.goods_id:
            domain.append(('goods_id', '=', self.goods_id.id))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.order_id:
            domain.append(('order_name', '=', self.order_id.name))
        if self.warehouse_dest_id:
            domain.append(('warehouse_dest_id', '=',
                           self.warehouse_dest_id.id))

        view = self.env.ref('buy.buy_order_detail_tree')
        return {
            'name': '采购入库明细表',
            'view_mode': 'tree',
            'view_id': False,
            'views': [(view.id, 'tree')],
            'res_model': 'buy.order.detail',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'domain': domain,
            'limit': 65535,
        }
