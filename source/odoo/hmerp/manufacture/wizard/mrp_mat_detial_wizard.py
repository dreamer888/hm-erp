
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError


class MrpMatDetialWizard(models.TransientModel):
    _name = 'mrp.mat.detial.dialog.wizard'
    _description = u'生产领退补明细查询向导'

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
    state_type = fields.Selection([
                ('draft', '草稿'),
                ('done', '已确认'),
                ('all', '所有'),
                ], string='单据状态', default='done')
    goods_id = fields.Many2one('goods', '商品')
    goods_categ_id = fields.Many2one('core.category', '商品类别',
                                     help='只统计选定的商品类别')
    warehouse_id = fields.Many2one('warehouse', '仓库',
                                   help='只统计选定的仓库')

    def button_ok(self):
        if self.date_end < self.date_start:
            raise UserError('开始日期不能大于结束日期！\n 所选的开始日期:%s 结束日期:%s' %
                            (self.date_start, self.date_end))
        fields = ['date_start', 'date_end']
        if self.user_id:
            fields.append('user_id')
        if self.name and self.name != '':
            fields.append('name')
        if self.goods_id:
            fields.append('goods_id')
        if self.goods_categ_id:
            fields.append('goods_categ_id')
        if self.state_type:
            fields.append('state_type')
        if self.warehouse_id:
            fields.append('warehouse_id')
        return {
            'name': '生产领退补明细',
            'view_mode': 'tree',
            'res_model': 'mrp.mat.detial.report',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'context': self.read(fields)[0],
            'limit': 65535,
        }