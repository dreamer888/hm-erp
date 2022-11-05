from odoo import models, fields, api

class SellToBuyWizard(models.TransientModel):
    _name = 'sell.to.buy.wizard'
    _description = '根据销售订单生成采购订单向导'

    sell_line_ids = fields.Many2many(
        'sell.order.line',
        string='销售单行',
        domain=[
            ('is_bought', '=', False),
            ('order_id.type', '=', 'sell'),
            ('order_id.state', '=', 'done')],
        help='对应的销售订单行')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def _get_vals(self, order, line):
        '''返回创建 buy order line 时所需数据'''
        return {
            'order_id': order.id,
            'goods_id': line.goods_id.id,
            'attribute_id': line.attribute_id.id,
            'quantity': line.quantity - line.quantity_out,
            'uom_id': line.uom_id.id,
            'tax_rate': line.tax_rate,
            'sell_line_id': line.id,    # sell_line_id写入到采购订单行上
        }

    def button_ok(self):
        '''生成按钮，复制销售订单行到采购订单中'''
        for wizard in self:
            active_id = self.env.context.get('active_id')
            buy_lines = []
            order = self.env['buy.order'].browse(active_id)
            for line in wizard.sell_line_ids:
                if line.quantity > line.quantity_out:
                    buy_lines.append(self._get_vals(order, line))
                    line.is_bought = True
            bought_success = False
            if buy_lines and buy_lines is not None:
                # 将销售订单行复制到采购订单
                order.write({
                    'line_ids': [(0, 0, line) for line in buy_lines]})
                # 价格取自商品的成本字段或者供应商供货价格
                for line in order.line_ids:
                    line.onchange_goods_id()
                bought_success = True
            if not bought_success:  # 判断采购订单行写入不成功，重置销售订单行商品“已采购”状态
                for line in wizard.sell_line_ids:
                    line.is_bought = False
            return True
