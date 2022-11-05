
from odoo import fields, models, api

from odoo.exceptions import UserError
import datetime
from odoo.tools import float_compare, float_is_zero

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
}
ISODATEFORMAT = '%Y-%m-%d'


class BuyReceipt(models.Model):
    _name = "buy.receipt"
    _inherits = {'wh.move': 'buy_move_id'}
    _inherit = ['mail.thread']
    _description = "采购入库单"
    _order = 'date desc, id desc'

    @api.depends('line_in_ids.subtotal', 'discount_amount',
                 'payment', 'line_out_ids.subtotal', 'delivery_fee')
    def _compute_all_amount(selfs):
        '''当优惠金额改变时，改变成交金额'''
        for self in selfs:
            total = 0
            if self.line_in_ids:
                # 入库时优惠前总金额
                total = sum(line.subtotal for line in self.line_in_ids)
            elif self.line_out_ids:
                # 退货时优惠前总金额
                total = sum(line.subtotal for line in self.line_out_ids)
            self.amount = total - self.discount_amount + self.delivery_fee

    @api.depends('is_return', 'invoice_id.reconciled', 'invoice_id.amount')
    def _get_buy_money_state(selfs):
        '''返回付款状态'''
        for self in selfs:
            if not self.is_return:
                if self.invoice_id.reconciled == 0:
                    self.money_state = '未付款'
                elif self.invoice_id.reconciled < self.invoice_id.amount:
                    self.money_state = '部分付款'
                elif self.invoice_id.reconciled == self.invoice_id.amount:
                    self.money_state = '全部付款'

        # 返回退款状态
        if self.is_return:
            if self.invoice_id.reconciled == 0:
                self.return_state = '未退款'
            elif abs(self.invoice_id.reconciled) < abs(self.invoice_id.amount):
                self.return_state = '部分退款'
            elif self.invoice_id.reconciled == self.invoice_id.amount:
                self.return_state = '全部退款'

    buy_move_id = fields.Many2one('wh.move', '入库单',
                                  required=True, ondelete='cascade',
                                  help='入库单号')
    is_return = fields.Boolean('是否退货',
                               default=lambda self: self.env.context.get(
                                   'is_return'),
                               help='是否为退货类型')
    order_id = fields.Many2one('buy.order', '订单号',
                               copy=False, ondelete='cascade',
                               help='产生入库单/退货单的采购订单')
    invoice_id = fields.Many2one('money.invoice', '发票号', copy=False,
                                 ondelete='set null',
                                 help='产生的发票号')
    date_due = fields.Date('到期日期', copy=False,
                           default=lambda self: fields.Date.context_today(
                               self),
                           help='付款截止日期')
    discount_rate = fields.Float('优惠率(%)', states=READONLY_STATES,
                                 help='整单优惠率')
    discount_amount = fields.Float('优惠金额', states=READONLY_STATES,
                                   digits='Amount',
                                   help='整单优惠金额，可由优惠率自动计算得出，也可手动输入')
    invoice_by_receipt = fields.Boolean(string="按收货结算", default=True,
                                        help='如未勾选此项，可在资金行里输入付款金额，订单保存后，采购人员可以单击资金行上的【确认】按钮。')
    amount = fields.Float('成交金额', compute=_compute_all_amount,
                          store=True, readonly=True,
                          digits='Amount',
                          help='总金额减去优惠金额')
    payment = fields.Float('本次付款', states=READONLY_STATES,
                           digits='Amount',
                           help='本次付款金额')
    bank_account_id = fields.Many2one('bank.account', '结算账户',
                                      ondelete='restrict',
                                      help='用来核算和监督企业与其他单位或个人之间的债权债务的结算情况')
    cost_line_ids = fields.One2many('cost.line', 'buy_id', '采购费用', copy=False,
                                    help='采购费用明细行')
    money_state = fields.Char('付款状态', compute=_get_buy_money_state,
                              store=True, default='未付款',
                              help="采购入库单的付款状态",
                              index=True, copy=False)
    return_state = fields.Char('退款状态', compute=_get_buy_money_state,
                               store=True, default='未退款',
                               help="采购退货单的退款状态",
                               index=True, copy=False)
    voucher_id = fields.Many2one('voucher', '入库凭证', readonly=True,
                                 copy=False,
                                 help='入库时产生的入库凭证')
    origin_id = fields.Many2one('buy.receipt', '来源单据', copy=False)
    currency_id = fields.Many2one('res.currency',
                                  '外币币别',
                                  help='外币币别')
    currency_rate = fields.Float('汇率',digits='Price')
    delivery_fee = fields.Float('运费')
    money_order_id = fields.Many2one(
        'money.order',
        '付款单',
        readonly=True,
        copy=False,
        help='输入本次付款确认时产生的付款单')

    def set_today(self):
        self.date = fields.Date.today()

    def _compute_total(self, line_ids):
        return sum(line.subtotal for line in line_ids)

    @api.onchange('discount_rate', 'line_in_ids', 'line_out_ids')
    def onchange_discount_rate(self):
        '''当优惠率或订单行发生变化时，单据优惠金额发生变化'''
        line = self.line_in_ids or self.line_out_ids
        total = self._compute_total(line)
        if self.discount_rate:
            self.discount_amount = total * self.discount_rate * 0.01

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            for line in self.line_in_ids:
                line.tax_rate = line.goods_id.get_tax_rate(line.goods_id, self.partner_id, 'buy')

    def get_move_origin(self, vals):
        return self._name + (self.env.context.get('is_return') and
                             '.return' or '.buy')

    @api.model
    def create(self, vals):
        '''创建采购入库单时生成有序编号'''
        if not self.env.context.get('is_return'):
            name = self._name
        else:
            name = 'buy.return'
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(name) or '/'

        vals.update({
            'origin': self.get_move_origin(vals),
            'finance_category_id': self.env.ref('finance.categ_buy_goods').id,
        })
        return super(BuyReceipt, self).create(vals)

    def unlink(self):
        for receipt in self:
            receipt.buy_move_id.unlink()

    def _wrong_receipt_done(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复入库')
        batch_one_list_wh = []
        batch_one_list = []
        for line in self.line_in_ids:
            if line.amount < 0:
                raise UserError('采购金额不能小于 0！请修改。')
            if line.goods_id.force_batch_one:
                wh_move_lines = self.env['wh.move.line'].search(
                    [('state', '=', 'done'), ('type', '=', 'in'), ('goods_id', '=', line.goods_id.id)])
                for move_line in wh_move_lines:
                    if (move_line.goods_id.id, move_line.lot) not in batch_one_list_wh and move_line.lot:
                        batch_one_list_wh.append(
                            (move_line.goods_id.id, move_line.lot))

            if (line.goods_id.id, line.lot) in batch_one_list_wh:
                raise UserError('仓库已存在相同序列号的商品！\n商品:%s 序列号:%s' %
                                (line.goods_id.name, line.lot))

        for line in self.line_in_ids:
            if line.goods_qty <= 0 or line.price_taxed < 0:
                raise UserError('商品 %s 的数量和含税单价不能小于0！' % line.goods_id.name)
            if line.goods_id.force_batch_one:
                batch_one_list.append((line.goods_id.id, line.lot))

        if len(batch_one_list) > len(set(batch_one_list)):
            raise UserError('不能创建相同序列号的商品！\n 序列号列表为%s' %
                            [lot[1] for lot in batch_one_list])

        for line in self.line_out_ids:
            if line.amount < 0:
                raise UserError('退货金额不能小于 0！请修改。')
            if line.goods_qty <= 0 or line.price_taxed < 0:
                raise UserError('商品 %s 的数量和含税单价不能小于0！' % line.goods_id.name)

        if not self.bank_account_id and self.payment:
            raise UserError('付款额不为空时，请选择结算账户！')
        decimal_amount = self.env.ref('core.decimal_amount')
        if float_compare(self.payment, self.amount, precision_digits=decimal_amount.digits) == 1:
            raise UserError('本次付款金额不能大于折后金额！\n付款金额:%s 折后金额:%s' %
                            (self.payment, self.amount))
        if float_compare(sum(cost_line.amount for cost_line in self.cost_line_ids),
                         sum(line.share_cost for line in self.line_in_ids),
                         precision_digits=decimal_amount.digits) != 0:
            raise UserError('采购费用还未分摊或分摊不正确！\n采购费用:%s 分摊总费用:%s' %
                            (sum(cost_line.amount for cost_line in self.cost_line_ids),
                             sum(line.share_cost for line in self.line_in_ids)))
        return

    def _line_qty_write(self):
        self.ensure_one()
        if self.order_id:
            for line in self.line_in_ids:
                decimal_quantity = self.env.ref('core.decimal_quantity')
                if float_compare(
                        line.buy_line_id.quantity_in + line.goods_qty,
                        line.buy_line_id.quantity,
                        decimal_quantity.digits) == 1:
                    if not line.goods_id.excess:
                        raise UserError('%s收货数量大于订单数量' % line.goods_id.name)
                line.buy_line_id.quantity_in += line.goods_qty
            for line in self.line_out_ids:  # 退货单行
                if self.order_id.type == 'return':  # 退货类型的buy_order生成的采购退货单审核
                    line.buy_line_id.quantity_in += line.goods_qty
                else:
                    line.buy_line_id.quantity_in -= line.goods_qty

        return

    def _get_invoice_vals(self, partner_id, category_id, date, amount, tax_amount):
        '''返回创建 money_invoice 时所需数据'''
        return {
            'move_id': self.buy_move_id.id,
            'name': self.name,
            'partner_id': partner_id.id,
            'category_id': category_id.id,
            'date': date,
            'amount': amount,
            'reconciled': 0,
            'to_reconcile': amount,
            'tax_amount': tax_amount,
            'date_due': self.date_due,
            'state': 'draft',
        }

    def _receipt_make_invoice(self):
        '''入库单/退货单 生成结算单'''
        invoice_id = False
        if not self.is_return:
            if not self.invoice_by_receipt:
                return False
            amount = self.amount
            tax_amount = sum(line.tax_amount for line in self.line_in_ids)
        else:
            amount = -self.amount
            tax_amount = - sum(line.tax_amount for line in self.line_out_ids)
        categ = self.env.ref('money.core_category_purchase')
        if not float_is_zero(amount, 2):
            invoice_id = self.env['money.invoice'].create(
                self._get_invoice_vals(
                    self.partner_id, categ, self.date, amount, tax_amount)
            )
        return invoice_id

    def _buy_amount_to_invoice(self):
        '''采购费用产生结算单'''
        self.ensure_one()
        if sum(cost_line.amount for cost_line in self.cost_line_ids) > 0:
            for line in self.cost_line_ids:
                if not float_is_zero(line.amount, 2):
                    self.env['money.invoice'].create(
                        self._get_invoice_vals(line.partner_id, line.category_id, self.date, line.amount + line.tax,
                                               line.tax)
                    )
        return

    def _make_payment(self, invoice_id, amount, this_reconcile):
        '''根据传入的invoice_id生成付款单'''
        categ = self.env.ref('money.core_category_purchase')
        money_lines = [
            {'bank_id': self.bank_account_id.id, 'amount': this_reconcile}]
        source_lines = [{'name': invoice_id.id,
                         'category_id': categ.id,
                         'date': invoice_id.date,
                         'amount': amount,
                         'reconciled': 0.0,
                         'to_reconcile': amount,
                         'this_reconcile': this_reconcile}]
        rec = self.with_context(type='pay')
        money_order = rec.env['money.order'].create({
            'partner_id': self.partner_id.id,
            'bank_name': self.partner_id.bank_name,
            'bank_num': self.partner_id.bank_num,
            'date' : fields.Date.context_today(self),
            'line_ids':
                [(0, 0, line) for line in money_lines],
            'source_ids':
                [(0, 0, line) for line in source_lines],
            'amount': amount,
            'reconciled': this_reconcile,
            'to_reconcile': amount,
            'state': 'draft',
            'origin_name': self.name,
            'buy_id': self.order_id.id,
        })
        return money_order

    def _create_voucher_line(self, account_id, debit, credit, voucher_id, goods_id, goods_qty, partner_id):
        '''返回voucher line'''
        voucher = self.env['voucher.line'].create({
            'name': '%s %s' % (self.name, ''),
            'account_id': account_id and account_id.id,
            'partner_id': partner_id and partner_id.id,
            'debit': debit,
            'credit': credit,
            'voucher_id': voucher_id and voucher_id.id,
            'goods_id': goods_id and goods_id.id,
            'goods_qty': goods_qty,
        })
        return voucher

    def create_voucher(self):
        '''
        借： 商品分类对应的会计科目 一般是库存商品
        贷：类型为支出的类别对应的会计科目 一般是材料采购

        当一张入库单有多个商品的时候，按对应科目汇总生成多个借方凭证行。

        采购退货单生成的金额为负
        '''
        self.ensure_one()
        vouch_id = self.env['voucher'].create({'date': self.date, 'ref': '%s,%s' % (self._name, self.id)})

        sum_amount = 0
        if not self.is_return:
            for line in self.line_in_ids:
                if line.amount:
                    # 借方明细
                    self._create_voucher_line(line.goods_id.category_id.account_id,
                                              line.amount + line.share_cost, 0, vouch_id, line.goods_id, line.goods_qty, False)
                sum_amount += line.amount

            if sum_amount:
                # 贷方明细
                self._create_voucher_line(self.buy_move_id.finance_category_id.account_id,
                                          0, sum_amount, vouch_id, False, 0, self.partner_id)
            for l in self.cost_line_ids:
                self._create_voucher_line(self.buy_move_id.finance_category_id.account_id,
                                          0, l.amount, vouch_id, False, 0, l.partner_id)

        if self.is_return:
            for line in self.line_out_ids:
                if line.amount:
                    # 借方明细
                    self._create_voucher_line(line.goods_id.category_id.account_id,
                                              -line.amount, 0, vouch_id, line.goods_id, line.goods_qty, False)
                    sum_amount += line.amount

            if sum_amount:
                # 贷方明细
                self._create_voucher_line(self.buy_move_id.finance_category_id.account_id,
                                          0, -sum_amount, vouch_id, False, 0, self.partner_id)

        if len(vouch_id.line_ids) > 0:
            vouch_id.voucher_done()
            return vouch_id
        else:
            vouch_id.unlink()

    def multi_currency_rate(self):
        if self.currency_rate:
            for l in self.line_in_ids:
                l.price = l.buy_line_id.price * self.currency_rate
                l.onchange_price()
                l.cost = l.price * l.goods_qty - l.discount_amount + l.share_cost

    def buy_receipt_done(self):
        '''审核采购入库单/退货单，更新本单的付款状态/退款状态，并生成结算单和付款单'''
        self.ensure_one()
        # 报错
        self.multi_currency_rate()
        self._wrong_receipt_done()
        # 调用wh.move中审核方法，更新审核人和审核状态
        self.buy_move_id.approve_order()

        # 将收货/退货数量写入订单行
        self._line_qty_write()

        # 创建入库的会计凭证
        voucher = self.create_voucher()

        # 入库单/退货单 生成结算单
        invoice_id = self._receipt_make_invoice()
        # 采购费用产生结算单
        self._buy_amount_to_invoice()
        # 生成付款单
        money_order = False
        if self.payment:
            flag = not self.is_return and 1 or -1
            amount = flag * self.amount
            this_reconcile = flag * self.payment
            money_order = self._make_payment(invoice_id, amount, this_reconcile)
        self.write({
            'voucher_id': voucher and voucher.id,
            'invoice_id': invoice_id and invoice_id.id,
            'money_order_id': money_order and money_order.id,
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })
        if self.order_id:
            # 如果已退货也已退款，不生成新的分单
            if self.is_return and self.payment:
                return True
            #产生新的入库单时，如果已经存在草稿的入库单时，先将已经存在的草稿进行删除
            self.env['buy.receipt'].search(['&',('state', '=', 'draft'),'&',('order_id','=', self.order_id.id),('is_return', '=', False)]).unlink()                           
            return self.order_id.buy_generate_receipt()

    def buy_receipt_draft(self):
        '''反审核采购入库单/退货单，更新本单的付款状态/退款状态，并删除生成的结算单、付款单及凭证'''
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销 %s' % self._description)
        # 查找产生的付款单
        source_line = self.env['source.order.line'].search(
            [('name', '=', self.invoice_id.id)])
        for line in source_line:
            if line.money_id.state == 'done':
                line.money_id.money_order_draft()  # 反审核付款单
            # 判断付款单 源单行 是否有别的行存在
            other_source_line = []
            for s_line in line.money_id.source_ids:
                if s_line.id != line.id:
                    other_source_line.append(s_line)
            # 付款单 源单行 不存在别的行，删除付款单；否则删除付款单行，并对原付款单审核
            if not other_source_line:
                line.money_id.unlink()
            else:
                line.unlink()
                other_source_line[0].money_id.money_order_done()

        # 查找产生的结算单
        invoice_ids = self.env['money.invoice'].search(
            [('name', '=', self.invoice_id.name)])
        for invoice in invoice_ids:
            if invoice.state == 'done':
                if self.env.company.draft_invoice:
                    raise UserError('发票已收不可撤销入库')
                invoice.money_invoice_draft()
            invoice.unlink()
        # 反审核采购入库单时删除对应的入库凭证
        voucher = self.voucher_id
        if voucher.state == 'done':
            voucher.voucher_draft()
        voucher.unlink()
        self.write({
            'state': 'draft',
        })
        # 修改订单行中已执行数量
        if self.order_id:
            for line in self.line_in_ids:
                line.buy_line_id.quantity_in -= line.goods_qty
            for line in self.line_out_ids:
                if self.order_id.type == 'return':
                    line.buy_line_id.quantity_in -= line.goods_qty
                else:
                    line.buy_line_id.quantity_in += line.goods_qty
        # 调用wh.move中反审核方法，更新审核人和审核状态
        self.buy_move_id.cancel_approved_order()

    def buy_share_cost(self):
        '''入库单上的采购费用分摊到入库单明细行上'''
        self.ensure_one()
        total_amount = 0
        for line in self.line_in_ids:
            total_amount += line.amount
        cost = sum(cost_line.amount for cost_line in self.cost_line_ids)
        for line in self.line_in_ids:
            line.share_cost = cost / total_amount * line.amount
        share_cost = sum(line.share_cost for line in self.line_in_ids)
        diff_cost = cost - share_cost
        self.line_in_ids[0].share_cost = self.line_in_ids[0].share_cost + diff_cost
        return True

    def buy_to_return(self):
        '''采购入库单转化为采购退货单'''
        return_goods = {}

        return_order_draft = self.search([
            ('is_return', '=', True),
            ('origin_id', '=', self.id),
            ('state', '=', 'draft')
        ])
        if return_order_draft:
            raise UserError('采购入库单存在草稿状态的退货单！')

        return_order = self.search([
            ('is_return', '=', True),
            ('origin_id', '=', self.id),
            ('state', '=', 'done')
        ])
        for order in return_order:
            for return_line in order.line_out_ids:
                # 用产品、属性、批次做key记录已退货数量
                t_key = (return_line.goods_id.id,
                         return_line.attribute_id.id, return_line.lot_id.lot)
                if return_goods.get(t_key):
                    return_goods[t_key] += return_line.goods_qty
                else:
                    return_goods[t_key] = return_line.goods_qty
        receipt_line = []
        for line in self.line_in_ids:
            qty = line.goods_qty
            l_key = (line.goods_id.id, line.attribute_id.id, line.lot)
            if return_goods.get(l_key):
                qty = qty - return_goods[l_key]
            if qty > 0:
                dic = {
                    'goods_id': line.goods_id.id,
                    'attribute_id': line.attribute_id.id,
                    'uom_id': line.uom_id.id,
                    'warehouse_id': line.warehouse_dest_id.id,
                    'warehouse_dest_id': line.warehouse_id.id,
                    'buy_line_id': line.buy_line_id.id,
                    'goods_qty': qty,
                    'price_taxed': line.price_taxed,
                    'price': line.price,
                    'tax_rate':line.tax_rate,
                    'cost_unit': line.cost_unit,
                    'discount_rate': line.discount_rate,
                    'discount_amount': line.discount_amount,
                    'type': 'out'
                }
                receipt_line.append(dic)
        if len(receipt_line) == 0:
            raise UserError('该订单已全部退货！')

        vals = {'partner_id': self.partner_id.id,
                'is_return': True,
                'order_id': self.order_id.id,
                'origin_id': self.id,
                'origin': 'buy.receipt.return',
                'warehouse_dest_id': self.warehouse_id.id,
                'warehouse_id': self.warehouse_dest_id.id,
                'bank_account_id': self.bank_account_id.id,
                'date_due': (datetime.datetime.now()).strftime(ISODATEFORMAT),
                'date': (datetime.datetime.now()).strftime(ISODATEFORMAT),
                'line_out_ids': [(0, 0, line) for line in receipt_line],
                'discount_amount': self.discount_amount,
                }
        delivery_return = self.with_context(is_return=True).create(vals)
        view_id = self.env.ref('buy.buy_return_form').id
        name = '采购退货单'
        return {
            'name': name,
            'view_mode': 'form',
            'view_id': False,
            'views': [(view_id, 'form')],
            'res_model': 'buy.receipt',
            'type': 'ir.actions.act_window',
            'res_id': delivery_return.id,
            'target': 'current'
        }


class WhMoveLine(models.Model):
    _inherit = 'wh.move.line'

    buy_line_id = fields.Many2one('buy.order.line',
                                  '采购单行', ondelete='cascade',
                                  help='对应的采购订单行')

    def _buy_get_price_and_tax(self):
        self.tax_rate = self.env.user.company_id.import_tax_rate
        self.price_taxed = self.goods_id.cost
        order_id = self.buy_line_id and self.buy_line_id.order_id.id or self.env.context.get('order_id')
        if order_id:
            line_domain = [
                    ('order_id', '=', order_id),
                    ('goods_id', '=', self.goods_id.id)
                ]
            # 如果行有属性，添加进搜索条件
            if self.attribute_id:
                line_domain.append(('attribute_id', '=', self.attribute_id.id))
            else:
                pass
            line = self.env['buy.order.line'].search(line_domain, limit=1)
            if line:
                self.buy_line_id = line.id
                self.uos_id = line.goods_id.uos_id.id
                self.uom_id = line.uom_id.id
                self.cost_unit = line.price
                self.price = line.price
                self.price_taxed = line.price_taxed
                self.discount_rate = line.discount_rate
                self.tax_rate = line.tax_rate
                self.plan_date = line.order_id.planned_date
            else:
                raise UserError('无此商品的订单行')
    
    @api.onchange('attribute_id')
    def onchange_attribute_id(self):
        '''当订单行的商品属性变化时，计算准确的采购订单行'''
        self.ensure_one()
        if self.attribute_id:
            self._buy_get_price_and_tax()

    @api.onchange('goods_id')
    def onchange_goods_id(self):
        '''当订单行的商品变化时，带出商品上的成本价，以及公司的进项税'''
        self.ensure_one()
        if self.goods_id:
            is_return = self.env.context.get('default_is_return')
            # 如果是采购入库单行 或 采购退货单行
            if is_return is not None and \
                    ((self.type == 'in' and not is_return) or (self.type == 'out' and is_return)):
                self._buy_get_price_and_tax()

        return super(WhMoveLine, self).onchange_goods_id()
