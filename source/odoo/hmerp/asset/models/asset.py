
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],      # 已确认
    'clean': [('readonly', True)],     # 已清理
}


class AssetCategory(models.Model):
    '''固定资产分类'''
    _name = 'asset.category'
    _description = '固定资产分类'

    # 字段，命名问题很严重
    name = fields.Char('名称', required=True)
    # 一些带到固定资产上的默认值
    account_accumulated_depreciation = fields.Many2one(
        'finance.account', '累计折旧科目', required=True)
    account_asset = fields.Many2one(
        'finance.account', '固定资产科目', required=True)
    account_depreciation = fields.Many2one(
        'finance.account', '折旧费用科目', required=True)
    depreciation_number = fields.Float('折旧期间数', required=True)
    depreciation_value = fields.Float('最终残值率%', required=True)
    clean_income = fields.Many2one(
        'finance.account', '固定资产清理收入科目', required=True)
    clean_costs = fields.Many2one(
        'finance.account', '固定资产清理成本科目', required=True)
    # 用于软删除归档
    active = fields.Boolean('启用', default=True)
    # 未来支持多公司
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class Asset(models.Model):
    _name = 'asset'
    _description = '固定资产'
    _order = "code"        # 按资产编号排序

    @api.depends('date')
    def _compute_period_id(selfs):
        ''' 根据入账日期获取期间，用于生成凭证 '''
        for self in selfs:
            self.period_id = self.env['finance.period'].get_period(self.date)

    @api.depends('cost', 'tax')
    def _get_amount(selfs):
        ''' 价税合计 '''
        for self in selfs:
            self.amount = self.cost + self.tax

    @api.depends('cost', 'depreciation_previous')
    def _get_surplus_value(selfs):
        ''' 计算固定资产原值和残值 '''
        for self in selfs:
            # 原值 = 购置成本 - （ERP系统上线前）已提折旧
            self.surplus_value = self.cost - self.depreciation_previous
            # 残值按固定资产分类上的残值比率计算
            self.depreciation_value = self.category_id.depreciation_value * self.cost / 100

    @api.depends('surplus_value', 'depreciation_value', 'depreciation_number','no_depreciation')
    def _get_cost_depreciation(selfs):
        ''' 计算每月折旧 '''
        for self in selfs:
            if self.no_depreciation == True:  # 不提折旧不要算
                self.cost_depreciation = 0
            else:                             # 原值减残值减已折旧额，再除以剩余折旧期数
                dep_his_count = 0     # 已提期数
                dep_his_amount = 0    # 已提折旧
                for l in self.line_ids:
                    dep_his_amount += l.cost_depreciation
                    dep_his_count += 1
                if dep_his_count == self.depreciation_number:
                    self.cost_depreciation = 0      # 已提完
                else:
                    self.cost_depreciation = (self.surplus_value - self.depreciation_value
                                            - dep_his_amount) \
                                            / (self.depreciation_number - dep_his_count)
    
    @api.depends('surplus_value', 'line_ids','state')
    def _get_net_value(selfs):
        ''' 计算固定资产净值 '''
        for self in selfs:
            if self.state == 'clean':       # 已清理的固定资产净值为0
                self.net_value = 0
            else:                           # 原值 - 折旧
                self.net_value = self.surplus_value - sum(
                    [l.cost_depreciation for l in self.line_ids] )

    # 字段
    code = fields.Char('编号', required="1", states=READONLY_STATES)
    name = fields.Char('名称', required=True, states=READONLY_STATES)
    category_id = fields.Many2one(
        'asset.category', '固定资产分类', ondelete='restrict', required=True, states=READONLY_STATES)
    cost = fields.Float('金额', digits='Amount', required=True, states=READONLY_STATES)
    surplus_value = fields.Float('原值', digits='Amount', store=True, compute='_get_surplus_value')

    net_value = fields.Float('净值',digits='Amount', store=True, compute='_get_net_value')
    no_depreciation = fields.Boolean('不折旧')
    depreciation_number = fields.Integer(
        '折旧期间数', required=True, states=READONLY_STATES)
    depreciation_value = fields.Float('最终残值', digits='Amount', required=True, states=READONLY_STATES)
    cost_depreciation = fields.Float('每月折旧额', digits='Amount', 
        store=True, compute='_get_cost_depreciation')
    
    state = fields.Selection([('draft', '草稿'),
                              ('done', '已确认'),
                              ('clean', '已清理')], '状态', default='draft',
                             index=True,)

    period_id = fields.Many2one(
        'finance.period',
        '会计期间',
        compute='_compute_period_id', ondelete='restrict', store=True)
    date = fields.Date('记帐日期', required=True, states=READONLY_STATES)
    tax = fields.Float('税额', digits='Amount', required=True, states=READONLY_STATES)
    amount = fields.Float('价税合计', digits='Amount', store=True, compute='_get_amount')
    partner_id = fields.Many2one('partner', '供应商', ondelete='restrict', states=READONLY_STATES,
                                 domain="[('s_category_id', '!=', False)]",
                                 help='用于记录采购固定资产时的应付账款，据此生成结算单')
    bank_account = fields.Many2one('bank.account', '结算账户', ondelete='restrict', states=READONLY_STATES,
                                   help='用于记录现金采购固定资产时的付款，据此生成其他支出单')
    is_init = fields.Boolean('初始化资产', states=READONLY_STATES,
                             help='此固定资产在ERP系统启用前就已经有折旧了')
    depreciation_previous = fields.Float('以前折旧', digits='Amount', required=True, states=READONLY_STATES)
    
    account_credit = fields.Many2one(
        'finance.account', '资产贷方科目', required=True, states=READONLY_STATES,
        help='固定资产入账时：\n 如赊购，此处为应付科目；\n 如现购，此处为资金科目；\n 如自建，此处为在建工程')
    account_asset = fields.Many2one(
        'finance.account', '固定资产科目', required=True, states=READONLY_STATES)
    account_depreciation = fields.Many2one(
        'finance.account', '折旧费用科目', required=True, states=READONLY_STATES)
    account_accumulated_depreciation = fields.Many2one(
        'finance.account', '累计折旧科目', required=True, states=READONLY_STATES)

    line_ids = fields.One2many('asset.line', 'order_id', '折旧明细行',
                               states=READONLY_STATES, copy=False)
    chang_ids = fields.One2many('chang.line', 'order_id', '变更明细行',
                                states=READONLY_STATES, copy=False)

    auxiliary_id = fields.Many2one(
        'auxiliary.financing', '辅助核算', help='辅助核算是对账务处理的一种补充,即实现更广泛的账务处理,\
        以适应企业管理和决策的需要.辅助核算一般通过核算项目来实现', ondelete='restrict')
    
    # 界面上不可见的字段
    voucher_id = fields.Many2one(
        'voucher', '对应凭证', readonly=True, ondelete='restrict', copy=False)
    money_invoice = fields.Many2one(
        'money.invoice', '对应结算单', readonly=True, ondelete='restrict', copy=False)
    other_money_order = fields.Many2one(
        'other.money.order', '对应其他应付款单', readonly=True, ondelete='restrict', copy=False)
    # 未来支持多公司
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', '固定资产编号必须唯一')
    ]

    @api.onchange('category_id')
    def onchange_category_id(self):
        '''当固定资产分类发生变化时，折旧期间数，固定资产科目，累计折旧科目，最终残值同时变化'''
        if self.category_id:
            self.depreciation_number = self.category_id.depreciation_number
            self.account_asset = self.category_id.account_asset
            self.account_accumulated_depreciation = self.category_id.account_accumulated_depreciation
            self.account_depreciation = self.category_id.account_depreciation
            self.depreciation_value = self.category_id.depreciation_value * self.cost / 100

    @api.onchange('cost')
    def onchange_cost(self):
        '''当固定资产金额发生变化时，最终残值变化'''
        if self.cost:
            self.depreciation_value = self.category_id.depreciation_value * self.cost / 100

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        '''当合作伙伴发生变化时，固定资产贷方科目变化'''
        if self.partner_id:
            self.account_credit = self.partner_id.s_category_id.account_id

    @api.onchange('bank_account')
    def onchange_bank_account(self):
        '''当结算帐户发生变化时，固定资产贷方科目变化'''
        if self.bank_account:
            self.account_credit = self.bank_account.account_id

    def _wrong_asset_done(self):
        ''' 固定资产确认入账前的验证 '''
        if self.state == 'done':
            raise UserError('请不要重复确认！')
        if self.period_id.is_closed:
            raise UserError('该会计期间(%s)已结账！不能确认' % self.period_id.name)
        if self.cost <= 0:
            raise UserError('金额必须大于0！\n金额:%s' % self.cost)
        if self.tax < 0:
            raise UserError('税额必须大于0！\n税额:%s' % self.tax)
        if self.depreciation_previous < 0:
            raise UserError('以前折旧必须大于0！\n折旧金额:%s' %
                            self.depreciation_previous)


    def _partner_generate_invoice(self):
        ''' 赊购的方式，选择往来单位时，生成结算单 '''
        categ = self.env.ref('asset.asset_expense')   # 固定资产采购
        # 创建结算单
        money_invoice = self.env['money.invoice'].create({
            'name': '固定资产' + self.code,
            'partner_id': self.partner_id.id,
            'category_id': categ and categ.id,
            'date': self.date,
            'invoice_date': self.date,
            'amount': self.amount,
            'reconciled': 0,
            'to_reconcile': self.amount,
            'date_due': fields.Date.context_today(self),
            'state': 'draft',
            'tax_amount': self.tax
        })
        self.write({'money_invoice': money_invoice.id})

        ''' 因分类上只能设置一个固定资产科目，这里要用当前固定资产的对应科目替换凭证 '''
        
        # 如未自动确认，则确认一下结算单
        if money_invoice.state != 'done':
            money_invoice.money_invoice_done()
        # 找到结算单对应的凭证行并修改科目
        chang_account = self.env['voucher.line'].search(
            [('voucher_id', '=', money_invoice.voucher_id.id),
            ('account_id', '=', categ.account_id.id)])
        chang_account.write({'account_id': self.account_asset.id})
        
        return money_invoice

    def _bank_account_generate_other_pay(self):
        ''' 现金和银行支付的方式，选择结算账户，生成其他支出单 '''
        category = self.env.ref('asset.asset')     # 借：固定资产
        other_money_order = self.with_context(type='other_pay').env['other.money.order'].create({
            'state': 'draft',
            'partner_id': self.partner_id.id,
            'date': self.date,
            'bank_id': self.bank_account.id,
        })
        self.write({'other_money_order': other_money_order.id})
        self.env['other.money.order.line'].create({
            'other_money_id': other_money_order.id,
            'amount': self.cost,
            'tax_rate': self.cost and self.tax / self.cost * 100 or 0,
            'tax_amount': self.tax,
            'category_id': category and category.id
        })

        return other_money_order

    def _construction_generate_voucher(self):
        ''' 贷方科目选择在建工程，直接生成凭证 '''
        vals = {}
        vouch_obj = self.env['voucher'].create({'date': self.date, 'ref': '%s,%s' % (self._name, self.id)})
        self.write({'voucher_id': vouch_obj.id})
        vals.update({'vouch_obj_id': vouch_obj.id, 'string': self.name, 'name': '固定资产',
                     'amount': self.amount, 'credit_account_id': self.account_credit.id,
                     'debit_account_id': self.account_asset.id, 
                     'buy_tax_amount': self.tax or 0
                     })
        self.env['money.invoice'].create_voucher_line(vals)
        vouch_obj.voucher_done()

        return vouch_obj

    def asset_done(selfs):
        ''' 确认固定资产 '''
        for self in selfs:
            self._wrong_asset_done()
            # 非初始化固定资产生成入账凭证
            if not self.is_init:
                if self.partner_id and self.partner_id.s_category_id.account_id == self.account_credit:
                    # 赊购
                    self._partner_generate_invoice()
                elif self.bank_account and self.account_credit == self.bank_account.account_id:
                    # 现金购入
                    self._bank_account_generate_other_pay()
                else:
                    # 在建工程转入
                    self._construction_generate_voucher()
            # 初始化的固定资产需要在初始化会计凭证上点击【导入固定资产】按钮

            self.state = 'done'
            return True

    def asset_draft(selfs):
        ''' 撤销确认固定资产 '''
        for self in selfs:
            if self.state == 'draft':
                raise UserError('请不要重复撤销 %s' % self._description)
            if self.line_ids:
                raise UserError('已折旧不能撤销确认！')
            if self.chang_ids:
                raise UserError('已变更不能撤销确认！')
            if self.period_id.is_closed:
                raise UserError('该会计期间(%s)已结账！不能撤销确认' % self.period_id.name)
            if self.money_invoice.reconciled != 0:
                raise UserError('固定资产已有核销，请不要撤销')

            '''删掉凭证'''
            if self.voucher_id:
                Voucher, self.voucher_id = self.voucher_id, False
                if Voucher.state == 'done':
                    Voucher.voucher_draft()
                Voucher.unlink()
            '''删掉其他应付款单'''
            if self.other_money_order:
                other_money_order, self.other_money_order = self.other_money_order, False
                if other_money_order.state == 'done':
                    other_money_order.other_money_draft()
                other_money_order.unlink()
            '''删掉结算单'''
            if self.money_invoice:
                money_invoice, self.money_invoice = self.money_invoice, False
                if money_invoice.state == 'done':
                    money_invoice.money_invoice_draft()
                money_invoice.unlink()

            self.state = 'draft'
        return True


class CreateCleanWizard(models.TransientModel):
    '''固定资产清理'''
    _name = 'create.clean.wizard'
    _description = '固定资产清理向导'

    @api.depends('date')
    def _compute_period_id(selfs):
        ''' 根据清理日期取得期间 '''
        for self in selfs:
            self.period_id = self.env['finance.period'].get_period(self.date)

    #字段
    date = fields.Date('清理日期', required=True)
    period_id = fields.Many2one(
        'finance.period',
        '会计期间',
        compute='_compute_period_id', ondelete='restrict', store=True)
    clean_cost = fields.Float('清理费用', required=True)
    residual_income = fields.Float('残值收入', required=True)
    sell_tax_amount = fields.Float('销项税额', required=True)
    bank_account = fields.Many2one('bank.account', '结算账户')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def _generate_other_get(self):
        '''按发票收入生成收入单'''
        get_category = self.env.ref('asset.asset_clean_get')
        other_money_order = self.with_context(type='other_get').env['other.money.order'].create({
            'state': 'draft',
            'partner_id': None,
            'date': self.date,
            'bank_id': self.bank_account.id,
        })
        self.env['other.money.order.line'].create({
            'other_money_id': other_money_order.id,
            'amount': self.residual_income,
            'tax_rate': self.residual_income and self.sell_tax_amount / self.residual_income * 100 or 0,
            'tax_amount': self.sell_tax_amount,
            'category_id': get_category and get_category.id
        })

    def _clean_cost_generate_other_pay(self, clean_cost):
        '''按费用生成支出单'''
        pay_category = self.env.ref('asset.asset_clean_pay')
        other_money_order = self.with_context(type='other_pay').env['other.money.order'].create({
            'state': 'draft',
            'partner_id': None,
            'date': self.date,
            'bank_id': self.bank_account.id,
        })
        self.env['other.money.order.line'].create({
            'other_money_id': other_money_order.id,
            'amount': clean_cost,
            'category_id': pay_category and pay_category.id
        })

    def _generate_voucher(self, Asset):
        ''' 生成凭证，并确认 '''
        vouch_obj = self.env['voucher'].create({'date': self.date, 'ref': '%s,%s' % (Asset._name, Asset.id)})
        depreciation2 = sum(line.cost_depreciation for line in Asset.line_ids)
        depreciation = Asset.depreciation_previous + depreciation2
        income = Asset.cost - depreciation
        Asset.write({'voucher_id': vouch_obj.id})
        '''借方行'''
        if income:
            self.env['voucher.line'].create({'voucher_id': vouch_obj.id, 'name': '清理固定资产',
                                            'debit': income, 'account_id': Asset.category_id.clean_costs.id,
                                            })
        if depreciation:
            self.env['voucher.line'].create({'voucher_id': vouch_obj.id, 'name': '清理固定资产',
                                            'debit': depreciation, 'account_id': Asset.account_accumulated_depreciation.id,
                                            })
        '''贷方行'''
        self.env['voucher.line'].create({'voucher_id': vouch_obj.id, 'name': '清理固定资产',
                                         'credit': Asset.cost, 'account_id': Asset.account_asset.id,
                                         })
        vouch_obj.voucher_done()

    def create_clean_account(selfs):
        ''' 清理固定资产 '''
        for self in selfs:
            if not self.env.context.get('active_id'):
                return
            Asset = self.env['asset'].browse(self.env.context.get('active_id'))
            Asset.no_depreciation = 1
            Asset.state = 'clean'
            # 按发票收入生成收入单
            self._generate_other_get()
            # 按费用生成支出单
            if self.clean_cost:
                self._clean_cost_generate_other_pay(self.clean_cost)
            # 生成凭证
            self._generate_voucher(Asset)


class CreateChangWizard(models.TransientModel):
    '''固定资产变更'''
    _name = 'create.chang.wizard'
    _description = '固定资产变更向导'

    @api.depends('chang_date')
    def _compute_period_id(selfs):
        ''' 根据变更日期取会计期间 '''
        for self in selfs:
            self.period_id = self.env['finance.period'].get_period(self.chang_date)

    # 字段
    chang_date = fields.Date('变更日期', required=True)
    period_id = fields.Many2one(
        'finance.period',
        '会计期间',
        compute='_compute_period_id', ondelete='restrict', store=True)
    chang_cost = fields.Float('增加金额', required=True,
                              digits='Amount')
    chang_depreciation_number = fields.Float('变更折旧期间', required=True)
    chang_tax = fields.Float(
        '增加税额', digits='Amount', required=True)
    chang_partner_id = fields.Many2one(
        'partner', '供应商', ondelete='restrict', required=True)
    change_reason = fields.Text('变更原因')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def create_chang_account(selfs):
        ''' 创建变更对应的结算单，确认应付 '''
        ''' TODO 逻辑似乎不太对，原值和折旧期的变更都会引起每月折旧的金额变化，但是已经提过的折旧差异没有处理 '''
        for self in selfs:
            if not self.env.context.get('active_id'):
                return
            Asset = self.env['asset'].browse(self.env.context.get('active_id'))
            if self.chang_cost > 0:
                chang_before_cost = Asset.cost
                chang_before_depreciation_number = Asset.depreciation_number
                Asset.cost = self.chang_cost + Asset.cost                      # 历史成本
                Asset.surplus_value = Asset.cost - Asset.depreciation_previous # 入账价值
                Asset.tax = Asset.tax + self.chang_tax                         # 税

                categ = self.env.ref('money.core_category_purchase')
                money_invoice = self.env['money.invoice'].create({
                    'name': '固定资产变更' + Asset.code,
                            'partner_id': self.chang_partner_id.id,
                            'category_id': categ.id,
                            'date': self.chang_date,
                            'amount': self.chang_cost + self.chang_tax,
                            'reconciled': 0,
                            'to_reconcile': self.chang_cost + self.chang_tax,
                            'date_due': fields.Date.context_today(self),
                            'state': 'draft',
                            'tax_amount': self.chang_tax
                })

                # 如未自动确认，则确认一下结算单
                if money_invoice.state != 'done':
                    money_invoice.money_invoice_done()
                #将分类上的资产科目替换为固定资产上的资产科目
                chang_account = self.env['voucher.line'].search(
                    [('voucher_id', '=',money_invoice.voucher_id.id),
                    ('account_id', '=', categ.account_id.id)])
                chang_account.write({'account_id': Asset.account_asset.id})
                # 记录变更历史 - 原值变更
                self.env['chang.line'].create({'date': self.chang_date, 'period_id': self.period_id.id,
                                            'chang_before': chang_before_cost,
                                            'change_reason': self.change_reason,
                                            'chang_after': Asset.cost, 'chang_name': '原值变更',
                                            'order_id': Asset.id, 'partner_id': self.chang_partner_id.id
                                            })
            Asset.depreciation_number = Asset.depreciation_number + \
                self.chang_depreciation_number                            # 折旧期数
            Asset.depreciation_value = Asset.depreciation_value + Asset.category_id.depreciation_value * \
                self.chang_cost / 100                                     # 残值
            if self.chang_depreciation_number:
                self.env['chang.line'].create({'date': self.chang_date, 'period_id': self.period_id.id,
                                            'chang_before': chang_before_depreciation_number,
                                            'change_reason': self.change_reason,
                                            'chang_after': Asset.depreciation_number, 'chang_name': '折旧期间变更',
                                            'order_id': Asset.id, 'partner_id': self.chang_partner_id.id
                                            })

        return True


class AssetLine(models.Model):
    _name = 'asset.line'
    _description = '资产折旧明细'

    @api.depends('date')
    def _compute_period_id(selfs):
        ''' 根据记账日期取会计期间 '''
        for self in selfs:
            self.period_id = self.env['finance.period'].get_period(self.date)

    # 查看固定资产卡片
    def view_asset(self):
            view = self.env.ref('asset.asset_form_readonly')
            return {
                'name': '固定资产卡片',
                'view_mode': 'form',
                'view_id': False,
                'views': [(view.id, 'form')],
                'res_model': 'asset',
                'type': 'ir.actions.act_window',
                'target':'new',
                'res_id': self.order_id.id,
            }

    order_id = fields.Many2one('asset', '资产', index=True,
                               required=True, ondelete='restrict')
    category_id = fields.Many2one(
                                'asset.category',
                                 string='固定资产分类',
                                 related='order_id.category_id',
                                 store=True )
    net_value = fields.Float('净值',digits='Amount')
    cost_depreciation = fields.Float(
        '折旧额', required=True, digits='Amount')
    no_depreciation = fields.Float('未提折旧额')
    code = fields.Char('编码')
    name = fields.Char('名称')
    date = fields.Date('记帐日期', required=True)
    period_id = fields.Many2one(
        'finance.period',
        '会计期间',
        compute='_compute_period_id', ondelete='restrict', store=True)
    auxiliary_id = fields.Many2one(
        'auxiliary.financing', '辅助核算',
        related="order_id.auxiliary_id", store=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class CreateDepreciationWizard(models.TransientModel):
    """生成每月折旧的向导 根据输入的期间"""
    _name = "create.depreciation.wizard"
    _description = '资产折旧向导'

    @api.depends('date')
    def _compute_period_id(selfs):
        '''根据输入的日期取期间'''
        for self in selfs:
            self.period_id = self.env['finance.period'].get_period(self.date)

    @api.model
    def _get_last_date(self):
        ''' 取本月的最后一天作为默认折旧日  '''
        date_now_period_id = self.env['finance.period'].get_date_now_period_id()
        if not date_now_period_id:
            raise UserError('当前日期对应的会计期间不存在，请先创建！')
        (first,last) = self.env['finance.period'].get_period_month_date_range(date_now_period_id)
        return last

    date = fields.Date('记帐日期', required=True, default=_get_last_date)
    period_id = fields.Many2one(
        'finance.period',
        '会计期间',
        compute='_compute_period_id', ondelete='restrict', store=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def _get_voucher_line(self, Asset, cost_depreciation, vouch_obj):
        ''' 借：累计折旧 '''
        res = {}
        if Asset.account_depreciation.id not in res:
            res[Asset.account_depreciation.id] = {'debit': 0}
        val = res[Asset.account_depreciation.id]
        val.update({'debit': val.get('debit') + cost_depreciation,
                    'voucher_id': vouch_obj.id,
                    'account_id': Asset.account_depreciation.id,
                    'auxiliary_id': Asset.auxiliary_id.id,
                    'name': '固定资产折旧',
                    })

        ''' 贷：费用科目 '''
        if Asset.account_accumulated_depreciation.id not in res:
            res[Asset.account_accumulated_depreciation.id] = {'credit': 0}
            val = res[Asset.account_accumulated_depreciation.id]
            val.update({'credit': val.get('credit') + cost_depreciation,
                        'voucher_id': vouch_obj.id,
                        'account_id': Asset.account_accumulated_depreciation.id,
                        'name': '固定资产折旧',
                        })
        return res

    def _generate_asset_line(self, Asset, cost_depreciation, total):
        '''生成折旧明细行'''
        AssetLine = self.env['asset.line'].create({
            'date': self.date,
            'order_id': Asset.id,
            'company_id': Asset.company_id.id,
            'period_id': self.period_id.id,
            'cost_depreciation': cost_depreciation,
            'name': Asset.name,
            'code': Asset.code,
            # 未提折旧：原值 - 已提折旧 - 本期折旧
            'no_depreciation': Asset.surplus_value - total - cost_depreciation,
            # 净值：未提折旧 + 残值
            'net_value' :      Asset.surplus_value - total - cost_depreciation + Asset.depreciation_value ,
        })
        return AssetLine

    def create_depreciation(selfs):
        ''' 资产折旧，生成凭证和折旧明细'''
        for self in selfs:
            vouch_obj = self.env['voucher'].create({'date': self.date})
            res = []
            asset_line_id_list = []
            for Asset in self.env['asset'].search([('no_depreciation', '=', False),           # 提折旧的
                                                ('state', '=', 'done'),                    # 已确认
                                                ('period_id', '!=', self.period_id.id)]):  # 从入账下月开始
                # 本期间没有折旧过，本期间晚于固定资产入账期间
                if self.period_id not in [line.period_id for line in Asset.line_ids] and \
                        self.env['finance.period'].period_compare(self.period_id, Asset.period_id) > 0:
                    # 本月折旧
                    cost_depreciation = Asset.cost_depreciation
                    # 累计折旧
                    total = sum(
                        line.cost_depreciation for line in Asset.line_ids) + Asset.depreciation_value
                    # 最后一次折旧
                    if Asset.surplus_value <= (total + cost_depreciation):
                        cost_depreciation = Asset.surplus_value - total
                        Asset.no_depreciation = 1
                    # 构造凭证明细行字典
                    res.append(self._get_voucher_line(
                        Asset, cost_depreciation, vouch_obj))

                    # 生成折旧明细行
                    asset_line_row = self._generate_asset_line(
                        Asset, cost_depreciation, total)
                    asset_line_id_list.append(asset_line_row.id)
            # 构造凭证明细行字典
            debit_line_dict, credit_line_dict = {}, {}
            for i in range(len(res)):
                for account_id, val in res[i].items():
                    # 生成借方凭证明细
                    if 'debit' in list(val.keys()):
                        auxiliary_id = val.get('auxiliary_id')
                        if (account_id, auxiliary_id) not in debit_line_dict:
                            debit_line_dict[(account_id, auxiliary_id)] = val
                        else:
                            debit_line_dict[(account_id, auxiliary_id)]['debit'] += val['debit']
                    # 生成贷方凭证明细
                    if 'credit' in list(val.keys()):
                        if account_id not in credit_line_dict:
                            credit_line_dict[account_id] = val
                        else:
                            credit_line_dict[account_id]['credit'] += val['credit']
            line_dict = dict(list(debit_line_dict.items()) + list(credit_line_dict.items()))
            for account_id, val in line_dict.items():
                self.env['voucher.line'].create(val) # 创建凭证行

            # 没有凭证行则报错
            if not vouch_obj.line_ids:
                raise UserError('本期没有需要折旧的固定资产。')
            #vouch_obj.voucher_done()

            # 界面转到本月折旧明细
            view = self.env.ref('asset.asset_line_tree')
            return {
                'view_mode': 'tree',
                'name': '资产折旧明细行',
                'views': [(view.id, 'tree')],
                'res_model': 'asset.line',
                'type': 'ir.actions.act_window',
                'target': 'main',
                'domain': [('id', 'in', asset_line_id_list)]
            }


class ChangLine(models.Model):
    _name = 'chang.line'
    _description = '资产变更明细'

    @api.depends('date')
    def _compute_period_id(selfs):
        ''' 根据变更日期取会计期间 '''
        for self in selfs:
            self.period_id = self.env['finance.period'].get_period(self.date)

    # 字段
    order_id = fields.Many2one('asset', '订单编号', index=True,
                               required=True, ondelete='cascade')
    chang_name = fields.Char('变更内容', required=True)
    date = fields.Date('记帐日期', required=True)
    period_id = fields.Many2one(
        'finance.period',
        '会计期间',
        compute='_compute_period_id', ondelete='restrict', store=True)
    chang_before = fields.Float('变更前')
    chang_after = fields.Float('变更后')
    chang_money_invoice = fields.Many2one(
        'money.invoice', '对应结算单', readonly=True, ondelete='restrict')
    partner_id = fields.Many2one('partner', '供应商')
    change_reason = fields.Text('变更原因')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

class Voucher(models.Model):
    ''' 在凭证上增加 引入固定资产 按钮逻辑 '''
    _inherit = 'voucher'

    def init_asset(selfs):
        '''删除以前引入的固定资产内容'''
        for self in selfs:
            for line in self.line_ids:
                if line.init_obj == 'asset':
                    line.unlink()

            '''引入固定资产初始化单据'''
            res = {}
            if self.env['asset'].search([('is_init', '=', True),
                                        ('state', '=', 'draft')]):
                raise UserError('有未确认的初始化固定资产')
            for Asset in self.env['asset'].search([('is_init', '=', True),
                                                ('state', '=', 'done')]):
                cost = Asset.cost
                depreciation_previous = Asset.depreciation_previous
                '''固定资产'''
                if Asset.account_asset.id not in res:
                    res[Asset.account_asset.id] = {'credit': 0, 'debit': 0}

                val = res[Asset.account_asset.id]
                val.update({'debit': val.get('debit') + cost,
                            'account_id': Asset.account_asset.id,
                            'voucher_id': self.id,
                            'init_obj': 'asset',
                            'name': '固定资产 期初'
                            })
                '''累计折旧'''
                if Asset.account_accumulated_depreciation.id not in res:
                    res[Asset.account_accumulated_depreciation.id] = {
                        'credit': 0, 'debit': 0}

                val = res[Asset.account_accumulated_depreciation.id]
                val.update({'credit': val.get('credit') + depreciation_previous,
                            'account_id': Asset.account_accumulated_depreciation.id,
                            'voucher_id': self.id,
                            'init_obj': 'asset',
                            'name': '固定资产 期初'
                            })

            for account_id, val in res.items():
                self.env['voucher.line'].create(dict(val, account_id=account_id),
                                                )
