from datetime import datetime

from odoo import fields, models, api
from odoo.tools import float_is_zero
from odoo.exceptions import UserError, ValidationError


class Partner(models.Model):
    '''查看业务伙伴对账单'''
    _inherit = 'partner'

    def _init_source_create(self, name, partner_id, category_id, is_init, date,
                            currency_id,
                            amount, reconciled, to_reconcile, date_due, state):
        if not float_is_zero(amount, 2):
            return self.env['money.invoice'].create({
                'name': name,
                'partner_id': partner_id,
                'category_id': category_id,
                'is_init': is_init,
                'currency_id': currency_id,
                'date': date,
                'amount': amount,
                'reconciled': reconciled,
                'to_reconcile': to_reconcile,
                'date_due': date_due,
                'state': state,
            })

    def _set_receivable_init(self):
        self.ensure_one()
        # 如果有前期初值，删掉已前的单据
        money_invoice_id = self.env['money.invoice'].search([
            ('partner_id', '=', self.id),
            ('name','=','期初应收余额'),
            ('is_init', '=', True)])
        if money_invoice_id:
            if money_invoice_id.state == 'done':
                money_invoice_id.money_invoice_draft()
            money_invoice_id.unlink()
        if self.receivable_init:
            # 创建结算单
            categ = self.env.ref('money.core_category_sale')
            self._init_source_create("期初应收余额", self.id, categ.id, True,
                                     self.env.user.company_id.start_date,
                                     self.c_category_id.account_id.currency_id.id,
                                     self.receivable_init, 0,
                                     self.receivable_init, self.env.user.company_id.start_date, 'draft')

    def _set_payable_init(self):
        self.ensure_one()
        # 如果有前期初值，删掉已前的单据
        money_invoice_id = self.env['money.invoice'].search([
            ('partner_id', '=', self.id),
            ('name','=','期初应付余额'),
            ('is_init', '=', True)])
        if money_invoice_id:
            money_invoice_id.money_invoice_draft()
            money_invoice_id.unlink()
        if self.payable_init:
            # 创建结算单
            categ = self.env.ref('money.core_category_purchase')
            self._init_source_create("期初应付余额", self.id, categ.id, True,
                                     self.env.user.company_id.start_date,
                                     self.s_category_id.account_id.currency_id.id,
                                     self.payable_init, 0,
                                     self.payable_init, self.env.user.company_id.start_date, 'draft')

    receivable_init = fields.Float(u'应收期初',
                                   digits='Amount',
                                   copy=False,
                                   inverse=_set_receivable_init,
                                   help=u'客户的应收期初余额')
    payable_init = fields.Float(u'应付期初',
                                digits='Amount',
                                copy=False,
                                inverse=_set_payable_init,
                                help=u'供应商的应付期初余额')
    invoice_ids = fields.One2many('money.invoice', 'partner_id', '未清结算单',
                                  domain=[('to_reconcile','>',0),('state','=','done'),('date_due','<=',datetime.today().date())])
    money_ids = fields.One2many('money.order', 'partner_id', '未清付款',
                                  domain=[('to_reconcile','>',0),('state','=','done')])
    amount_due = fields.Float('到期余额',compute='_compute_amount_due')

    def _compute_amount_due(self):
        for p in self:
            p.amount_due = 0
            p.amount_due += sum([i.to_reconcile for i in p.invoice_ids])
            p.amount_due -= sum([m.to_reconcile for m in p.money_ids])
            p.amount_due = round(p.amount_due,2)

    def partner_statements(self):
        """
        调用这个方法弹出 业务伙伴对账单向导
        :return:
        """
        self.ensure_one()
        ctx = {'default_partner_id': self.id}
        # 既是客户又是供应商的业务伙伴，根据是在客户还是供应商界面点击的 查看对账单 按钮，显示不同的明细
        if self.c_category_id.type == 'customer' and self.env.context.get('is_customer_view'):
            view = self.env.ref('money.customer_statements_report_wizard_form')
            ctx.update({'default_customer': True})
        else:
            view = self.env.ref('money.partner_statements_report_wizard_form')
            ctx.update({'default_supplier': True})

        return {
            'name': u'业务伙伴对账单向导',
            'view_mode': 'form',
            'view_id': False,
            'views': [(view.id, 'form')],
            'res_model': 'partner.statements.report.wizard',
            'type': 'ir.actions.act_window',
            'context': ctx,
            'target': 'new',
        }

    def action_view_money_invoice(self):
        self.ensure_one()
        act = self.env.ref('money.action_view_money_invoice').read([])[0]
        act.update({'domain': [('partner_id', '=', self.id)]})
        act.update({'context': {'search_default_to_reconcile': '1'}})
        return act


class BankAccount(models.Model):
    '''查看账户对账单'''
    _inherit = 'bank.account'

    def _set_init_balance(self):
        """
        如果  init_balance 字段里面有值则 进行 一系列的操作。
        :return:
        """
        self.ensure_one()
        start_date = self.env.user.company_id.start_date
        start_date_period_id = self.env['finance.period'].search_period(start_date)
        if self.init_balance and start_date_period_id.is_closed:
            raise UserError(u'初始化期间(%s)已结账！' % start_date_period_id.name)
        # 如果有前期初值，删掉已前的单据
        other_money_id = self.env['other.money.order'].search([
            ('bank_id', '=', self.id),
            ('is_init', '=', True)])
        if other_money_id:
            other_money_id.other_money_draft()
            other_money_id.unlink()
        if self.init_balance:
            # 资金期初 生成 其他收入
            other_money_init = self.with_context(type='other_get').env['other.money.order'].create({
                'bank_id': self.id,
                'date': self.env.user.company_id.start_date,
                'is_init': True,
                'line_ids': [(0, 0, {
                    'category_id': self.env.ref('money.core_category_init').id,
                    'amount': self.init_balance,
                    'tax_rate': 0,
                    'tax_amount': 0,
                })],
                'state': 'draft',
                'currency_amount': self.currency_amount,
            })
            # 审核 其他收入单
            other_money_init.other_money_done()


    init_balance = fields.Float(u'期初',
                                digits='Amount',
                                inverse=_set_init_balance,
                                help=u'资金的期初余额')

    def bank_statements(self):
        """
        账户对账单向导 调用这个方法弹出 账户对账单向导
        :return:
        """
        self.ensure_one()
        view = self.env.ref('money.bank_statements_report_wizard_form')

        return {
            'name': u'账户对账单向导',
            'view_mode': 'form',
            'view_id': False,
            'views': [(view.id, 'form')],
            'res_model': 'bank.statements.report.wizard',
            'type': 'ir.actions.act_window',
            'context': {'default_bank_id': self.id},
            'target': 'new',
        }
