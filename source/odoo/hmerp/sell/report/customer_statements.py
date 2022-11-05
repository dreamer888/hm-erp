##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, models, api, tools


from odoo.exceptions import UserError


class CustomerStatementsReport(models.Model):
    _inherit = "customer.statements.report"
    _auto = False

    sale_amount = fields.Float(string='销售金额', readonly=True,
                               digits='Amount')
    benefit_amount = fields.Float(string='优惠金额', readonly=True,
                                  digits='Amount')
    fee = fields.Float(string='客户承担费用', readonly=True,
                       digits='Amount')
    move_id = fields.Many2one('wh.move', string='出入库单', readonly=True)

    def init(self):
        # union money_order(type = 'get'), money_invoice(type = 'income')
        cr = self._cr
        tools.drop_view_if_exists(cr, 'customer_statements_report')
        cr.execute("""
            CREATE or REPLACE VIEW customer_statements_report AS (
            SELECT  ROW_NUMBER() OVER(ORDER BY partner_id, date, amount desc) AS id,
                    partner_id,
                    name,
                    date,
                    done_date,
                    sale_amount,
                    benefit_amount,
                    fee,
                    amount,
                    pay_amount,
                    discount_money,
                    balance_amount,
                    note,
                    move_id
            FROM
                (
               SELECT m.partner_id,
                        m.name,
                        m.date,
                        m.write_date AS done_date,
                        0 AS sale_amount,
                        0 AS benefit_amount,
                        0 AS fee,
                        0 AS amount,
                        m.amount AS pay_amount,
                        m.discount_amount as discount_money,
                        0 AS balance_amount,
                        m.note,
                        0 AS move_id
                FROM money_order AS m
                WHERE m.type = 'get' AND m.state = 'done'
                UNION ALL
                SELECT  mi.partner_id,
                        mi.name,
                        mi.date,
                        mi.create_date AS done_date,
                        sd.amount + sd.discount_amount AS sale_amount,
                        sd.discount_amount AS benefit_amount,
                        sd.partner_cost AS fee,
                        mi.amount,
                        0 AS pay_amount,
                        0 as discount_money,
                        0 AS balance_amount,
                        Null AS note,
                        mi.move_id
                FROM money_invoice AS mi
                LEFT JOIN core_category AS c ON mi.category_id = c.id
                LEFT JOIN sell_delivery AS sd ON sd.sell_move_id = mi.move_id
                WHERE c.type = 'income' AND mi.state = 'done'
                ) AS ps)
        """)

    def find_source_order(self):
        # 查看原始单据，三种情况：收款单、销售退货单、销售发货单、核销单
        self.ensure_one()
        model_view = {
            'money.order': {'name': '收款单',
                            'view': 'money.money_order_form'},
            'sell.delivery': {'name': '销售发货单',
                              'view': 'sell.sell_delivery_form',
                              'name_return': '销售退货单',
                              'view_return': 'sell.sell_return_form'},
            'reconcile.order': {'name': '核销单',
                                'view': 'money.reconcile_order_form'}
        }
        for model, view_dict in model_view.items():
            res = self.env[model].search([('name', '=', self.name)])
            name = model == 'sell.delivery' and res.is_return and \
                view_dict['name_return'] or view_dict['name']
            view = model == 'sell.delivery' and res.is_return and \
                self.env.ref(view_dict['view_return']) \
                or self.env.ref(view_dict['view'])
            if res:
                return {
                    'name': name,
                    'view_mode': 'form',
                    'view_id': False,
                    'views': [(view.id, 'form')],
                    'res_model': model,
                    'type': 'ir.actions.act_window',
                    'res_id': res.id,
                }
        raise UserError('期初余额无原始单据可查看。')


class CustomerStatementsReportWithGoods(models.TransientModel):
    _name = "customer.statements.report.with.goods"
    _description = "客户对账单带商品明细"

    partner_id = fields.Many2one('partner', string='业务伙伴', readonly=True)
    name = fields.Char(string='单据编号', readonly=True)
    date = fields.Date(string='单据日期', readonly=True)
    done_date = fields.Datetime(string='完成日期', readonly=True)
    category_id = fields.Many2one('core.category', '商品类别')
    goods_code = fields.Char('商品编号')
    goods_name = fields.Char('商品名称')
    attribute_id = fields.Many2one('attribute', '规格型号')
    uom_id = fields.Many2one('uom', '单位')
    quantity = fields.Float('数量', digits='Quantity')
    price = fields.Float('单价', digits='Price')
    discount_amount = fields.Float('折扣额', digits='Amount')
    without_tax_amount = fields.Float(
        '不含税金额', digits='Amount')
    tax_amount = fields.Float('税额', digits='Amount')
    order_amount = fields.Float(
        string='销售金额', digits='Amount')
    benefit_amount = fields.Float(
        string='优惠金额', digits='Amount')
    fee = fields.Float(string='客户承担费用', digits='Amount')
    amount = fields.Float(string='应收金额', digits='Amount')
    pay_amount = fields.Float(
        string='实际收款金额', digits='Amount')
    discount_money = fields.Float(string='收款折扣', readonly=True,
                                  digits='Amount')
    balance_amount = fields.Float(
        string='应收款余额', digits='Amount')
    note = fields.Char(string='备注', readonly=True)
    move_id = fields.Many2one('wh.move', string='出入库单', readonly=True)

    def find_source_order(self):
        # 查看原始单据，三种情况：收款单、销售退货单、销售发货单
        self.ensure_one()
        model_view = {
            'money.order': {'name': '收款单',
                            'view': 'money.money_order_form'},
            'sell.delivery': {'name': '销售发货单',
                              'view': 'sell.sell_delivery_form',
                              'name_return': '销售退货单',
                              'view_return': 'sell.sell_return_form'},
            'reconcile.order': {'name': '核销单',
                                'view': 'money.reconcile_order_form'}
        }
        for model, view_dict in model_view.items():
            res = self.env[model].search([('name', '=', self.name)])
            name = model == 'sell.delivery' and res.is_return and view_dict[
                'name_return'] or view_dict['name']
            view = model == 'sell.delivery' and res.is_return and self.env.ref(view_dict['view_return']) \
                or self.env.ref(view_dict['view'])
            if res:
                return {
                    'name': name,
                    'view_mode': 'form',
                    'view_id': False,
                    'views': [(view.id, 'form')],
                    'res_model': model,
                    'type': 'ir.actions.act_window',
                    'res_id': res.id,
                }
        raise UserError('期初余额无原始单据可查看。')
