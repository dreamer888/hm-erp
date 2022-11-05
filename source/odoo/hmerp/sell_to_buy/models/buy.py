from odoo import models, fields, api


class buy_order(models.Model):
    _inherit = "buy.order"


    def sell_to_buy(self):
        '''根据销售订单生成采购订单'''
        for order in self:
            return {
                'name': '销售订单生成采购订单向导',
                'view_mode': 'form',
                'res_model': 'sell.to.buy.wizard',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def unlink(self):
        """删除采购订单时，如果对应销售订单行已采购，则去掉打勾"""
        bo_line_ids = []
        for line in self:
            for li in line.line_ids:
                bo_line_ids.append(li.sell_line_id.id)
        sol_line_ids = self.env['sell.order.line'].search([('id', 'in', bo_line_ids)])
        for rec in sol_line_ids:
            rec.is_bought = False
        return super(buy_order, self).unlink()


class buy_order_line(models.Model):
    _inherit = "buy.order.line"

    sell_line_id = fields.Many2one('sell.order.line',
                                   '销售单行',
                                   copy=False,
                                   ondelete='restrict',
                                   help='对应的销售订单行')

    def unlink(self):
        '''删除采购订单行时，如果对应销售订单行已采购，则去掉打勾'''
        for line in self:
            if line.sell_line_id:
                line.sell_line_id.is_bought = False
        return super(buy_order_line, self).unlink()


class BuyReceipt(models.Model):

    _inherit = 'buy.receipt'

    def buy_receipt_done(self):
        res = super().buy_receipt_done()
        # 通知发货单已到货
        for l in self.line_in_ids:
            sol = l.buy_line_id.sell_line_id
            if sol:
                wml = self.env['wh.move.line'].search(
                    [('sell_line_id', '=', sol.id),
                     ('state', '=', 'draft')]
                )
                if len(wml) != 1:
                    continue
                sd = self.env['sell.delivery'].search(
                    [('sell_move_id', '=', wml.move_id.id)]
                )
                sd.message_post(
                    subtype='mail.mt_comment',
                    body=self._get_delivery_arrive_message(rl=l, sd=sd)
                    )
        return res

    def _get_delivery_arrive_message(self, rl, sd):
        return '%s到货%s%s' % (rl.goods_id.name, rl.goods_qty, rl.uom_id.name)
