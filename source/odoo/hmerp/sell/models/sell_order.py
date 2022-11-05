
from odoo import fields, models, api

from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)

# 销售订单确认状态可选值
SELL_ORDER_STATES = [
    ('draft', '草稿'),
    ('done', '已确认'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class SellOrder(models.Model):
    _name = 'sell.order'
    _description = '销售订单'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    @api.depends('line_ids.subtotal', 'discount_amount')
    def _compute_amount(self):
        '''当订单行和优惠金额改变时，改变成交金额'''
        for o in self:
            total = sum(line.subtotal for line in o.line_ids)
            o.amount = total - o.discount_amount
            o.untax_amount = sum(line.amount for line in o.line_ids)
            o.tax_amount   = sum(line.tax_amount for line in o.line_ids)

    @api.depends('line_ids.quantity')
    def _compute_qty(self):
        '''当订单行数量改变时，更新总数量'''
        for o in self:
            o.total_qty = sum(line.quantity for line in o.line_ids)

    @api.depends('delivery_ids.state')
    def _get_sell_goods_state(selfs):
        '''返回发货状态'''
        for self in selfs:
            if all(line.quantity_out == 0 for line in self.line_ids):
                if any(r.state == 'draft' for r in self.delivery_ids) or self.state=='draft':
                    self.goods_state = '未出库'
                else:
                    self.goods_state = '全部作废'
            elif any(line.quantity > line.quantity_out for line in self.line_ids):
                if any(r.state == 'draft' for r in self.delivery_ids):
                    self.goods_state = '部分出库'
                else:
                    self.goods_state = '部分出库剩余作废'
            else:
                self.goods_state = '全部出库'

    @api.depends('partner_id')
    def _compute_currency_id(self):
        for o in self:
            self.currency_id = \
                self.partner_id.c_category_id.account_id.currency_id.id \
                or self.partner_id.s_category_id.account_id.currency_id.id

    @api.model
    def _default_warehouse(self):
        return self._default_warehouse_impl()

    @api.model
    def _default_warehouse_impl(self):
        if self.env.context.get('warehouse_type'):
            return self.env['warehouse'].get_warehouse_by_type(
                self.env.context.get('warehouse_type'))

    def _get_received_amount(selfs):
        '''计算销售订单收款/退款状态'''
        for self in selfs:
            deliverys = self.env['sell.delivery'].search(
                [('order_id', '=', self.id)])
            money_order_rows = self.env['money.order'].search([('sell_id', '=', self.id),
                                                            ('reconciled', '=', 0),
                                                            ('state', '=', 'done')])
            self.received_amount = sum([delivery.invoice_id.reconciled for delivery in deliverys]) +\
                sum([order_row.amount for order_row in money_order_rows])

    @api.depends('delivery_ids')
    def _compute_delivery(self):
        for order in self:
            order.delivery_count = len([deli for deli in order.delivery_ids if not deli.is_return])
            order.return_count = len([deli for deli in order.delivery_ids if deli.is_return])
    
    @api.depends('partner_id')
    def _get_sell_user(selfs):
        '''计算销售单据的业务员，不允许修改'''
        for self in selfs:
            if self.partner_id:
                if self.partner_id.responsible_id:
                    self.user_id = self.partner_id.responsible_id
                else:
                    self.user_id = self._uid

    @api.depends('line_ids.goods_id', 'line_ids.quantity')
    def _compute_net_weight(self):
        '''计算净重合计'''
        for o in self:
            o.net_weight = sum(
                line.goods_id.net_weight * line.quantity 
                for line in o.line_ids
                )

    partner_id = fields.Many2one('partner', '客户',
                                 ondelete='restrict', states=READONLY_STATES,
                                 help='签约合同的客户')
    contact = fields.Char('联系人', states=READONLY_STATES,
                          help='客户方的联系人')
    address_id = fields.Many2one('partner.address', '地址', states=READONLY_STATES,
                                 domain="[('partner_id', '=', partner_id)]",
                                 help='联系地址')
    mobile = fields.Char('手机', states=READONLY_STATES,
                         help='联系手机')
    user_id = fields.Many2one(
        'res.users',
        '销售员',
        ondelete='restrict',store=True,
        states=READONLY_STATES,
        compute='_get_sell_user',
        help='单据经办人',
    )
    date = fields.Date('单据日期',
                       required=True,
                       states=READONLY_STATES,
                       default=lambda self: fields.Date.context_today(self),
                       index=True,
                       copy=False,
                       help="默认是订单创建日期")
    delivery_date = fields.Date(
        '要求交货日期',
        required=True,
        states=READONLY_STATES,
        default=lambda self: fields.Date.context_today(self),
        index=True,
        copy=False,
        help="订单的要求交货日期")
    type = fields.Selection([('sell', '销售'), ('return', '退货')], '类型',
                            default='sell', states=READONLY_STATES,
                            help='销售订单的类型，分为销售或退货')
    ref = fields.Char('客户订单号')
    warehouse_id = fields.Many2one('warehouse',
                                   '调出仓库',
                                   required=True,
                                   ondelete='restrict',
                                   states=READONLY_STATES,
                                   default=_default_warehouse,
                                   help='商品将从该仓库调出')
    name = fields.Char('单据编号', index=True, copy=False,
                       default='/', help="创建时它会自动生成下一个编号")
    line_ids = fields.One2many('sell.order.line', 'order_id', '销售订单行',
                               states=READONLY_STATES, copy=True,
                               help='销售订单的明细行，不能为空')
    note = fields.Text('备注', help='单据备注')
    discount_rate = fields.Float('优惠率(%)', states=READONLY_STATES,
                                 help='整单优惠率')
    discount_amount = fields.Float('抹零', states=READONLY_STATES,
                                   track_visibility='always',
                                   digits='Amount',
                                   help='整单优惠金额，可由优惠率自动计算出来，也可手动输入')
    amount = fields.Float(string='成交金额', store=True, readonly=True,
                          compute='_compute_amount', track_visibility='always',
                          digits='Amount',
                          help='总金额减去优惠金额')
    tax_amount = fields.Float(string='税额', store=True, readonly=True,
                          compute='_compute_amount', track_visibility='always',
                          digits='Amount',
                          help='税额')
    untax_amount = fields.Float(string='不含税金额', store=True, readonly=True,
                          compute='_compute_amount', track_visibility='always',
                          digits='Amount',
                          help='不含税金额')
    total_qty = fields.Float(string='数量合计', store=True, readonly=True, copy=False,
                          compute='_compute_qty',
                          track_visibility='always',
                          digits='Quantity',
                          help='数量总计')
    pre_receipt = fields.Float('预收款', states=READONLY_STATES,
                               digits='Amount',
                               help='输入预收款确认销售订单，会产生一张收款单')
    bank_account_id = fields.Many2one('bank.account', '结算账户',
                                      ondelete='restrict',
                                      help='用来核算和监督企业与其他单位或个人之间的债权债务的结算情况')
    approve_uid = fields.Many2one('res.users', '确认人', copy=False,
                                  ondelete='restrict',
                                  help='确认单据的人')
    state = fields.Selection(SELL_ORDER_STATES, '确认状态', readonly=True,
                             help="销售订单的确认状态", index=True,
                             copy=False, default='draft')
    goods_state = fields.Char('发货状态', compute=_get_sell_goods_state,
                              default='未出库',
                              store=True,
                              help="销售订单的发货状态", index=True, copy=False)
    cancelled = fields.Boolean('已终止',
                               help='该单据是否已终止')
    currency_id = fields.Many2one('res.currency',
                                  '外币币别',
                                  compute='_compute_currency_id',
                                  store=True,
                                  readonly=True,
                                  help='外币币别')
    pay_base_currency = fields.Boolean('以本币结算', help='客户以本币付款到我公司基本账户内')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    received_amount = fields.Float(
        '已收金额',  compute=_get_received_amount, readonly=True)
    delivery_ids = fields.One2many(
        'sell.delivery', 'order_id', string='发货单', copy=False)
    delivery_count = fields.Integer(
        compute='_compute_delivery', string='发货单数量', default=0)
    return_count = fields.Integer(
        compute='_compute_delivery', string='退货单数量', default=0)
    pay_method = fields.Many2one('pay.method',
                                 string='付款方式',
                                 ondelete='restrict')
    term_id = fields.Many2one('core.value', "贸易条款",
                              domain=[('type', '=', 'price_term')],
                              context={'type': 'price_term'}
                              )
    pol = fields.Char('起运港')
    pod = fields.Char('目的港')
    express_type = fields.Char('承运商')
    money_order_id = fields.Many2one(
        'money.order',
        '预收款单',
        readonly=True,
        copy=False,
        help='输入预收款确认时产生的预收款单')
    net_weight = fields.Float(
        string='净重合计', compute='_compute_net_weight', store=True)

    invoice_ids = fields.One2many(
        'money.invoice', compute='_compute_invoice', string='Invoices')
    invoice_count = fields.Integer(
        compute='_compute_invoice', string='Invoices Count', default=0)

    details = fields.Html('明细',compute='_compute_details')

    paid_no_goods = fields.Boolean('已收款未发货',compute="_compute_paid_no_goods",store=True)

    goods_id = fields.Many2one(
        'goods', related='line_ids.goods_id', string='商品') #用于在列表上根据商品搜索

    @api.depends('money_order_id.state','goods_state')
    def _compute_paid_no_goods(self):
        for o in self:
            o.paid_no_goods = False
            if o.state == 'done' and o.goods_state == '未出库' and o.received_amount:
                if not all(line.goods_id.no_stock for line in self.line_ids):
                    o.paid_no_goods = True

    @api.depends('line_ids')
    def _compute_details(self):
        for v in self:
            vl = {'col':[],'val':[]}
            vl['col'] = ['商品','数量','单价','已发']
            for l in v.line_ids:
                vl['val'].append([l.goods_id.name,l.quantity,l.price,l.quantity_out])
            v.details = v.company_id._get_html_table(vl)

    @api.onchange('address_id')
    def onchange_partner_address(self):
        ''' 选择地址填充 联系人、电话 '''
        if self.address_id:
            self.contact = self.address_id.contact
            self.mobile = self.address_id.mobile

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        ''' 选择客户带出其默认地址信息 '''
        if self.partner_id:
            self.contact = self.partner_id.contact
            self.mobile = self.partner_id.mobile
            self.pay_method = self.partner_id.pay_method

            for child in self.partner_id.child_ids:
                if child.is_default_add:
                    self.address_id = child.id
            if self.partner_id.child_ids and not any([child.is_default_add for child in self.partner_id.child_ids]):
                partners_add = self.env['partner.address'].search(
                    [('partner_id', '=', self.partner_id.id)], order='id')
                self.address_id = partners_add[0].id

            for line in self.line_ids:
                line.tax_rate = line.goods_id.get_tax_rate(line.goods_id, self.partner_id, 'sell')

            address_list = [
                child_list.id for child_list in self.partner_id.child_ids]
            if address_list:
                return {'domain': {'address_id': [('id', 'in', address_list)]}}
            else:
                self.address_id = False

    @api.onchange('discount_rate', 'line_ids')
    def onchange_discount_rate(self):
        '''当优惠率或销售订单行发生变化时，单据优惠金额发生变化'''
        total = sum(line.subtotal for line in self.line_ids)
        self.discount_amount = total * self.discount_rate * 0.01

    def _get_vals(self):
        '''返回创建 money_order 时所需数据'''
        flag = (self.type == 'sell' and 1 or -1)  # 用来标志发库或退货
        amount = flag * self.amount
        this_reconcile = flag * self.pre_receipt
        money_lines = [{
            'bank_id': self.bank_account_id.id,
            'amount': this_reconcile,
        }]
        return {
            'partner_id': self.partner_id.id,
            'date': fields.Date.context_today(self),
            'line_ids':
            [(0, 0, line) for line in money_lines],
            'amount': amount,
            'reconciled': this_reconcile,
            'to_reconcile': amount,
            'state': 'draft',
            'origin_name': self.name,
            'sell_id': self.id,
        }

    def generate_receipt_order(self):
        '''由销售订单生成收款单'''
        # 发库单/退货单
        if self.pre_receipt:
            money_order = self.with_context(type='get').env['money.order'].create(
                self._get_vals()
            )
            return money_order

    def sell_order_done(self):
        '''确认销售订单'''
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认！')
        if not self.line_ids:
            raise UserError('请输入商品明细行！')
        for line in self.line_ids:
            # 检查属性是否填充，防止无权限人员不填就可以保存
            if line.using_attribute and not line.attribute_id:
                raise UserError('请输入商品：%s 的属性' % line.goods_id.name)
            if line.quantity <= 0 or line.price_taxed < 0:
                raise UserError('商品 %s 的数量和含税单价不能小于0！' % line.goods_id.name)
            if line.tax_amount > 0 and self.currency_id:
                raise UserError('外贸免税！')
        if not self.bank_account_id and self.pre_receipt:
            raise UserError('预付款不为空时，请选择结算账户！')
        # 销售预收款生成收款单
        money_order = self.generate_receipt_order()
        self.sell_generate_delivery()

        self.approve_uid = self._uid
        self.write({
            'money_order_id': money_order and money_order.id,
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })
        return True

    def sell_order_draft(self):
        '''撤销确认销售订单'''
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销 %s' % self._description)
        if any(r.state == 'done' for r in self.delivery_ids):
            raise UserError('该销售订单已经发货，不能撤销确认！')
        # 查找产生的发货单并删除
        self.delivery_ids.unlink()
        # 查找产生的收款单并删除
        if self.money_order_id:
            self.money_order_id.unlink()
        self.approve_uid = False
        self.state = 'draft'

    def get_delivery_line(self, line, single=False):
        '''返回销售发货/退货单行'''
        self.ensure_one()
        qty = 0
        discount_amount = 0
        if single:
            qty = 1
            discount_amount = line.discount_amount \
                / ((line.quantity - line.quantity_out) or 1)
        else:
            qty = line.quantity - line.quantity_out
            discount_amount = line.discount_amount

        return {
            'type': self.type == 'sell' and 'out' or 'in',
            'sell_line_id': line.id,
            'goods_id': line.goods_id.id,
            'attribute_id': line.attribute_id.id,
            'uos_id': line.goods_id.uos_id.id,
            'goods_qty': qty,
            'uom_id': line.uom_id.id,
            'cost_unit': line.goods_id.cost,
            'price': line.price,
            'price_taxed': line.price_taxed,
            'discount_rate': line.discount_rate,
            'discount_amount': discount_amount,
            'tax_rate': line.tax_rate,
            'plan_date':self.delivery_date,
        }

    def _generate_delivery(self, delivery_line):
        '''根据明细行生成发货单或退货单'''
        # 如果退货，warehouse_dest_id，warehouse_id要调换
        warehouse = (self.type == 'sell'
                     and self.warehouse_id
                     or self.env.ref("warehouse.warehouse_customer"))
        warehouse_dest = (self.type == 'sell'
                          and self.env.ref("warehouse.warehouse_customer")
                          or self.warehouse_id)
        rec = (self.type == 'sell' and self.with_context(is_return=False)
               or self.with_context(is_return=True))
        delivery_id = rec.env['sell.delivery'].create({
            'partner_id': self.partner_id.id,
            'warehouse_id': warehouse.id,
            'warehouse_dest_id': warehouse_dest.id,
            'user_id': self.user_id.id,
            'date': self.delivery_date,
            'order_id': self.id,
            'ref':self.ref,
            'origin': 'sell.delivery',
            'discount_rate': self.discount_rate,
            'discount_amount': self.discount_amount,
            'currency_id': self.currency_id.id,
            'contact': self.contact,
            'address_id': self.address_id.id,
            'mobile': self.mobile,
            'express_type': self.express_type,
        })
        if self.type == 'sell':
            delivery_id.write({'line_out_ids': [
                (0, 0, line) for line in delivery_line]})
        else:
            delivery_id.write({'line_in_ids': [
                (0, 0, line) for line in delivery_line]})
        return delivery_id

    def sell_generate_delivery(self):
        '''由销售订单生成销售发货单'''
        self.ensure_one()
        delivery_line = []  # 销售发货单行

        for line in self.line_ids:
            # 如果订单部分出库，则点击此按钮时生成剩余数量的出库单
            to_out = line.quantity - line.quantity_out
            if to_out <= 0:
                continue
            if line.goods_id.force_batch_one:
                i = 0
                while i < to_out:
                    i += 1
                    delivery_line.append(
                        self.get_delivery_line(line, single=True))
            else:
                delivery_line.append(
                    self.get_delivery_line(line, single=False))

        if not delivery_line:
            return {}
        self._generate_delivery(delivery_line)
        return {}

    @api.depends('delivery_ids')
    def _compute_invoice(self):
        for order in self:
            money_invoices = self.env['money.invoice'].search([
                ('name', '=', order.name)])
            order.invoice_ids = not money_invoices and order.delivery_ids.mapped('invoice_id') or money_invoices + order.delivery_ids.mapped('invoice_id')
            order.invoice_count = len(order.invoice_ids.ids)
    
    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_count == 0:
            return False
        action = {
            'name': '结算单（客户发票）',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'money.invoice',
            'view_id': False,
            'target': 'current',
        }
        invoice_ids = self.invoice_ids.ids
        # choose the view_mode accordingly
        action['domain'] = "[('id','in',[" + \
            ','.join(map(str, invoice_ids)) + "])]"
        action['view_mode'] = 'tree'
        return action

    def action_view_delivery(self):
        '''
        This function returns an action that display existing deliverys of given sells order ids.
        When only one found, show the delivery immediately.
        '''
        self.ensure_one()
        action = {
            'name': '销售发货单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sell.delivery',
            'view_id': False,
            'target': 'current',
        }
        delivery_ids = [delivery.id for delivery in self.delivery_ids if not delivery.is_return]
        if len(delivery_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, delivery_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(delivery_ids) == 1:
            view_id = self.env.ref('sell.sell_delivery_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = delivery_ids and delivery_ids[0] or False
        return action

    def action_view_return(self):
        '''
        该销售订单对应的退货单
        '''
        self.ensure_one()
        action = {
            'name': '销售退货单',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sell.delivery',
            'view_id': False,
            'target': 'current',
        }
        tree_view_id = self.env.ref('sell.sell_return_tree').id
        form_view_id = self.env.ref('sell.sell_return_form').id
        delivery_ids = [delivery.id for delivery in self.delivery_ids if delivery.is_return]
        if len(delivery_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                               ','.join(map(str, delivery_ids)) + "])]"
            action['view_mode'] = 'tree,form'
            action['views'] = [(tree_view_id, 'tree'), (form_view_id, 'form')]
        elif len(delivery_ids) == 1:
            action['views'] = [(form_view_id, 'form')]
            action['res_id'] = delivery_ids and delivery_ids[0] or False
        return action


class SellOrderLine(models.Model):
    _name = 'sell.order.line'
    _description = '销售订单明细'

    @api.depends('goods_id')
    def _compute_using_attribute(self):
        '''返回订单行中商品是否使用属性'''
        for l in self:
            l.using_attribute = l.goods_id.attribute_ids and True or False

    @api.depends('quantity', 'price_taxed', 'discount_amount', 'tax_rate')
    def _compute_all_amount(selfs):
        '''当订单行的数量、含税单价、折扣额、税率改变时，改变销售金额、税额、价税合计'''
        for self in selfs:
            if self.order_id.currency_id.id == self.env.user.company_id.currency_id.id:
                self.subtotal = self.price_taxed * self.quantity - self.discount_amount  # 价税合计
                self.tax_amount = self.subtotal / \
                                  (100 + self.tax_rate) * self.tax_rate  # 税额
                self.amount = self.subtotal - self.tax_amount  # 金额
            else:
                rate_silent = self.env['res.currency'].get_rate_silent(
                    self.order_id.date, self.order_id.currency_id.id) or 1
                if not self.order_id.pay_base_currency:
                    rate_silent = 1
                self.subtotal = (self.price_taxed * self.quantity -
                                 self.discount_amount) * rate_silent  # 价税合计
                self.tax_amount = self.subtotal / \
                                  (100 + self.tax_rate) * self.tax_rate  # 税额
                self.amount = self.subtotal - self.tax_amount  # 本位币金额

    @api.onchange('price', 'tax_rate')
    def onchange_price(self):
        '''当订单行的不含税单价改变时，改变含税单价。
        如果将含税价改为99,则self.price计算出来为84.62,price=99/1.17，
        跟84.62保留相同位数比较时是相等的，这种情况则保留含税价不变，
        这样处理是为了使得修改含税价时不再重新计算含税价。
        '''
        _logger.info('单价或税率发生变化')
        price = self.price_taxed / (1 + self.tax_rate * 0.01)  # 不含税单价
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price_taxed = self.price * (1 + self.tax_rate * 0.01)

    order_id = fields.Many2one('sell.order', '订单编号', index=True,
                               required=True, ondelete='cascade',
                               help='关联订单的编号')
    goods_id = fields.Many2one('goods',
                               '商品',
                               required=True,
                               ondelete='restrict',
                               help='商品')
    using_attribute = fields.Boolean('使用属性', compute=_compute_using_attribute,
                                     help='商品是否使用属性')
    attribute_id = fields.Many2one('attribute', '属性',
                                   ondelete='restrict',
                                   domain="[('goods_id', '=', goods_id)]",
                                   help='商品的属性，当商品有属性时，该字段必输')
    uom_id = fields.Many2one('uom', '单位', ondelete='restrict',
                             help='商品计量单位')
    quantity = fields.Float('数量',
                            default=1,
                            required=True,
                            digits='Quantity',
                            help='下单数量')
    quantity_out = fields.Float('已执行数量', copy=False,
                                digits='Quantity',
                                help='销售订单产生的发货单/退货单已执行数量')
    price = fields.Float('销售单价',
                         store=True,
                         digits='Price',
                         help='不含税单价，由含税单价计算得出')
    price_taxed = fields.Float('含税单价',
                               digits='Price',
                               help='含税单价，取商品零售价')
    discount_rate = fields.Float('折扣率%',
                                 help='折扣率')
    discount_amount = fields.Float('折扣额',
                                   help='输入折扣率后自动计算得出，也可手动输入折扣额')
    amount = fields.Float('金额',
                          compute=_compute_all_amount,
                          store=True,
                          digits='Amount',
                          help='金额  = 价税合计  - 税额')
    tax_rate = fields.Float('税率(%)',
                            help='税率')
    tax_amount = fields.Float('税额',
                              compute=_compute_all_amount,
                              store=True,
                              digits='Amount',
                              help='税额')
    subtotal = fields.Float('价税合计',
                            compute=_compute_all_amount,
                            store=True,
                            digits='Amount',
                            help='含税单价 乘以 数量')
    note = fields.Char('备注',
                       help='本行备注')
    company_id = fields.Many2one(
        'res.company', string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    @api.onchange('goods_id')
    def onchange_warehouse_id(self):
        '''当订单行的仓库变化时，带出定价策略中的折扣率'''
        if self.order_id.warehouse_id and self.goods_id:
            partner = self.order_id.partner_id
            warehouse = self.order_id.warehouse_id
            goods = self.goods_id
            date = self.order_id.date
            pricing = self.env['pricing'].get_pricing_id(
                partner, warehouse, goods, date)
            if pricing:
                self.discount_rate = pricing.discount_rate
            else:
                self.discount_rate = 0

    @api.onchange('goods_id')
    def onchange_goods_id(self):
        '''当订单行的商品变化时，带出商品上的单位、默认仓库、价格、税率'''
        if self.goods_id:
            self.uom_id = self.goods_id.uom_id
            self.price = self.goods_id.price
            self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, self.order_id.partner_id, 'sell')

    @api.onchange('quantity', 'price_taxed', 'discount_rate')
    def onchange_discount_rate(self):
        '''当数量、单价或优惠率发生变化时，优惠金额发生变化'''
        _logger.info('数量、含税价、折扣率发生变化')
        self.price = self.price_taxed / (1 + self.tax_rate * 0.01)
        self.discount_amount = self.quantity * self.price \
            * self.discount_rate * 0.01
    
    @api.constrains('tax_rate')
    def _check_tax_rate(selfs):
        for self in selfs:
            if self.tax_rate > 100:
                raise UserError('税率不能输入超过100的数!\n输入税率:%s' % self.tax_rate)
            if self.tax_rate < 0:
                raise UserError('税率不能输入负数\n 输入税率:%s' % self.tax_rate)
            
    


class ApproveMultiSellOrder(models.TransientModel):
    _name = "approve.multi.sell.order"
    _description = '批量确认销售订单'

    def set_default_note(self):
        """
        设置默认值, 用来确认要批量确认的订单
        """
        context = self.env.context
        order_names = [order.name for order in self.env['sell.order'].browse(context.get('active_ids'))]
        return '-'.join(order_names)

    note = fields.Char('本次处理销售订单', default=set_default_note, readonly=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """ 根据内容判断 报出错误 """
        res = super(ApproveMultiSellOrder, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=False)
        orders = self.env['sell.order'].browse(self.env.context.get('active_ids'))
        done_lists = ''
        for order in orders:
            if order.state == 'done':
                done_lists += order.name
        if done_lists:
            raise UserError('销售订单 ' + done_lists + ' 已确认!')
        return res

    def approve_sell_order(self):
        """ 确认销售订单 """
        for order in self.env['sell.order'].search([('id', 'in', self.env.context.get('active_ids'))]):
            order.sell_order_done()
