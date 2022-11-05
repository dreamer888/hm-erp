from odoo import models


class BuyOrder(models.Model):
    _inherit = 'buy.order'

    def buy_order_done(self):
        ret = super().buy_order_done()
        for bo in self:
            for line in bo.line_ids:
                if not line.price:
                    continue      # 采购价为 0 不更新
                line.goods_id.cost = line.price
                line.goods_id.onchange_gpm()
                if not line.goods_id.supplier_id:
                    line.goods_id.supplier_id = bo.partner_id.id
        return ret
