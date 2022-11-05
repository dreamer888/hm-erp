from odoo import models, fields
from odoo.exceptions import UserError


class BuyOrderSplitWizard(models.TransientModel):
    _name = 'buy.order.split.wizard'
    _description = '采购订单拆分向导'

    order_line_id = fields.Many2one(
        'buy.order.line', '已选采购单行',
        default=lambda s: s.env.context.get('active_id'))
    exist_order_id = fields.Many2one(
        'buy.order', '未确认采购订单',
        domain=[('state', '=', 'draft')])
    new_order_vendor = fields.Many2one(
        'partner', '新订单供应商',
        domain=[('s_category_id', '!=', False)])

    def button_ok(self):
        if not self.exist_order_id and not self.new_order_vendor:
            raise UserError('请选择要加入的订单号或要新增订单的供应商')
        dest_order_id = False
        if self.exist_order_id:
            dest_order_id = self.exist_order_id.id
        else:
            # 创建新采购订单
            dest_order_id = self.env['buy.order'].create({
                'partner_id': self.new_order_vendor.id,
            }).id
        self.order_line_id.order_id = dest_order_id
        self.order_line_id.onchange_goods_id()

