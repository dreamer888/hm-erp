
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError


class SellSummaryPartnerWizard(models.TransientModel):
    _name = 'sell.summary.partner.wizard'
    _description = '销售汇总表（按客户）向导'

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
    c_category_id = fields.Many2one('core.category', '客户类别',
                                    domain=[('type', '=', 'customer')],
                                    context={'type': 'customer'},
                                    help='只统计选定的客户类别')
    warehouse_id = fields.Many2one('warehouse', '仓库',
                                   help='只统计选定的仓库')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def button_ok(self):
        self.ensure_one()
        if self.date_end < self.date_start:
            raise UserError('开始日期不能大于结束日期！\n 所选的开始日期:%s 结束日期:%s' %
                            (self.date_start, self.date_end))
        read_fields = ['date_start', 'date_end', 'partner_id',
                       'goods_id', 'c_category_id', 'warehouse_id']
        return {
            'name': '销售汇总表（按客户）',
            'view_mode': 'tree',
            'res_model': 'sell.summary.partner',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'context': self.read(read_fields)[0],
            'limit': 65535,
        }
