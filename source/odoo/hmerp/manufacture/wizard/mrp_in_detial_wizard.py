
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError


class MrpInDetialWizard(models.TransientModel):
    _name = 'mrp.in.detial.dialog.wizard'
    _description = u'生产入库明细查询向导'

    @api.model
    def _default_date_start(self):
        return self.env.user.company_id.start_date

    @api.model
    def _default_date_end(self):
        return date.today()

    name = fields.Char('单据号码')
    date_start = fields.Date('开始日期', default=_default_date_start, required=True)
    date_end = fields.Date('结束日期', default=_default_date_end, required=True)
    user_id = fields.Many2one('staff', '经办人')
    goods_id = fields.Many2one('goods', '商品')
    goods_categ_id = fields.Many2one('core.category', '商品类别', help='只统计选定的商品类别')
    warehouse_id = fields.Many2one('warehouse', '仓库', help='只统计选定的仓库')
    state_type = fields.Selection([
                ('draft', '草稿'),
                ('done', '已确认'),
                ('all', '所有'),
                ], string='单据状态', default='done')

    def button_ok(self):
        if self.date_end < self.date_start:
            raise UserError('开始日期不能大于结束日期！\n 所选的开始日期:%s 结束日期:%s' %
                            (self.date_start, self.date_end))
        domain = [('date', '>=', self.date_start),
                  ('date', '<=', self.date_end),
                  ]

        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.warehouse_id:
            domain.append(('warehouse_id', '=', self.warehouse_id.id))
        if self.name and self.name != '':
            domain.append(('name', 'ilike', self.name))
        if self.goods_id:
            domain.append(('goods_id', '=', self.goods_id.id))
        if self.goods_categ_id:
            domain.append(('category_id', '=', self.goods_categ_id.id))
        if self.state_type in ['draft', 'done']:
            domain.append(('state', '=', self.state_type))
        return {
            'name': '生产入库明细',
            'view_mode': 'tree',
            'res_model': 'mrp.in.detial.report',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'domain': domain,
            'limit': 65535,
        }