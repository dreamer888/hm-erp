
from datetime import date, timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError


class SellTopTenWizard(models.TransientModel):
    _name = 'sell.top.ten.wizard'
    _description = '销量前十商品向导'

    @api.model
    def _default_date_start(self):
        '''返回6天前的日期'''
        now = date.today()
        return (now - timedelta(days=6)).strftime('%Y-%m-%d')

    @api.model
    def _default_date_end(self):
        return date.today()

    date_start = fields.Date('开始日期', default=_default_date_start,
                             help='报表汇总的开始日期，默认为一周前日期')
    date_end = fields.Date('结束日期', default=_default_date_end,
                           help='报表汇总的结束日期，默认为当前日期')
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

        return {
            'name': '销量前十商品',
            'view_mode': 'tree',
            'res_model': 'sell.top.ten',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'context': self.read(['date_start', 'date_end', 'warehouse_id'])[0],
        }
