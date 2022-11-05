from odoo import models, fields, api


class sell_order_line(models.Model):
    _inherit = "sell.order.line"

    is_bought = fields.Boolean('已采购', copy=False, readonly=True)
    buy_price = fields.Float('采购单价', compute='_compute_buy_price')

    @api.depends('is_bought')
    def _compute_buy_price(self):
        for s in self:
            s.buy_price = 0
            if s.is_bought:
                bol = self.env['buy.order.line'].search([
                    ('sell_line_id', '=', s.id),
                ])
                s.buy_price = bol.price
