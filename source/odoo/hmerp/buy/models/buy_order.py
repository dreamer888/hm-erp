##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022  唤梦科技(<http://www.dreammm.net>).
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

from odoo import fields, models, api

from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import float_compare, float_is_zero

# 采购订单确认状态可选值
BUY_ORDER_STATES = [
    ('draft', '草稿'),
    ('done', '已确认'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class BuyOrder(models.Model):
    _name = "buy.order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "采购订单"
    _order = 'date desc, id desc'

    @api.depends('line_ids.subtotal', 'discount_amount')
    def _compute_amount(selfs):
        '''当订单行和优惠金额改变时，改变成交金额'''
        for self in selfs:
            total = sum(line.subtotal for line in self.line_ids)
            self.amount = total - self.discount_amount
            self.untax_amount = sum(line.amount for line in self.line_ids)
            self.tax_amount   = sum(line.tax_amount for line in self.line_ids)
    
    @api.depends('line_ids.quantity')
    def _compute_qty(selfs):
        '''当订单行数量改变时，更新总数量'''
        for self in selfs:
            self.total_qty = sum(line.quantity for line in self.line_ids)

    @api.depends('receipt_ids.state')
    def _get_buy_goods_state(selfs):
        '''返回收货状态'''
        for self in selfs:
            if all(line.quantity_in == 0 for line in self.line_ids):
                if any(r.state == 'draft' for r in self.receipt_ids) or self.state=='draft':
                    self.goods_state = '未入库'
                else:
                    self.goods_state = '全部作废'
            elif any(line.quantity > line.quantity_in for line in self.line_ids):
                if any(r.state == 'draft' for r in self.receipt_ids):
                    self.goods_state = '部分入库'
                else:
                    self.goods_state = '部分入库剩余作废'
            else:
                self.goods_state = '全部入库'

    @api.model
    def _default_warehouse_dest_impl(self):
        if self.env.context.get('warehouse_dest_type'):
            return self.env['warehouse'].get_warehouse_by_type(
                self.env.context.get('warehouse_dest_type'))

    @api.model
    def _default_warehouse_dest(self):
        '''获取默认调入仓库'''
        return self._default_warehouse_dest_impl()

    def _get_paid_amount(selfs):
        '''计算采购订单付款/退款状态'''
        for self in selfs:
            if not self.invoice_by_receipt: # 分期付款时
                money_invoices = self.env['money.invoice'].search([
                    ('name', '=', self.name),
                    ('state', '=', 'done')])
                self.paid_amount = sum([invoice.reconciled for invoice in money_invoices])
            else:
                receipts = self.env['buy.receipt'].search([('order_id', '=', self.id)])
                # 采购订单上输入预付款时
                money_order_rows = self.env['money.order'].search([('buy_id', '=', self.id),
                                                                ('reconciled', '=', 0),
                                                                ('state', '=', 'done')])
                self.paid_amount = sum([receipt.invoice_id.reconciled for receipt in receipts]) +\
                    sum([order_row.amount for order_row in money_order_rows])

    @api.depends('receipt_ids')
    def _compute_receipt(self):
        for order in self:
            order.receipt_count = len([receipt for receipt in order.receipt_ids if not receipt.is_return])
            order.return_count = len([receipt for receipt in order.receipt_ids if receipt.is_return])

    @api.depends('receipt_ids')
    def _compute_invoice(self):
        for order in self:
            money_invoices = self.env['money.invoice'].search([
                ('name', '=', order.name)])
            order.invoice_ids = not money_invoices and order.receipt_ids.mapped('invoice_id') or money_invoices + order.receipt_ids.mapped('invoice_id')
            order.invoice_count = len(order.invoice_ids.ids)

    partner_id = fields.Many2one('partner', '供应商',
                                 states=READONLY_STATES,
                                 ondelete='restrict',
                                 help='供应商')
    contact = fields.Char('联系人', states=READONLY_STATES)

    address_id = fields.Many2one('partner.address', '地址', 
                                 states=READONLY_STATES,
                                 domain="[('partner_id', '=', partner_id)]",
                                 help='联系地址')

    date = fields.Date('单据日期',
                       states=READONLY_STATES,
                       default=lambda self: fields.Date.context_today(self),
                       index=True,
                       copy=False,
                       help="默认是订单创建日期")
    planned_date = fields.Date(
        '要求交货日期',
        states=READONLY_STATES,
        default=lambda self: fields.Date.context_today(
            self),
        index=True,
        copy=False,
        help="订单的要求交货日期")
    name = fields.Char('单据编号',
                       index=True,
                       copy=False,
                       help="采购订单的唯一编号，当创建时它会自动生成下一个编号。")
    type = fields.Selection([('buy', '采购'),
                             ('return', '退货')],
                            '类型',
                            default='buy',
                            states=READONLY_STATES,
                            help='采购订单的类型，分为采购或退货')
    ref = fields.Char('供应商订单号')
    warehouse_dest_id = fields.Many2one('warehouse',
                                        '调入仓库',
                                        required=True,
                                        default=_default_warehouse_dest,
                                        ondelete='restrict',
                                        states=READONLY_STATES,
                                        help='将商品调入到该仓库')
    invoice_by_receipt = fields.Boolean(string="按收货结算",
                                        default=True,
                                        help='如未勾选此项，可在资金行里输入付款金额，订单保存后，采购人员可以单击资金行上的【确认】按钮。')
    line_ids = fields.One2many('buy.order.line',
                               'order_id',
                               '采购订单行',
                               states=READONLY_STATES,
                               copy=True,
                               help='采购订单的明细行，不能为空')
    note = fields.Text('备注',
                       help='单据备注')
    discount_rate = fields.Float('优惠率(%)',
                                 states=READONLY_STATES,
                                 digits='Amount',
                                 help='整单优惠率')
    discount_amount = fields.Float('抹零',
                                   states=READONLY_STATES,
                                   track_visibility='always',
                                   digits='Amount',
                                   help='整单优惠金额，可由优惠率自动计算出来，也可手动输入')
    amount = fields.Float('成交金额',
                          store=True,
                          compute='_compute_amount',
                          track_visibility='always',
                          digits='Amount',
                          help='总金额减去优惠金额')
    untax_amount = fields.Float('不含税合计',
                          store=True,
                          compute='_compute_amount',
                          track_visibility='always',
                          digits='Amount')
    tax_amount = fields.Float('税金合计',
                          store=True,
                          compute='_compute_amount',
                          track_visibility='always',
                          digits='Amount')
    total_qty = fields.Float(string='数量合计', store=True, readonly=True,
                          compute='_compute_qty',
                          track_visibility='always',
                          digits='Quantity',
                          help='数量总计')
    prepayment = fields.Float('预付款',
                              states=READONLY_STATES,
                              digits='Amount',
                              help='输入预付款确认采购订单，会产生一张付款单')
    bank_account_id = fields.Many2one('bank.account',
                                      '结算账户',
                                      ondelete='restrict',
                                      help='用来核算和监督企业与其他单位或个人之间的债权债务的结算情况')
    approve_uid = fields.Many2one('res.users',
                                  '确认人',
                                  copy=False,
                                  ondelete='restrict',
                                  help='确认单据的人')
    state = fields.Selection(BUY_ORDER_STATES,
                             '确认状态',
                             readonly=True,
                             help="采购订单的确认状态",
                             index=True,
                             copy=False,
                             default='draft')
    goods_state = fields.Char('收货状态',
                              compute=_get_buy_goods_state,
                              default='未入库',
                              store=True,
                              help="采购订单的收货状态",
                              index=True,
                              copy=False)
    cancelled = fields.Boolean('已终止',
                               help='该单据是否已终止')
    pay_ids = fields.One2many("payment.plan",
                              "buy_id",
                              string="付款计划",
                              help='分批付款时使用付款计划')
    goods_id = fields.Many2one(
        'goods', related='line_ids.goods_id', string='商品')
    receipt_ids = fields.One2many(
        'buy.receipt', 'order_id', string='入库单', copy=False)
    receipt_count = fields.Integer(
        compute='_compute_receipt', string='入库单数量', default=0)
    return_count = fields.Integer(
        compute='_compute_receipt', string='退货单数量', default=0)
    invoice_ids = fields.One2many(
        'money.invoice', compute='_compute_invoice', string='Invoices')
    invoice_count = fields.Integer(
        compute='_compute_invoice', string='Invoices Count', default=0)
    currency_id = fields.Many2one('res.currency',
                                  '外币币别',
                                  store=True,
                                  related='partner_id.s_category_id.account_id.currency_id',
                                  help='外币币别')
    express_type = fields.Char(string='承运商',)
    term_id = fields.Many2one('core.value', "贸易条款",
                              domain=[('type', '=', 'price_term')],
                              context={'type': 'price_term'})
    user_id = fields.Many2one(
        'res.users',
        '经办人',
        ondelete='restrict',
        states=READONLY_STATES,
        default=lambda self: self.env.user,
        help='单据经办人',
    )
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    paid_amount = fields.Float(
        '已付金额', compute=_get_paid_amount, readonly=True)
    paid_no_goods = fields.Boolean('已付款未到货',compute="_compute_paid_no_goods",store=True)
    money_order_id = fields.Many2one(
        'money.order',
        '预付款单',
        readonly=True,
        copy=False,
        help='输入预付款确认时产生的预付款单')

    details = fields.Html('明细',compute='_compute_details')

    @api.depends('money_order_id.state','goods_state')
    def _compute_paid_no_goods(self):
        for o in self:
            o.paid_no_goods = False
            if o.state == 'done' and o.goods_state == '未入库' and o.paid_amount:
                if not all(line.goods_id.no_stock for line in self.line_ids):
                    o.paid_no_goods = True

    @api.depends('line_ids')
    def _compute_details(self):
        for v in self:
            vl = {'col':[],'val':[]}
            vl['col'] = ['商品','数量','单价','已收']
            for l in v.line_ids:
                vl['val'].append([l.goods_id.name,l.quantity,l.price,l.quantity_in])
            v.details = v.company_id._get_html_table(vl)


    @api.onchange('discount_rate', 'line_ids')
    def onchange_discount_rate(self):
        '''当优惠率或采购订单行发生变化时，单据优惠金额发生变化'''
        total = sum(line.subtotal for line in self.line_ids)
        self.discount_amount = total * self.discount_rate * 0.01

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            for line in self.line_ids:
                line.tax_rate = line.goods_id.get_tax_rate(line.goods_id, self.partner_id, 'buy')
            self.contact = self.partner_id.main_contact
    
    @api.onchange('address_id')
    def onchange_address_id(self):
        if self.address_id:
            self.contact = self.address_id.contact

    def _get_vals(self):
        '''返回创建 money_order 时所需数据'''
        flag = (self.type == 'buy' and 1 or -1)  # 用来标志入库或退货
        amount = flag * self.amount
        this_reconcile = flag * self.prepayment
        money_lines = [{
            'bank_id': self.bank_account_id.id,
            'amount': this_reconcile,
        }]
        return {
            'partner_id': self.partner_id.id,
            'bank_name': self.partner_id.bank_name,
            'bank_num': self.partner_id.bank_num,
            'date': fields.Date.context_today(self),
            'line_ids':
            [(0, 0, line) for line in money_lines],
            'amount': amount,
            'reconciled': this_reconcile,
            'to_reconcile': amount,
            'state': 'draft',
            'origin_name': self.name,
            'buy_id': self.id,
        }

    def generate_payment_order(self):
        '''由采购订单生成付款单'''
        # 入库单/退货单
        if self.prepayment:
            money_order = self.with_context(type='pay').env['money.order'].create(
                self._get_vals()
            )
            return money_order

    def buy_order_done(self):
        '''确认采购订单'''
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认')
        if not self.line_ids:
            raise UserError('请输入商品明细行')
        for line in self.line_ids:
            # 检查属性是否填充，防止无权限人员不填就可以保存
            if line.using_attribute and not line.attribute_id:
                raise UserError('请输入商品：%s 的属性' % line.goods_id.name)
            if line.quantity <= 0 or line.price_taxed < 0:
                raise UserError('商品 %s 的数量和含税单价不能小于0' % line.goods_id.name)
            if line.tax_amount > 0 and self.currency_id:
                raise UserError('外贸免税')
        if not self.bank_account_id and self.prepayment:
            raise UserError('预付款不为空时，请选择结算账户')
        # 采购预付款生成付款单
        money_order = self.generate_payment_order()
        self.buy_generate_receipt()

        self.approve_uid = self._uid
        self.write({
            'money_order_id': money_order and money_order.id,
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })

    def buy_order_draft(self):
        '''撤销确认采购订单'''
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销%s' % self._description)
        if any(r.state == 'done' for r in self.receipt_ids):
            raise UserError('该采购订单已经收货，不能撤销确认！')
        # 查找产生的发票并删除
        for inv in self.invoice_ids:
            if inv.state == 'done':
                raise UserError('该采购订单已经收票，不能撤销确认！')
            else:
                inv.unlink()
        for plan in self.pay_ids:
            plan.date_application = ''
        # 查找产生的入库单并删除
        self.receipt_ids.unlink()
        # 查找产生的付款单并撤销确认，删除
        for money_order_id in self.env['money.order'].search([('buy_id','=',self.id)]):
            if money_order_id.state == 'done':
                money_order_id.money_order_draft()
            money_order_id.unlink()
        self.approve_uid = False
        self.state = 'draft'

    def get_receipt_line(self, line, single=False):
        '''返回采购入库/退货单行'''
        self.ensure_one()
        qty = 0
        discount_amount = 0
        if single:
            qty = 1
            discount_amount = (line.discount_amount /
                               ((line.quantity - line.quantity_in) or 1))
        else:
            qty = line.quantity - line.quantity_in
            discount_amount = line.discount_amount
        return {
            'type': self.type == 'buy' and 'in' or 'out',
            'buy_line_id': line.id,
            'goods_id': line.goods_id.id,
            'attribute_id': line.attribute_id.id,
            'uos_id': line.goods_id.uos_id.id,
            'goods_qty': qty,
            'uom_id': line.uom_id.id,
            'cost_unit': line.price,
            'price': line.price,
            'price_taxed': line.price_taxed,
            'discount_rate': line.discount_rate,
            'discount_amount': discount_amount,
            'tax_rate': line.tax_rate,
            'plan_date':self.planned_date,
        }

    def _generate_receipt(self, receipt_line):
        '''根据明细行生成入库单或退货单'''
        # 如果退货，warehouse_dest_id，warehouse_id要调换
        warehouse = (self.type == 'buy'
                     and self.env.ref("warehouse.warehouse_supplier")
                     or self.warehouse_dest_id)
        warehouse_dest = (self.type == 'buy'
                          and self.warehouse_dest_id
                          or self.env.ref("warehouse.warehouse_supplier"))
        rec = (self.type == 'buy' and self.with_context(is_return=False)
               or self.with_context(is_return=True))
        receipt_id = rec.env['buy.receipt'].create({
            'partner_id': self.partner_id.id,
            'warehouse_id': warehouse.id,
            'warehouse_dest_id': warehouse_dest.id,
            'date': self.planned_date,
            'date_due': self.planned_date,
            'order_id': self.id,
            'ref':self.ref,
            'origin': 'buy.receipt',
            'discount_rate': self.discount_rate,
            'discount_amount': self.discount_amount,
            'invoice_by_receipt': self.invoice_by_receipt,
            'currency_id': self.currency_id.id,
        })
        if self.type == 'buy':
            receipt_id.write({'line_in_ids': [
                (0, 0, line) for line in receipt_line]})
        else:
            receipt_id.write({'line_out_ids': [
                (0, 0, line) for line in receipt_line]})
        return receipt_id

    def buy_generate_receipt(self):
        '''由采购订单生成采购入库/退货单'''
        self.ensure_one()
        receipt_line = []  # 采购入库/退货单行

        for line in self.line_ids:
            # 如果订单部分入库，则点击此按钮时生成剩余数量的入库单
            to_in = line.quantity - line.quantity_in
            if to_in <= 0:
                continue
            if line.goods_id.force_batch_one:
                i = 0
                while i < to_in:
                    i += 1
                    receipt_line.append(
                        self.get_receipt_line(line, single=True))
            else:
                receipt_line.append(self.get_receipt_line(line, single=False))

        if not receipt_line:
            return {}
        self._generate_receipt(receipt_line)
        return {}

    def action_view_receipt(self):
        '''
        This function returns an action that display existing picking orders of given purchase order ids.
        When only one found, show the picking immediately.
        '''

        self.ensure_one()
        action = {
            'name': '采购入库单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'buy.receipt',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        receipt_ids = [receipt.id for receipt in self.receipt_ids if not receipt.is_return]
        # choose the view_mode accordingly
        if len(receipt_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, receipt_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(receipt_ids) == 1:
            view_id = self.env.ref('buy.buy_receipt_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = receipt_ids and receipt_ids[0] or False
        return action

    def action_view_return(self):
        '''
        该采购订单对应的退货单
        '''
        self.ensure_one()
        action = {
            'name': '采购退货单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'buy.receipt',
            'view_id': False,
            'target': 'current',
        }

        receipt_ids = [receipt.id for receipt in self.receipt_ids if receipt.is_return]
        if len(receipt_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                               ','.join(map(str, receipt_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(receipt_ids) == 1:
            view_id = self.env.ref('buy.buy_return_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = receipt_ids and receipt_ids[0] or False
        return action

    def action_view_invoice(self):
        '''
        This function returns an action that display existing invoices of given purchase order ids( linked/computed via buy.receipt).
        When only one found, show the invoice immediately.
        '''

        self.ensure_one()
        if self.invoice_count == 0:
            return False
        action = {
            'name': '结算单（供应商发票）',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'money.invoice',
            'view_id': False,
            'target': 'current',
        }
        invoice_ids = self.invoice_ids.ids
        action['domain'] = "[('id','in',[" + \
            ','.join(map(str, invoice_ids)) + "])]"
        action['view_mode'] = 'tree'
        return action


class BuyOrderLine(models.Model):
    _name = 'buy.order.line'
    _description = '采购订单明细'

    # 根据采购商品的主单位数量，计算该商品的辅助单位数量
    @api.depends('quantity', 'goods_id')
    def _get_goods_uos_qty(self):
        for line in self:
            if line.goods_id and line.quantity:
                line.goods_uos_qty = line.quantity / line.goods_id.conversion
            else:
                line.goods_uos_qty = 0

    # 根据商品的辅助单位数量，反算出商品的主单位数量
    @api.onchange('goods_uos_qty', 'goods_id')
    def _inverse_quantity(self):
        for line in self:
            line.quantity = line.goods_uos_qty * line.goods_id.conversion

    @api.depends('goods_id')
    def _compute_using_attribute(selfs):
        '''返回订单行中商品是否使用属性'''
        for self in selfs:
            self.using_attribute = self.goods_id.attribute_ids and True or False

    @api.depends('quantity', 'price_taxed', 'discount_amount', 'tax_rate')
    def _compute_all_amount(selfs):
        for self in selfs:
            '''当订单行的数量、含税单价、折扣额、税率改变时，改变采购金额、税额、价税合计'''
            self.subtotal = self.price_taxed * self.quantity - self.discount_amount  # 价税合计
            self.tax_amount = self.subtotal / (100 + self.tax_rate) * self.tax_rate  # 税额
            self.amount = self.subtotal - self.tax_amount  # 金额

    @api.onchange('price', 'tax_rate')
    def onchange_price(self):
        '''当订单行的不含税单价改变时，改变含税单价'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)  # 不含税单价
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price_taxed = self.price * (1 + self.tax_rate * 0.01)

    order_id = fields.Many2one('buy.order',
                               '订单编号',
                               index=True,
                               required=True,
                               ondelete='cascade',
                               help='关联订单的编号')
    goods_id = fields.Many2one('goods',
                               '商品',
                               ondelete='restrict',
                               help='商品')
    using_attribute = fields.Boolean('使用属性',
                                     compute=_compute_using_attribute,
                                     help='商品是否使用属性')
    attribute_id = fields.Many2one('attribute',
                                   '属性',
                                   ondelete='restrict',
                                   domain="[('goods_id', '=', goods_id)]",
                                   help='商品的属性，当商品有属性时，该字段必输')
    goods_uos_qty = fields.Float('辅助数量', digits='Quantity', compute='_get_goods_uos_qty',
                                 inverse='_inverse_quantity', store=True,
                                 help='商品的辅助数量')
    uos_id = fields.Many2one('uom', string='辅助单位', ondelete='restrict', readonly=True, help='商品的辅助单位')
    uom_id = fields.Many2one('uom',
                             '单位',
                             ondelete='restrict',
                             help='商品计量单位')
    quantity = fields.Float('数量',
                            default=1,
                            required=True,
                            digits='Quantity',
                            help='下单数量')
    quantity_in = fields.Float('已执行数量',
                               copy=False,
                               digits='Quantity',
                               help='采购订单产生的入库单/退货单已执行数量')
    price = fields.Float('采购单价',
                         store=True,
                         digits='Price',
                         help='不含税单价，由含税单价计算得出')
    price_taxed = fields.Float('含税单价',
                               digits='Price',
                               help='含税单价，取自商品成本或对应供应商的采购价')
    discount_rate = fields.Float('折扣率%',
                                 help='折扣率')
    discount_amount = fields.Float('折扣额',
                                   digits='Amount',
                                   help='输入折扣率后自动计算得出，也可手动输入折扣额')
    amount = fields.Float('金额',
                          compute=_compute_all_amount,
                          store=True,
                          digits='Amount',
                          help='金额  = 价税合计  - 税额')
    tax_rate = fields.Float('税率(%)',
                            default=lambda self: self.env.user.company_id.import_tax_rate,
                            help='默认值取公司进项税率')
    tax_amount = fields.Float('税额',
                              compute=_compute_all_amount,
                              store=True,
                              digits='Amount',
                              help='由税率计算得出')
    subtotal = fields.Float('价税合计',
                            compute=_compute_all_amount,
                            store=True,
                            digits='Amount',
                            help='含税单价 乘以 数量')
    note = fields.Char('备注',
                       help='本行备注')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    @api.onchange('goods_id', 'quantity','order_id')
    def onchange_goods_id(self):
        '''当订单行的商品变化时，带出商品上的单位、成本价。
        在采购订单上选择供应商，自动带出供货价格，没有设置供货价的取成本价格。'''
        if not self.order_id.partner_id:
            raise UserError('请先选择一个供应商！')
        if self.goods_id:
            self.uom_id = self.goods_id.uom_id
            self.uos_id = self.goods_id.uos_id
            if self.price == 0:
                self.price = self.goods_id.cost
            for line in self.goods_id.vendor_ids:
                if line.date and line.date > self.order_id.date:
                    continue
                if line.vendor_id == self.order_id.partner_id \
                        and self.quantity >= line.min_qty:
                    if self.env.company.vendor_price_taxed:
                        self.price_taxed = line.price
                    else:
                        self.price = line.price
                    break

            self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, self.order_id.partner_id, 'buy')

    @api.onchange('quantity', 'price_taxed', 'discount_rate')
    def onchange_discount_rate(self):
        '''当数量、单价或优惠率发生变化时，优惠金额发生变化'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price = price
        self.discount_amount = (self.quantity * price *
                                self.discount_rate * 0.01)
    
    @api.constrains('tax_rate')
    def _check_tax_rate(self):
        for record in self:
            if record.tax_rate > 100:
                raise UserError('税率不能输入超过100的数')
            if record.tax_rate < 0:
                raise UserError('税率不能输入负数')
            
    

class Payment(models.Model):
    _name = "payment.plan"
    _description = '付款计划'

    name = fields.Char(string="付款阶段名称", required=True,
                       help='付款计划名称')
    amount_money = fields.Float(string="金额", required=True,
                                help='付款金额')
    date_application = fields.Date(string="申请日期", readonly=True,
                                   help='付款申请日期')
    buy_id = fields.Many2one("buy.order",
                             help='关联的采购订单',
                             ondelete='cascade'
                             )

    def unlink(self):
        for p in self:
            if self.date_application:
                raise UserError('此付款计划已申请，不能删除。')
        return super().unlink()


    def request_payment(self):
        self.ensure_one()
        categ = self.env.ref('money.core_category_purchase')
        tax_rate = self.buy_id.line_ids[0].tax_rate
        tax_amount = self.amount_money * tax_rate / (100 + tax_rate)
        if not float_is_zero(self.amount_money, 2):
            source_id = self.env['money.invoice'].create({
                'name': self.buy_id.name,
                'partner_id': self.buy_id.partner_id.id,
                'category_id': categ.id,
                'date': fields.Date.context_today(self),
                'amount': self.amount_money,
                'tax_amount': tax_amount,
                'reconciled': 0,
                'to_reconcile': self.amount_money,
                'date_due': fields.Date.context_today(self),
                'state': 'draft',
            })
            # 避免付款单去核销一张未确认的结算单（公司按发票确认应收应付的场景下出现）
            if source_id.state == 'draft':
                source_id.money_invoice_done()
            self.with_context(type='pay').env["money.order"].create({
                'partner_id': self.buy_id.partner_id.id,
                'bank_name': self.buy_id.partner_id.bank_name,
                'bank_num': self.buy_id.partner_id.bank_num,
                'date': fields.Date.context_today(self),
                'source_ids':
                [(0, 0, {'name': source_id.id,
                         'category_id': categ.id,
                         'date': source_id.date,
                         'amount': self.amount_money,
                         'reconciled': 0.0,
                         'to_reconcile': self.amount_money,
                         'this_reconcile': self.amount_money})],
                'line_ids':
                [(0, 0, {'bank_id': self.buy_id.company_id.bank_account_id.id,
                       'amount': self.amount_money})],
                'type': 'pay',
                'amount': self.amount_money,
                'reconciled': 0,
                'to_reconcile': self.amount_money,
                'state': 'draft',
                'buy_id': self.buy_id.id,
            })
        self.date_application = datetime.now()
