from odoo import models, fields, api


class SellOrderLine(models.Model):
    _inherit = 'sell.order.line'

    @api.onchange('subtotal')
    def _inverse_all_amount(selfs):
        '''当订单行的价税合计改变时，改变销售单价、含税单价、金额、外币金额'''
        # subtotal 价税合计  tax_amount 税额  tax_rate 税率(%)  amount  金额
        # discount_amount  折扣额  discount_rate  折扣率%  price_taxed  含税单价
        # price  销售单价  currency_amount  外币金额
        for self in selfs:
            if self.order_id.currency_id.id == self.env.user.company_id.currency_id.id:
                self.price_taxed = (self.subtotal + self.discount_amount) / \
                    self.quantity if self.quantity is not None else 0  # 含税单价
                self.tax_amount = self.subtotal / (100 + self.tax_rate) * self.tax_rate  # 税额
                self.amount = self.subtotal - self.tax_amount  # 金额
            else:
                rate_silent = self.env['res.currency'].get_rate_silent(
                    self.order_id.date, self.order_id.currency_id.id) or 1
                if not self.order_id.pay_base_currency:
                    rate_silent = 1
                if self.quantity != 0:
                    self.price_taxed = (self.subtotal / rate_silent +
                                self.discount_amount) / self.quantity   # 含税单价
                self.tax_amount = self.subtotal / (100 + 
                                self.tax_rate) * self.tax_rate  # 税额
                self.amount = self.subtotal - self.tax_amount  # 本位币金额
                currency_amount = self.quantity * self.price_taxed - self.discount_amount    # 外币金额
                self.currency_amount = currency_amount  # 外币金额

    subtotal = fields.Float(inverse=_inverse_all_amount)     # 可输入并反算

