

from odoo import fields, models, api, tools


class SellOrderDetail(models.Model):
    _name = 'sell.order.detail'
    _description = '销售明细表'
    _auto = False

    date = fields.Date('销售日期')
    order_name = fields.Char('销售单据号')
    type = fields.Char('业务类型')
    user_id = fields.Many2one('res.users', '销售员')
    partner_id = fields.Many2one('partner', '客户')
    goods_code = fields.Char('商品编码')
    goods_id = fields.Many2one('goods', '商品名称')
    attribute = fields.Char('属性')
    warehouse_id = fields.Many2one('warehouse', '仓库')
    qty = fields.Float('数量', digits='Quantity')
    uom = fields.Char('单位')
    price = fields.Float('单价', digits='Price')
    amount = fields.Float('销售收入', digits='Amount')
    tax_amount = fields.Float('税额', digits='Amount')
    subtotal = fields.Float('价税合计', digits='Amount')
    margin = fields.Float('毛利', digits='Amount')
    money_state = fields.Char('收款状态')
    note = fields.Char('备注')
    last_receipt_date = fields.Date(string='最后收款日期')

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, 'sell_order_detail')
        cr.execute("""
            CREATE or REPLACE VIEW sell_order_detail AS (
                SELECT  MIN(wml.id) AS id,
                    wm.date AS date,
                    wm.name AS order_name,
                    (CASE WHEN wm.origin = 'sell.delivery.sell' THEN '销售'
                    ELSE '退货' END) AS type,
                    wm.user_id AS user_id,
                    wm.partner_id AS partner_id,
                    goods.code AS goods_code,
                    goods.id AS goods_id,
                    attr.name AS attribute,
                    wh.id AS warehouse_id,
                    SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_qty
                        ELSE - wml.goods_qty END) AS qty,
                    uom.name AS uom,
                    wml.price AS price,
                    SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.amount
                        ELSE - wml.amount END) AS amount,
                    SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.tax_amount
                        ELSE - wml.tax_amount END) AS tax_amount,
                    SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.subtotal
                        ELSE - wml.subtotal END) AS subtotal,
                    (SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.amount
                            ELSE - wml.amount END) - SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_qty
                                                            ELSE - wml.goods_qty END) * wml.cost_unit) AS margin,
                    (CASE WHEN wm.origin = 'sell.delivery.sell' THEN sd.money_state
                    ELSE sd.return_state END) AS money_state,
                    wml.note AS note,
                    mi.get_amount_date AS last_receipt_date

                FROM wh_move_line AS wml
                    LEFT JOIN wh_move wm ON wml.move_id = wm.id
                    LEFT JOIN partner ON wm.partner_id = partner.id
                    LEFT JOIN goods ON wml.goods_id = goods.id
                    LEFT JOIN attribute AS attr ON wml.attribute_id = attr.id
                    LEFT JOIN warehouse AS wh ON wml.warehouse_id = wh.id
                         OR wml.warehouse_dest_id = wh.id
                    LEFT JOIN uom ON goods.uom_id = uom.id
                    LEFT JOIN sell_delivery AS sd ON wm.id = sd.sell_move_id
                    LEFT JOIN money_invoice AS mi ON mi.id = sd.invoice_id

                WHERE wml.state = 'done'
                  AND wm.origin like 'sell.delivery%%'
                  AND wh.type = 'stock'

                GROUP BY wm.date, wm.name, origin, wm.user_id, wm.partner_id,
                    goods_code, goods.id, attribute, wh.id, uom,
                    wml.price, wml.cost_unit, sd.money_state, sd.return_state, wml.note,
                    mi.get_amount_date
                )
        """)

    def view_detail(self):
        '''查看明细按钮'''
        self.ensure_one()
        order = self.env['sell.delivery'].search(
            [('name', '=', self.order_name)])
        if order:
            if not order.is_return:
                view = self.env.ref('sell.sell_delivery_form')
            else:
                view = self.env.ref('sell.sell_return_form')

            return {
                'name': '销售发货单',
    
                'view_mode': 'form',
                'view_id': False,
                'views': [(view.id, 'form')],
                'res_model': 'sell.delivery',
                'type': 'ir.actions.act_window',
                'res_id': order.id,
            }
