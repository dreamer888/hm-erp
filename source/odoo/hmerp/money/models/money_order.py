##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016  唤梦科技(<http://osbzr.com>).
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

from odoo.exceptions import UserError, ValidationError

from odoo import fields, models, api
from odoo.tools import float_compare, float_is_zero, date_utils
import datetime
#from datetime import datetime


class MoneyOrder(models.Model):
    _name = 'money.order'
    _description = "收付款单"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    TYPE_SELECTION = [
        ('pay', '付款'),
        ('get', '收款'),
    ]

    @api.model
    def create(self, values):
        # 创建单据时，根据订单类型的不同，生成不同的单据编号
        if self.env.context.get('type') == 'pay':
            values.update(
                {'name': self.env['ir.sequence'].next_by_code('pay.order')})
        else:
            values.update(
                {'name': self.env['ir.sequence'].next_by_code('get.order')})

        # 创建时查找该业务伙伴是否存在 未审核 状态下的收付款单
        orders = self.env['money.order'].search([('partner_id', '=', values.get('partner_id')),
                                                 ('state', '=', 'draft'),
                                                 ('source_ids', '!=', False),
                                                 ('id', '!=', self.id)])
        if values.get('source_ids') and orders:
            raise UserError('该业务伙伴存在未确认的收/付款单，请先确认')

        return super(MoneyOrder, self).create(values)

    def write(self, values):
        # 修改时查找该业务伙伴是否存在 未审核 状态下的收付款单
        if values.get('partner_id'):
            orders = self.env['money.order'].search([('partner_id', '=', values.get('partner_id')),
                                                     ('state', '=', 'draft'),
                                                     ('id', '!=', self.id)])
            if orders:
                raise UserError('业务伙伴(%s)存在未审核的收/付款单，请先审核' %
                                orders.partner_id.name)

        return super(MoneyOrder, self).write(values)

    @api.depends('discount_amount',
                 'line_ids.amount',
                 'source_ids.this_reconcile')
    def _compute_advance_payment(self):
        """
        计算字段advance_payment（本次预收） 监控 discount_amount， source_ids.this_reconcile line_ids.amount
        对应的字段变化则 执行本方法进行重新计算。
        :return:
        """
        for mo in self:
            amount, this_reconcile = 0.0, 0.0
            for line in mo.line_ids:
                amount += line.amount
            for line in mo.source_ids:
                this_reconcile += line.this_reconcile

            if mo.type == 'get':
                mo.advance_payment = amount - this_reconcile + mo.discount_amount
            else:
                mo.advance_payment = amount - this_reconcile - mo.discount_amount

            mo.amount = amount

    @api.depends('partner_id','type')
    def _compute_currency_id(self):
        """
        取出币别
        :return:
        """
        for mo in self:
            partner_currency_id = (mo.type == 'get')                                    \
                            and mo.partner_id.c_category_id.account_id.currency_id.id \
                            or mo.partner_id.s_category_id.account_id.currency_id.id
            mo.currency_id = partner_currency_id or mo.env.user.company_id.currency_id.id

    state = fields.Selection([
        ('draft', '草稿'),
        ('done', '已完成'),
        ('cancel', '已作废'),
    ], string='状态', readonly=True, default='draft', copy=False, index=True,
        help='收/付款单状态标识，新建时状态为草稿;确认后状态为已完成')
    partner_id = fields.Many2one('partner', string='往来单位', required=True,
                                 readonly=True, ondelete='restrict',
                                 states={'draft': [('readonly', False)]},
                                 help='该单据对应的业务伙伴，单据确认时会影响他的应收应付余额')
    date = fields.Date(string='单据日期', readonly=True,
                       default=lambda self: fields.Date.context_today(self),
                       states={'draft': [('readonly', False)]},
                       help='单据创建日期')
    name = fields.Char(string='单据编号', copy=False, readonly=True,
                       help='单据编号，创建时会根据类型自动生成')
    note = fields.Text(string='备注', help='可以为该单据添加一些需要的标识信息')
    currency_id = fields.Many2one('res.currency', '币别',
                                  compute='_compute_currency_id', store=True, readonly=True,
                                  help='业务伙伴的类别科目上对应的外币币别')
    discount_amount = fields.Float(string='我方承担费用', readonly=True,
                                   states={'draft': [('readonly', False)]},
                                   digits='Amount',
                                   help='收/付款时发生的银行手续费或给业务伙伴的现金折扣。')
    discount_account_id = fields.Many2one('finance.account', '费用科目',
                                          readonly=True,
                                          domain="[('account_type','=','normal')]",
                                          states={
                                              'draft': [('readonly', False)]},
                                          help='收/付款单确认生成凭证时，手续费或折扣对应的科目')
    line_ids = fields.One2many('money.order.line', 'money_id',
                               string='收/付款单行', readonly=True,
                               states={'draft': [('readonly', False)]},
                               help='收/付款单明细行')
    source_ids = fields.One2many('source.order.line', 'money_id',
                                 string='待核销行', readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 help='收/付款单待核销行')
    type = fields.Selection(TYPE_SELECTION, string='类型',
                            default=lambda self: self.env.context.get('type'),
                            help='类型：收款单 或者 付款单')
    amount = fields.Float(string='总金额', compute='_compute_advance_payment',
                          digits='Amount',
                          store=True, readonly=True,
                          help='收/付款单行金额总和')
    advance_payment = fields.Float(string='本次预付',
                                  compute='_compute_advance_payment',
                                  digits='Amount',
                                  store=True, readonly=True,
                                  help='根据收/付款单行金额总和，原始单据行金额总和及折扣额计算得来的预收/预付款，'
                                  '值>=0')
    to_reconcile = fields.Float(string='未核销金额',
                                digits='Amount',
                                help='未核销的预收/预付款金额')
    reconciled = fields.Float(string='已核销金额',
                              digits='Amount',
                              help='已核销的预收/预付款金额')
    origin_name = fields.Char('原始单据编号',
                              help='原始单据编号')
    bank_name = fields.Char('开户行',
                            readonly=True,
                            states={'draft': [('readonly', False)]},
                            help='开户行取自业务伙伴，可修改')
    bank_num = fields.Char('银行账号',
                           readonly=True,
                           states={'draft': [('readonly', False)]},
                           help='银行账号取自业务伙伴，可修改')
    approve_uid = fields.Many2one('res.users', '确认人',
                                  copy=False, ondelete='restrict')
    approve_date = fields.Datetime('确认日期', copy=False)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    voucher_id = fields.Many2one('voucher',
                                 '对应凭证',
                                 readonly=True,
                                 ondelete='restrict',
                                 copy=False,
                                 help='收/付款单确认时生成的对应凭证')

    def create_reconcile(self):
        self.ensure_one()
        if self.env['money.invoice'].search([('partner_id','=',self.partner_id.id),
                                             ('state','=','done'),
                                             ('to_reconcile','!=',0),
                                            ],limit=1):
            if self.type == 'get':
                business_type = 'adv_pay_to_get'
            else:
                business_type = 'adv_get_to_pay' 
            recon = self.env['reconcile.order'].create({'partner_id':self.partner_id.id,
                                                        'business_type':business_type})
            recon.onchange_partner_id()
            action = {
                'name':'核销单',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'reconcile.order',
                'res_id':recon.id,
            }
            return action
        else:
            raise UserError('没有未核销结算单')

    def write_off_reset(self):
        """
        单据审核前重置计算单行上的本次核销金额
        :return:
        """
        self.ensure_one()
        if self.state != 'draft':
            raise ValueError('已确认的单据不能执行这个操作')
        for source in self.source_ids:
            source.this_reconcile = 0
        return True

    @api.onchange('date')
    def onchange_date(self):
        """
        当修改日期时，则根据context中的money的type对客户添加过滤，过滤出是供应商还是客户。
        （因为date有默认值所以这个过滤是默认触发的） 其实和date是否变化没有关系，页面加载就触发下面的逻辑
        :return:
        """
        if self.env.context.get('type') == 'get':
            return {'domain': {'partner_id': [('c_category_id', '!=', False)]}}
        else:
            return {'domain': {'partner_id': [('s_category_id', '!=', False)]}}

    def _get_source_line(self, invoice):
        """
        根据传入的invoice的对象取出对应的值 构造出 source_line的一个dict 包含source line的主要参数
        :param invoice: money_invoice对象
        :return: dict
        """

        return {
            'name': invoice.id,
            'category_id': invoice.category_id.id,
            'amount': invoice.amount,
            'date': invoice.date,
            'reconciled': invoice.reconciled,
            'to_reconcile': invoice.to_reconcile,
            'this_reconcile': invoice.to_reconcile,
            'date_due': invoice.date_due,
        }

    def _get_invoice_search_list(self):
        """
        构造出 invoice 搜索的domain
        :return:
        """
        invoice_search_list = [('partner_id', '=', self.partner_id.id),
                               ('to_reconcile', '!=', 0),
                               ('state', '=', 'done')]
        if self.env.context.get('type') == 'get':
            invoice_search_list.append(('category_id.type', '=', 'income'))
        else:  # type = 'pay':
            invoice_search_list.append(('category_id.type', '=', 'expense'))

        return invoice_search_list

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        对partner修改的监控当 partner 修改时，就对 页面相对应的字段进行修改（bank_name，bank_num，source_ids）
        :return:
        """
        if not self.partner_id:
            return {}

        self.source_ids = False
        source_lines = []
        self.bank_name = self.partner_id.bank_name
        self.bank_num = self.partner_id.bank_num

        for invoice in self.env['money.invoice'].search(self._get_invoice_search_list()):
            source_lines.append((0,0,self._get_source_line(invoice)))
        self.source_ids = source_lines

    def money_order_done(self):
        '''对收付款单的审核按钮'''
        for order in self:
            if order.state == 'done':
                raise UserError('请不要重复确认')
            if order.type == 'pay' and not order.partner_id.s_category_id.account_id:
                raise UserError('请输入供应商类别(%s)上的科目' %
                                order.partner_id.s_category_id.name)
            if order.type == 'get' and not order.partner_id.c_category_id.account_id:
                raise UserError('请输入客户类别(%s)上的科目' %
                                order.partner_id.c_category_id.name)
            if order.advance_payment < 0 and order.source_ids:
                raise UserError('本次核销金额不能大于付款金额。\n差额: %s' %
                                (order.advance_payment))

            total = 0
            for line in order.line_ids:
                rate_silent = self.env['res.currency'].get_rate_silent(
                    order.date, line.currency_id.id)
                if order.type == 'pay':  # 付款账号余额减少, 退款账号余额增加
                    decimal_amount = self.env.ref('core.decimal_amount')
                    balance = line.currency_id != self.env.user.company_id.currency_id \
                        and line.bank_id.currency_amount or line.bank_id.balance
                    if float_compare(balance, line.amount,
                                     precision_digits=decimal_amount.digits) == -1:
                        raise UserError('账户余额不足。\n账户余额:%s 付款行金额:%s' %
                                        (balance, line.amount))
                    if line.currency_id != self.env.user.company_id.currency_id:  # 外币
                        line.bank_id.currency_amount -= line.amount
                        line.bank_id.balance -= line.amount * rate_silent
                    else:
                        line.bank_id.balance -= line.amount
                else:  # 收款账号余额增加, 退款账号余额减少
                    if line.currency_id != self.env.user.company_id.currency_id:    # 外币
                        line.bank_id.currency_amount += line.amount
                        line.bank_id.balance += line.amount * rate_silent
                    else:
                        line.bank_id.balance += line.amount
                total += line.amount

            if order.type == 'pay':
                order.partner_id.payable -= total - order.discount_amount
            else:
                order.partner_id.receivable -= total + order.discount_amount

            # 更新结算单的未核销金额、已核销金额
            for source in order.source_ids:
                '''float_compare(value1,value2): return -1, 0 or 1,
                if 'value1' is lower than, equal to, or greater than 'value2' at the given precision'''
                decimal_amount = self.env.ref('core.decimal_amount')
                if float_compare(source.this_reconcile, abs(source.to_reconcile), precision_digits=decimal_amount.digits) == 1:
                    raise UserError('本次核销金额不能大于未核销金额。\n 核销金额:%s 未核销金额:%s'
                                    % (abs(source.to_reconcile), source.this_reconcile))

                source.name.to_reconcile -= source.this_reconcile
                source.name.reconciled += source.this_reconcile

                if source.this_reconcile == 0: # 如果核销行的本次付款金额为0，删除
                    source.unlink()

            # 生成凭证并审核
            if order.type == 'get':
                voucher = order.create_money_order_get_voucher(
                    order.line_ids, order.source_ids, order.partner_id, order.name, order.note or '')
            else:
                voucher = order.create_money_order_pay_voucher(
                    order.line_ids, order.source_ids, order.partner_id, order.name, order.note or '')
            voucher.voucher_done()

            return order.write({
                'to_reconcile': order.advance_payment,
                'reconciled': order.amount - order.advance_payment,
                'voucher_id': voucher.id,
                'approve_uid': self.env.uid,
                'approve_date': fields.Datetime.now(self),
                'state': 'done',
            })

    def money_order_draft(self):
        """
        收付款单反审核方法
        :return: 
        """
        for order in self:
            if order.state == 'draft':
                raise UserError('请不要重复撤销 %s' % self._description)

            # 收/付款单 存在已审核金额不为0的核销单
            total_current_reconciled = order.amount - order.advance_payment
            decimal_amount = self.env.ref('core.decimal_amount')
            if float_compare(order.reconciled, total_current_reconciled, precision_digits=decimal_amount.digits) != 0:
                raise UserError('单据已核销金额不为0，不能反审核！请检查核销单!')

            total = 0
            for line in order.line_ids:
                rate_silent = self.env['res.currency'].get_rate_silent(
                    order.date, line.currency_id.id)
                if order.type == 'pay':  # 反审核：付款账号余额增加
                    if line.currency_id != self.env.user.company_id.currency_id:  # 外币
                        line.bank_id.currency_amount += line.amount
                        line.bank_id.balance += line.amount * rate_silent
                    else:
                        line.bank_id.balance += line.amount
                else:  # 反审核：收款账号余额减少
                    balance = line.currency_id != self.env.user.company_id.currency_id \
                        and line.bank_id.currency_amount or line.bank_id.balance
                    decimal_amount = self.env.ref('core.decimal_amount')
                    if float_compare(balance, line.amount, precision_digits=decimal_amount.digits) == -1:
                        raise UserError('账户余额不足。\n 账户余额:%s 收款行金额:%s' %
                                        (balance, line.amount))
                    if line.currency_id != self.env.user.company_id.currency_id:  # 外币
                        line.bank_id.currency_amount -= line.amount
                        line.bank_id.balance -= line.amount * rate_silent
                    else:
                        line.bank_id.balance -= line.amount
                total += line.amount

            if order.type == 'pay':
                order.partner_id.payable += total - order.discount_amount
            else:
                order.partner_id.receivable += total + order.discount_amount

            for source in order.source_ids:
                source.name.to_reconcile += source.this_reconcile
                source.name.reconciled -= source.this_reconcile

            voucher = order.voucher_id
            order.write({
                'to_reconcile': 0,
                'reconciled': 0,
                'voucher_id': False,
                'approve_uid': False,
                'approve_date': False,
                'state': 'draft',
            })
            # 反审核凭证并删除
            if voucher.state == 'done':
                voucher.voucher_draft()
            voucher.unlink()
        return True

    def _prepare_vouch_line_data(self, line, name, account_id, debit, credit, voucher_id, partner_id, currency_id):
        rate_silent = currency_amount = 0
        if currency_id:
            rate_silent = self.env['res.currency'].get_rate_silent(
                self.date, currency_id)
            currency_amount = debit or credit
            debit = debit * (rate_silent or 1)
            credit = credit * (rate_silent or 1)
        return {
            'name': name,
            'account_id': account_id,
            'debit': debit,
            'credit': credit,
            'voucher_id': voucher_id,
            'partner_id': partner_id,
            'currency_id': currency_id,
            'currency_amount': currency_amount,
            'rate_silent': rate_silent or ''
        }

    def _create_voucher_line(self, line, name, account_id, debit, credit, voucher_id, partner_id, currency_id):
        line_data = self._prepare_vouch_line_data(
            line, name, account_id, debit, credit, voucher_id, partner_id, currency_id)
        voucher_line = self.env['voucher.line'].create(line_data)
        return voucher_line

    def create_money_order_get_voucher(self, line_ids, source_ids, partner, name, note):
        """
        为收款单创建凭证
        :param line_ids: 收款单明细
        :param source_ids: 没用到
        :param partner: 客户
        :param name: 收款单名称
        :return: 创建的凭证
        """
        vouch_obj = self.env['voucher'].create({'date': self.date, 'ref': '%s,%s' % (self._name, self.id)})
        # self.write({'voucher_id': vouch_obj.id})
        amount_all = 0.0
        line_data = False
        for line in line_ids:
            line_data = line
            if not line.bank_id.account_id:
                raise UserError('请配置%s的会计科目' % (line.bank_id.name))
            # 生成借方明细行
            # param: line, name, account_id, debit, credit, voucher_id, partner_id
            if line.amount:       # 可能输入金额为0的收款单用于核销尾差
                self._create_voucher_line(line,
                                        "%s %s" % (name, note),
                                        line.bank_id.account_id.id,
                                        line.amount,
                                        0,
                                        vouch_obj.id,
                                        '',
                                        line.currency_id.id
                                        )

            amount_all += line.amount
        if self.discount_amount != 0:
            # 生成借方明细行
            # param: False, name, account_id, debit, credit, voucher_id, partner_id
            self._create_voucher_line(False,
                                      "%s 现金折扣 %s" % (name, note),
                                      self.discount_account_id.id,
                                      self.discount_amount,
                                      0,
                                      vouch_obj.id,
                                      self.partner_id.id,
                                      line_data and line_data.currency_id.id or self.currency_id.id
                                      )

        if partner.c_category_id:
            partner_account_id = partner.c_category_id.account_id.id

        # 生成贷方明细行
        # param: source, name, account_id, debit, credit, voucher_id, partner_id
        if amount_all + self.discount_amount:
            self._create_voucher_line('',
                                  "%s %s" % (name, note),
                                  partner_account_id,
                                  0,
                                  amount_all + self.discount_amount,
                                  vouch_obj.id,
                                  self.partner_id.id,
                                  line_data and line.currency_id.id or self.currency_id.id
                                  )
        return vouch_obj

    def create_money_order_pay_voucher(self, line_ids, source_ids, partner, name, note):
        """
        为付款单创建凭证
        :param line_ids: 付款单明细
        :param source_ids: 没用到
        :param partner: 供应商
        :param name: 付款单名称
        :return: 创建的凭证
        """
        vouch_obj = self.env['voucher'].create({'date': self.date, 'ref': '%s,%s' % (self._name, self.id)})
        # self.write({'voucher_id': vouch_obj.id})

        amount_all = 0.0
        line_data = False
        for line in line_ids:
            line_data = line
            if not line.bank_id.account_id:
                raise UserError('请配置%s的会计科目' % (line.bank_id.name))
            # 生成贷方明细行 credit
            # param: line, name, account_id, debit, credit, voucher_id, partner_id
            if line.amount:   # 支持金额为0的付款用于核销尾差
                self._create_voucher_line(line,
                                          "%s %s" % (name, note),
                                          line.bank_id.account_id.id,
                                          0,
                                          line.amount,
                                          vouch_obj.id,
                                          '',
                                          line.currency_id.id
                                          )
            amount_all += line.amount
        partner_account_id = partner.s_category_id.account_id.id

        # 生成借方明细行 debit
        # param: source, name, account_id, debit, credit, voucher_id, partner_id
        if amount_all - self.discount_amount:
            self._create_voucher_line('',
                                  "%s %s" % (name, note),
                                  partner_account_id,
                                  amount_all - self.discount_amount,
                                  0,
                                  vouch_obj.id,
                                  self.partner_id.id,
                                  line_data and line.currency_id.id or self.currency_id.id
                                  )

        if self.discount_amount != 0:
            # 生成借方明细行 debit
            # param: False, name, account_id, debit, credit, voucher_id, partner_id
            self._create_voucher_line(line_data and line_data or False,
                                      "%s 手续费 %s" % (name, note),
                                      self.discount_account_id.id,
                                      self.discount_amount,
                                      0,
                                      vouch_obj.id,
                                      self.partner_id.id,
                                      line_data and line.currency_id.id or self.currency_id.id
                                      )
        return vouch_obj


class MoneyOrderLine(models.Model):
    _name = 'money.order.line'
    _description = '收付款单明细'

    @api.depends('bank_id')
    def _compute_currency_id(self):
        """
        获取币别
        :return: 
        """
        for mol in self:
            mol.currency_id = mol.bank_id.account_id.currency_id.id or mol.env.user.company_id.currency_id.id
            if mol.bank_id and mol.currency_id != mol.money_id.currency_id:
                raise ValidationError('结算帐户与业务伙伴币别不一致。\n 结算账户币别:%s 业务伙伴币别:%s'
                                    % (mol.currency_id.name, mol.money_id.currency_id.name))

    money_id = fields.Many2one('money.order', string='收付款单',
                               ondelete='cascade',
                               help='订单行对应的收付款单')
    bank_id = fields.Many2one('bank.account', string='结算账户',
                              required=True, ondelete='restrict',
                              help='本次收款/付款所用的计算账户，确认收付款单会修改对应账户的金额')
    amount = fields.Float(string='金额',
                          digits='Amount',
                          help='本次结算金额')
    mode_id = fields.Many2one('settle.mode', string='结算方式',
                              ondelete='restrict',
                              help='结算方式：支票、信用卡等')
    currency_id = fields.Many2one('res.currency', '币别', compute='_compute_currency_id',
                                  store=True, readonly=True,
                                  help='结算账户对应的外币币别')
    number = fields.Char(string='结算号',
                         help='本次结算号')
    note = fields.Char(string='备注',
                       help='可以为本次结算添加一些需要的标识信息')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class MoneyInvoice(models.Model):
    _name = 'money.invoice'
    _description = '结算单'
    _order = 'date DESC'

    @api.model
    def _get_category_id(self):
        cate_type = self.env.context.get('type')
        if cate_type:
            return self.env['core.category'].search([('type', '=', cate_type)])[0]
        return False

    def name_get(self):
        '''在many2one字段里有order则显示单号否则显示名称_票号'''
        res = []

        for invoice in self:
            if self.env.context.get('order'):
                res.append((invoice.id, invoice.name))
            else:
                res.append(
                    (invoice.id, invoice.bill_number and invoice.bill_number or invoice.name))
        return res

    @api.depends('date_due', 'to_reconcile')
    def compute_overdue(selfs):
        """
        计算逾期天数： 当前日期 - 到期日，< 0则显示为0；如果逾期金额为0则逾期天数也为0
        计算逾期金额： 逾期时等于未核销金额，否则为0
        :return: 逾期天数
        """
        for self in selfs:
            # 只计算未核销的
            self.overdue_days = 0
            self.overdue_amount = 0
            if self.to_reconcile and self.state=='done':
                d1 = fields.Date.context_today(self)
                d2 = self.date_due or d1
                day = (d1 - d2).days
                if day > 0:
                    self.overdue_days = day
                    self.overdue_amount = self.to_reconcile

    @api.depends('reconciled')
    def _get_sell_amount_state(self):
        for mi in self:
            if mi.reconciled:
                mi.get_amount_date = mi.write_date

    state = fields.Selection([
        ('draft', '草稿'),
        ('done', '完成')
    ], string='状态',
        default='draft', copy=False, index=True,
        help='结算单状态标识，新建时状态为草稿;确认后状态为完成')
    partner_id = fields.Many2one('partner', string='往来单位',
                                 required=True,
                                 ondelete='restrict',
                                 help='该单据对应的业务伙伴')
    name = fields.Char(string='前置单据编号', copy=False,
                       readonly=True, required=True,
                       help='该结算单编号，取自生成结算单的采购入库单和销售入库单')
    category_id = fields.Many2one('core.category', string='类别',
                                  domain="[('type', 'in', ('income','expense'))]",
                                  ondelete='restrict',
                                  default=_get_category_id,
                                  help='结算单类别：采购 或者 销售等')
    date = fields.Date(string='日期', required=True,
                       default=lambda self: fields.Date.context_today(self),
                       help='单据创建日期')
    amount = fields.Float(string='金额（含税）',
                          digits='Amount',
                          help='原始单据对应金额')
    reconciled = fields.Float(string='已核销金额', readonly=True,
                              digits='Amount',
                              help='原始单据已核销掉的金额')
    to_reconcile = fields.Float(string='未核销金额', readonly=True,
                                digits='Amount',
                                help='原始单据未核销掉的金额')
    tax_amount = fields.Float('税额',
                              digits='Amount',
                              help='对应税额')
    get_amount_date = fields.Date('最后收款日期', compute=_get_sell_amount_state,
                                 store=True, copy=False)

    auxiliary_id = fields.Many2one('auxiliary.financing', '辅助核算',
                                   help='辅助核算')
    pay_method = fields.Many2one('pay.method',
                                 string='付款方式',
                                 ondelete='restrict')
    date_due = fields.Date(string='到期日',
                           help='结算单的到期日')
    currency_id = fields.Many2one('res.currency', '外币币别',
                                  help='原始单据对应的外币币别')
    bill_number = fields.Char('纸质发票号',
                              help='纸质发票号')
    invoice_date = fields.Date('开票日期')
    is_init = fields.Boolean('是否初始化单')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    overdue_days = fields.Float('逾期天数', readonly=True,
                                compute='compute_overdue',
                                help='当前日期 - 到期日')
    overdue_amount = fields.Float('逾期金额', readonly=True,
                                  compute='compute_overdue',
                                  help='超过到期日后仍未核销的金额')
    note = fields.Char('备注',
                       help='可填入到期日计算的依据')
    handwork = fields.Boolean('手工结算')

    def money_invoice_done(self):
        """
        结算单审核方法
        :return: 
        """
        for inv in self:
            if inv.state == 'done':
                raise UserError('请不要重复确认')
            inv.reconciled = 0.0
            inv.to_reconcile = inv.amount
            inv.state = 'done'
            if inv.pay_method:
                inv.date_due = inv.pay_method.get_due_date(inv.invoice_date)
            else:
                inv.date_due = inv.partner_id.pay_method.get_due_date(inv.invoice_date)
            if inv.category_id.type == 'income':
                inv.partner_id.receivable += inv.amount
            if inv.category_id.type == 'expense':
                inv.partner_id.payable += inv.amount
            if inv.handwork:
                # 手工结算单开票日期
                inv.invoice_date = inv.date
            if inv.is_init:
                inv.bill_number = '期初余额'
                inv.invoice_date = inv.date
        return True

    def money_invoice_draft(self):
        """
        结算单反审核方法
        :return: 
        """
        for inv in self:
            if inv.state == 'draft':
                raise UserError('请不要重复撤销 %s' % self._description)
            if inv.reconciled != 0.0:
                raise UserError('已核销的结算单不允许删除')
            inv.reconciled = 0.0
            inv.to_reconcile = 0.0
            inv.state = 'draft'
            if inv.category_id.type == 'income':
                inv.partner_id.receivable -= inv.amount
            if inv.category_id.type == 'expense':
                inv.partner_id.payable -= inv.amount

    @api.model
    def create(self, values):
        """
        创建结算单时，如果公司上的‘根据发票确认应收应付’字段没有勾上，则直接审核结算单，否则不审核。
        :param values: 
        :return: 
        """
        new_id = super(MoneyInvoice, self).create(values)
        if not self.env.user.company_id.draft_invoice:
            new_id.money_invoice_done()
        return new_id

    def write(self, values):
        """
        当更新结算单到期日时，纸质发票号 相同的结算单到期日一起更新
        """
        if values.get('date_due') and self.bill_number and not self.env.context.get('other_invoice_date_due'):
            invoices = self.search([('bill_number', '=', self.bill_number)])
            for inv in invoices:
                inv.with_context({'other_invoice_date_due': True}).write({'date_due': values.get('date_due')})
        return super(MoneyInvoice, self).write(values)

    def unlink(self):
        """
        只允许删除未审核的单据
        :return: 
        """
        for invoice in self:
            if invoice.name == '.' and invoice.reconciled == 0.0:
                self.money_invoice_draft()
                continue

        return super(MoneyInvoice, self).unlink()

    def find_source_order(self):
        '''
        查看原始单据，有以下情况：销售发货单、销售退货单、采购退货单、采购入库单、
        项目、委外加工单、核销单、采购订单、固定资产、固定资产变更以及期初应收应付。
        '''
        self.ensure_one()
        code = False
        res_models = [
            'reconcile.order',
        ]
        views = [
            'money.reconcile_order_form',
        ]
        # 判断当前数据库中否存在该 model
        if self.env.get('sell.delivery') != None:
            res_models += ['sell.delivery']
            views += ['sell.sell_delivery_form']
        if self.env.get('outsource') != None:
            res_models += ['outsource']
            views += ['warehouse.outsource_form']
        if self.env.get('buy.order') != None:
            res_models += ['buy.order']
            views += ['buy.buy_order_form']
        if self.env.get('buy.receipt') != None:
            res_models += ['buy.receipt']
            views += ['buy.buy_receipt_form']
        if self.env.get('project') != None:
            res_models += ['project']
            views += ['task.project_form']
        if self.env.get('asset') != None:
            res_models += ['asset']
            views += ['asset.asset_form']
        if self.env.get('cost.order') != None:
            res_models += ['cost.order']
            views += ['account_cost.cost_order_form']
        if self.env.get('hr.expense') != None:
            res_models += ['hr.expense']
            views += ['staff_expense.hr_expense_form']
        if '固定资产变更' in self.name:
            code = self.name.replace('固定资产变更', '')
        elif '固定资产' in self.name:
            code = self.name.replace('固定资产', '')
        domain = code and [('code', '=', code)] or [('name', '=', self.name)]

        for i in range(len(res_models)):
            # 若code存在说明 model为asset，view为固定资产form视图。
            res_model = code and 'asset' or res_models[i]
            view = code and self.env.ref(
                'asset.asset_form') or self.env.ref(views[i])
            res = self.env[res_model].search(domain)
            if res:  # 如果找到res_id,则退出for循环。
                break

        if not res:
            raise UserError('没有原始单据可供查看。')

        if res_model == 'sell.delivery' and res.is_return:
            view = self.env.ref('sell.sell_return_form')
        elif res_model == 'buy.receipt' and res.is_return:
            view = self.env.ref('buy.buy_return_form')
        return {
            'view_mode': 'form',
            'view_id': False,
            'views': [(view.id, 'form')],
            'res_model': res_model,
            'type': 'ir.actions.act_window',
            'res_id': res.id,
        }


class SourceOrderLine(models.Model):
    _name = 'source.order.line'
    _description = '待核销行'

    money_id = fields.Many2one('money.order', string='收付款单',
                               ondelete='cascade',
                               help='待核销行对应的收付款单')  # 收付款单上的待核销行
    receivable_reconcile_id = fields.Many2one('reconcile.order',
                                              string='应收核销单', ondelete='cascade',
                                              help='核销单上的应收结算单明细')  # 核销单上的应收结算单明细
    payable_reconcile_id = fields.Many2one('reconcile.order',
                                           string='应付核销单', ondelete='cascade',
                                           help='核销单上的应付结算单明细')  # 核销单上的应付结算单明细
    name = fields.Many2one('money.invoice', string='发票号',
                           copy=False, required=True,
                           ondelete='cascade',
                           help='待核销行对应的结算单')
    category_id = fields.Many2one('core.category', string='类别',
                                  required=True, ondelete='restrict',
                                  help='待核销行类别：采购 或者 销售等')
    date = fields.Date(string='单据日期',
                       help='单据创建日期')
    amount = fields.Float(string='单据金额',
                          digits='Amount',
                          help='待核销行对应金额')
    reconciled = fields.Float(string='已核销金额',
                              digits='Amount',
                              help='待核销行已核销掉的金额')
    to_reconcile = fields.Float(string='未核销金额',
                                digits='Amount',
                                help='待核销行未核销掉的金额')
    this_reconcile = fields.Float(string='本次核销金额',
                                  digits='Amount',
                                  help='本次要核销掉的金额')
    invoice_date = fields.Date(string='开票日期',
                                help='待核销行开票日期',
                                related='name.invoice_date')
    date_due = fields.Date(string='到期日',
                           help='待核销行的到期日')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class ReconcileOrder(models.Model):
    _name = 'reconcile.order'
    _description = '核销单'
    _inherit = ['mail.thread']

    TYPE_SELECTION = [
        ('adv_pay_to_get', '预收冲应收'),
        ('adv_get_to_pay', '预付冲应付'),
        ('get_to_pay', '应收冲应付'),
        ('get_to_get', '应收转应收'),
        ('pay_to_pay', '应付转应付'),
    ]

    state = fields.Selection([
        ('draft', '草稿'),
        ('done', '已确认'),
        ('cancel', '已作废'),
    ], string='状态', readonly=True,
        default='draft', copy=False, index=True,
        help='核销单状态标识，新建时状态为草稿;确认后状态为已确认')
    partner_id = fields.Many2one('partner', string='往来单位', required=True,
                                 readonly=True, ondelete='restrict',
                                 states={'draft': [('readonly', False)]},
                                 help='该单据对应的业务伙伴，与业务类型一起带出待核销的明细行')
    to_partner_id = fields.Many2one('partner', string='转入往来单位',
                                    readonly=True, ondelete='restrict',
                                    states={'draft': [('readonly', False)]},
                                    help='应收转应收、应付转应付时对应的转入业务伙伴，'
                                    '订单确认时会影响该业务伙伴的应收/应付')
    advance_payment_ids = fields.One2many(
        'advance.payment', 'pay_reconcile_id',
        string='预收/付款单行', readonly=True,
        states={'draft': [('readonly', False)]},
        help='业务伙伴有预收/付款单，自动带出，用来与应收/应付款单核销')
    receivable_source_ids = fields.One2many(
        'source.order.line', 'receivable_reconcile_id',
        string='应收结算单行', readonly=True,
        states={'draft': [('readonly', False)]},
        help='业务伙伴有应收结算单，自动带出，待与预收款单核销')
    payable_source_ids = fields.One2many(
        'source.order.line', 'payable_reconcile_id',
        string='应付结算单行', readonly=True,
        states={'draft': [('readonly', False)]},
        help='业务伙伴有应付结算单，自动带出，待与预付款单核销')
    business_type = fields.Selection(TYPE_SELECTION, string='业务类型',
                                     readonly=True,
                                     states={'draft': [('readonly', False)]},
                                     help='类型：预收冲应收,预付冲应付,应收冲应付,应收转应收,应付转应付'
                                     )
    name = fields.Char(string='单据编号', copy=False, readonly=True,
                       help='单据编号，创建时会自动生成')
    date = fields.Date(string='单据日期', readonly=True,
                       default=lambda self: fields.Date.context_today(self),
                       states={'draft': [('readonly', False)]},
                       help='单据创建日期')
    note = fields.Text(string='备注',
                       help='可以为该单据添加一些需要的标识信息')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    @api.model
    def create(self, values):
        # 创建时查找该业务伙伴是否存在 未审核 状态下的核销单
        if values.get('partner_id'):
            orders = self.env['reconcile.order'].search([('partner_id', '=', values.get('partner_id')),
                                                         ('state', '=', 'draft'),
                                                         ('id', '!=', self.id),
                                                         ('business_type', '=', values.get('business_type'))])
            if orders:
                raise UserError('业务伙伴(%s)、业务类型(%s)存在未审核的核销单，请先审核' %(
                                orders.partner_id.name,dict(self.fields_get(allfields=['business_type'])['business_type']['selection'])[orders.business_type]))
        return super(ReconcileOrder, self).create(values)

    def write(self, values):
        # 写入时查找该业务伙伴是否存在 未审核 状态下的核销单
        orders = self.env['reconcile.order'].search([('partner_id', '=', (values.get('partner_id') or self.partner_id.id)),
                                                         ('state', '=', 'draft'),
                                                         ('id', '!=', self.id),
                                                         ('business_type', '=', (values.get('business_type') or self.business_type))])
        if orders:
            raise UserError('业务伙伴(%s)、业务类型(%s)存在未审核的核销单，请先审核' %(
                                orders.partner_id.name, dict(self.fields_get(allfields=['business_type'])['business_type']['selection'])[orders.business_type]))
        return super(ReconcileOrder, self).write(values)

    def _get_money_order(self, way='get'):
        """
        搜索到满足条件的预收/付款单，为one2many字段赋值构造列表
        :param way: 收/付款单的type
        :return: list
        """
        money_orders = self.env['money.order'].search(
            [('partner_id', '=', self.partner_id.id),
             ('type', '=', way),
             ('state', '=', 'done'),
             ('to_reconcile', '!=', 0)])
        result = []
        for order in money_orders:
            result.append((0, 0, {
                'name': order.id,
                'amount': order.amount,
                'date': order.date,
                'reconciled': order.reconciled,
                'to_reconcile': order.to_reconcile,
                'this_reconcile': order.to_reconcile,
            }))
        return result

    def _get_money_invoice(self, way='income'):
        """
        搜索到满足条件的money.invoice记录并且取出invoice对象 构造出one2many的

        :param way: money.invoice 中的category_id 的type
        :return:
        """
        MoneyInvoice = self.env['money.invoice'].search([
            ('category_id.type', '=', way),
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'done'),
            ('to_reconcile', '!=', 0)])
        result = []
        for invoice in MoneyInvoice:
            result.append((0, 0, {
                'name': invoice.id,
                'category_id': invoice.category_id.id,
                'amount': invoice.amount,
                'date': invoice.date,
                'reconciled': invoice.reconciled,
                'to_reconcile': invoice.to_reconcile,
                'date_due': invoice.date_due,
                'this_reconcile': invoice.to_reconcile,
            }))
        return result

    @api.onchange('partner_id', 'to_partner_id', 'business_type')
    def onchange_partner_id(self):
        """
        onchange 类型字段 当改变 客户或者转入往来单位  业务类型 自动生成 对应的
        核销单各种明细。
        :return:
        """
        if not self.partner_id or not self.business_type:
            return {}

        # 先清空之前填充的数据
        self.advance_payment_ids = None
        self.receivable_source_ids = None
        self.payable_source_ids = None

        if self.business_type == 'adv_pay_to_get':  # 预收冲应收
            self.advance_payment_ids = self._get_money_order('get')
            self.receivable_source_ids = self._get_money_invoice('income')

        if self.business_type == 'adv_get_to_pay':  # 预付冲应付
            self.advance_payment_ids = self._get_money_order('pay')
            self.payable_source_ids = self._get_money_invoice('expense')

        if self.business_type == 'get_to_pay':  # 应收冲应付
            self.receivable_source_ids = self._get_money_invoice('income')
            self.payable_source_ids = self._get_money_invoice('expense')

        if self.business_type == 'get_to_get':  # 应收转应收
            self.receivable_source_ids = self._get_money_invoice('income')
            return {'domain': {'to_partner_id': [('c_category_id', '!=', False)]}}

        if self.business_type == 'pay_to_pay':  # 应付转应付
            self.payable_source_ids = self._get_money_invoice('expense')
            return {'domain': {'to_partner_id': [('s_category_id', '!=', False)]}}

    def _get_or_pay(self, line, business_type,
                    partner_id, to_partner_id, name):
        """
        核销单 核销时 对具体核销单行进行的操作
        :param line:
        :param business_type:
        :param partner_id:
        :param to_partner_id:
        :param name:
        :return:
        """
        decimal_amount = self.env.ref('core.decimal_amount')
        if float_compare(line.this_reconcile, line.to_reconcile, precision_digits=decimal_amount.digits) == 1:
            raise UserError('核销金额不能大于未核销金额。\n核销金额:%s 未核销金额:%s' %
                            (line.this_reconcile, line.to_reconcile))
        # 更新每一行的已核销余额、未核销余额
        line.name.to_reconcile -= line.this_reconcile
        line.name.reconciled += line.this_reconcile

        # 应收转应收、应付转应付
        if business_type in ['get_to_get', 'pay_to_pay']:
            if not float_is_zero(line.this_reconcile, 2):
                # 转入业务伙伴往来增加
                self.env['money.invoice'].create({
                    'name': name,
                    'category_id': line.category_id.id,
                    'amount': line.this_reconcile,
                    'date': self.date,
                    'reconciled': 0,  # 已核销金额
                    'to_reconcile': line.this_reconcile,  # 未核销金额
                    'date_due': line.date_due,
                    'partner_id': to_partner_id.id,
                })
                # 转出业务伙伴往来减少
                to_invoice_id = self.env['money.invoice'].create({
                    'name': name,
                    'category_id': line.category_id.id,
                    'amount': -line.this_reconcile,
                    'date': self.date,
                    'date_due': line.date_due,
                    'partner_id': partner_id.id,
                })
                # 核销 转出业务伙伴 的转出金额
                to_invoice_id.to_reconcile = 0
                to_invoice_id.reconciled = -line.this_reconcile

        # 应收冲应付，应收行、应付行分别生成负的结算单，并且核销
        if business_type in ['get_to_pay']:
            if not float_is_zero(line.this_reconcile, 2):
                invoice_id = self.env['money.invoice'].create({
                    'name': name,
                    'category_id': line.category_id.id,
                    'amount': -line.this_reconcile,
                    'date': self.date,
                    'date_due': line.date_due,
                    'partner_id': partner_id.id,
                })
                # 核销 业务伙伴 的本次核销金额
                invoice_id.to_reconcile = 0
                invoice_id.reconciled = -line.this_reconcile
        return True

    def reconcile_order_done(self):
        '''核销单的审核按钮'''
        # 核销金额不能大于未核销金额
        for order in self:
            if order.state == 'done':
                raise UserError('核销单%s已确认，不能再次确认。' % order.name)
            order_reconcile, invoice_reconcile = 0, 0
            if order.business_type in ['get_to_get', 'pay_to_pay'] and order.partner_id == order.to_partner_id:
                raise UserError('业务伙伴和转入往来单位不能相同。\n业务伙伴:%s 转入往来单位:%s'
                                % (order.partner_id.name, order.to_partner_id.name))

            # 核销预收预付
            for line in order.advance_payment_ids:
                order_reconcile += line.this_reconcile
                decimal_amount = self.env.ref('core.decimal_amount')
                if float_compare(line.this_reconcile, line.to_reconcile, precision_digits=decimal_amount.digits) == 1:
                    raise UserError('核销金额不能大于未核销金额。\n核销金额:%s 未核销金额:%s' % (
                        line.this_reconcile, line.to_reconcile))

                # 更新每一行的已核销余额、未核销余额
                line.name.to_reconcile -= line.this_reconcile
                line.name.reconciled += line.this_reconcile

            for line in order.receivable_source_ids:
                invoice_reconcile += line.this_reconcile
                self._get_or_pay(line, order.business_type,
                                 order.partner_id,
                                 order.to_partner_id, order.name)
            for line in order.payable_source_ids:
                if self.business_type == 'adv_get_to_pay':
                    invoice_reconcile += line.this_reconcile
                else:
                    order_reconcile += line.this_reconcile
                self._get_or_pay(line, order.business_type,
                                 order.partner_id,
                                 order.to_partner_id, order.name)

            # 核销金额必须相同
            if order.business_type in ['adv_pay_to_get',
                                      'adv_get_to_pay', 'get_to_pay']:
                decimal_amount = self.env.ref('core.decimal_amount')
                if float_compare(order_reconcile, invoice_reconcile, precision_digits=decimal_amount.digits) != 0:
                    raise UserError('核销金额必须相同, %s 不等于 %s'
                                    % (order_reconcile, invoice_reconcile))

            order.state = 'done'
        return True

    def _get_or_pay_cancel(self, line, business_type, name):
        """
        反核销时 对具体核销单行进行的操作
        """
        # 每一行的已核销金额减少、未核销金额增加
        line.name.to_reconcile += line.this_reconcile
        line.name.reconciled -= line.this_reconcile

        # 应收转应收、应付转应付、应收冲应付，找到生成的结算单反审核并删除
        if business_type in ['get_to_get', 'pay_to_pay', 'get_to_pay']:
            invoices = self.env['money.invoice'].search([('name', '=', name)])
            for inv in invoices:
                if inv.state == 'done':
                    inv.reconciled = 0.0
                    inv.money_invoice_draft()
                inv.unlink()
        return True

    def reconcile_order_draft(self):
        ''' 核销单的反审核按钮 '''
        for order in self:
            if order.state == 'draft':
                raise UserError('核销单%s已撤销，不能再次撤销。' % order.name)
            order_reconcile, invoice_reconcile = 0, 0
            if order.business_type in ['get_to_get', 'pay_to_pay'] and order.partner_id == order.to_partner_id:
                raise UserError('业务伙伴和转入往来单位不能相同。\n业务伙伴:%s 转入往来单位:%s'
                                % (order.partner_id.name, order.to_partner_id.name))

            # 反核销预收预付
            for line in order.advance_payment_ids:
                order_reconcile += line.this_reconcile
                # 每一行的已核销余额减少、未核销余额增加
                line.name.to_reconcile += line.this_reconcile
                line.name.reconciled -= line.this_reconcile
            # 反核销应收行
            for line in order.receivable_source_ids:
                invoice_reconcile += line.this_reconcile
                self._get_or_pay_cancel(line, order.business_type, order.name)
            # 反核销应付行
            for line in order.payable_source_ids:
                if order.business_type == 'adv_get_to_pay':
                    invoice_reconcile += line.this_reconcile
                else:
                    order_reconcile += line.this_reconcile
                self._get_or_pay_cancel(line, order.business_type, order.name)

            # 反核销时，金额必须相同
            if self.business_type in ['adv_pay_to_get', 'adv_get_to_pay', 'get_to_pay']:
                decimal_amount = self.env.ref('core.decimal_amount')
                if float_compare(order_reconcile, invoice_reconcile, precision_digits=decimal_amount.digits) != 0:
                    raise UserError('反核销时，金额必须相同, %s 不等于 %s'
                                    % (order_reconcile, invoice_reconcile))

            order.state = 'draft'
        return True


class AdvancePayment(models.Model):
    _name = 'advance.payment'
    _description = '核销单预收付款行'

    pay_reconcile_id = fields.Many2one('reconcile.order',
                                       string='核销单', ondelete='cascade',
                                       help='核销单预收付款行对应的核销单')
    name = fields.Many2one('money.order', string='预收/付款单',
                           copy=False, required=True, ondelete='cascade',
                           help='核销单预收/付款行对应的预收/付款单')
    note = fields.Text('备注', related='name.note')
    date = fields.Date(string='单据日期',
                       help='单据创建日期')
    amount = fields.Float(string='单据金额',
                          digits='Amount',
                          help='预收/付款单的预收/付金额')
    reconciled = fields.Float(string='已核销金额',
                              digits='Amount',
                              help='已核销的预收/预付款金额')
    to_reconcile = fields.Float(string='未核销金额',
                                digits='Amount',
                                help='未核销的预收/预付款金额')
    this_reconcile = fields.Float(string='本次核销金额',
                                  digits='Amount',
                                  help='本次核销的预收/预付款金额')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class CostLine(models.Model):
    _name = 'cost.line'
    _description = "采购销售费用"

    @api.depends('amount', 'tax_rate')
    def _compute_tax(selfs):
        """
        计算字段根据 amount 和 tax_rate 是否变化进行判定tax 是否需要重新计算
        :return:
        """
        for self in selfs:
            self.tax = self.amount * self.tax_rate * 0.01

    partner_id = fields.Many2one('partner', '供应商', ondelete='restrict',
                                 required=True,
                                 help='采购/销售费用对应的业务伙伴')
    category_id = fields.Many2one('core.category', '类别',
                                  required=True,
                                  ondelete='restrict',
                                  help='分类：其他支出')
    amount = fields.Float('金额',
                          required=True,
                          digits='Amount',
                          help='采购/销售费用金额')
    tax_rate = fields.Float('税率(%)',
                            default=lambda self: self.env.user.company_id.import_tax_rate,
                            help='默认值取公司进项税率')
    tax = fields.Float('税额',
                       digits='Amount',
                       compute=_compute_tax,
                       help='采购/销售费用税额')
    note = fields.Char('备注',
                       help='该采购/销售费用添加的一些标识信息')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
