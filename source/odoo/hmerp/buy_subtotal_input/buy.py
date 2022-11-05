from odoo import models, fields, api


class BuyOrderLine(models.Model):
    _inherit = 'buy.order.line'

    @api.onchange('subtotal')
    def _inverse_all_amount(selfs):
        for self in selfs:
            '''当订单行的价税合计改变时，改变销售单价、含税单价、税额、金额'''
            if self.quantity:
                self.price_taxed = (
                    self.subtotal + self.discount_amount) / self.quantity  # 含税单价
            self.tax_amount = self.subtotal / (
                100 + self.tax_rate) * self.tax_rate  # 税额
            self.amount = self.subtotal - self.tax_amount  # 金额

    subtotal = fields.Float(inverse=_inverse_all_amount)  # 可输入并反算
