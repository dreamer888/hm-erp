from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.addons.finance.report.report import ReportVoucher


class TestReport(TransactionCase):

    def setUp(self):
        super(TestReport, self).setUp()
        # 审核2015年12月和2016年1月的会计凭证
        self.env.ref('finance.voucher_12').voucher_done()
        self.env.ref('finance.voucher_1').voucher_done()
        self.env.ref('finance.voucher_2').voucher_done()
        self.env.ref('finance.voucher_12_1').voucher_done()

        self.period_id = self.env.ref('finance.period_201601').id
        self.period_201411 = self.env.ref('finance.period_201411')
        self.period_201512 = self.env.ref('finance.period_201512')

        ''' FIXME
        # 结转2015年12月的期间
        month_end = self.env['checkout.wizard'].create(
                       {'date':'2015-12-31',
                        'period_id':self.env.ref('finance.period_201512').id})
        month_end.button_checkout()
        '''

    def test_trail_balance(self):
        ''' 测试科目余额表 '''
        # 上一期间未结账报错
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_id}
        )
        period_201411_wizard = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201411.id})
        with self.assertRaises(UserError):
            report.create_trial_balance()
        # 结转2015年12月的期间
        month_end = self.env['checkout.wizard'].create(
            {'date': '2015-12-31'})
        month_end.onchange_period_id()
        month_end.button_checkout()
        # 正常流程
        report.create_trial_balance()
        period_201411_wizard.create_trial_balance()

        # 执行 _default_period_id
        report_default_period = self.env['create.trial.balance.wizard'].create({
        })
        last_period = self.env['create.trial.balance.wizard'].compute_last_period_id(
            report_default_period.period_id)
        if last_period and last_period.is_closed == False:  # 如果上一个期间没有闭合，则闭合
            last_period.is_closed = True
        report_default_period.create_trial_balance()

    def test_button_change_number(self):
        ''' 测试 调整累计数 弹窗'''
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，弹出 调整累计数向导 窗口
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                trial.button_change_number()
                break

    def test_change_cumulative_occurrence_wizard_default_get(self):
        ''' 测试 调整累计数 向导 default_get '''
        wizard_obj = self.env['change.cumulative.occurrence.wizard']
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，调整累计数
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                ctx = self.env.context.copy()
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                wizard_obj.with_env(env2).default_get([
                    'cumulative_occurrence_debit', 'cumulative_occurrence_credit',
                    'old_cumulative_occurrence_debit', 'old_cumulative_occurrence_credit',
                    'trial_balance_id', 'account_id'])

                # 只能调整末级科目相关的行 报错
                with self.assertRaises(UserError):
                    trial.subject_name_id.account_type = 'view'
                    env2 = self.env(self.env.cr, self.env.uid, ctx)
                    wizard_obj.with_env(env2).default_get([
                        'cumulative_occurrence_debit', 'cumulative_occurrence_credit',
                        'old_cumulative_occurrence_debit', 'old_cumulative_occurrence_credit',
                        'trial_balance_id', 'account_id'])

                # 一次只能调整一行 报错
                with self.assertRaises(UserError):
                    trial.subject_name_id.account_type = 'normal'
                    ctx['active_ids'] = [trial.id, trial.id]
                    env2 = self.env(self.env.cr, self.env.uid, ctx)
                    wizard_obj.with_env(env2).default_get([
                        'cumulative_occurrence_debit', 'cumulative_occurrence_credit',
                        'old_cumulative_occurrence_debit', 'old_cumulative_occurrence_credit',
                        'trial_balance_id', 'account_id'])

    def test_update_cumulative_occurrence(self):
        ''' 测试：update_cumulative_occurrence '''
        wizard_obj = self.env['change.cumulative.occurrence.wizard']
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，调整累计数
        for trial in self.env['trial.balance'].search([]):
            ctx = self.env.context.copy()
            fields_list = ['cumulative_occurrence_debit', 'cumulative_occurrence_credit',
                           'old_cumulative_occurrence_debit', 'old_cumulative_occurrence_credit',
                           'trial_balance_id', 'account_id']
            # costs_types not in ('in', 'out')
            if trial.subject_name_id == self.env.ref('finance.account_bank'):
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                values = wizard_obj.with_env(env2).default_get(fields_list)
                wizard = wizard_obj.with_env(env2).create(values)
                wizard.update_cumulative_occurrence()
            if trial.subject_name_id == self.env.ref('finance.account_income'):  # costs_types in ('in', 'out')
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                values = wizard_obj.with_env(env2).default_get(fields_list)
                wizard = wizard_obj.with_env(env2).create(values)
                wizard.update_cumulative_occurrence()

    def test_check_trial_balance_wizard_default_get(self):
        ''' 测试 试算平衡 向导 default_get '''
        wizard_obj = self.env['check.trial.balance.wizard']
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 创建科目余额表
        report.create_trial_balance()
        field_list = [
            "total_year_init_debit", "total_year_init_credit",
            "total_initial_balance_debit", "total_initial_balance_credit",
            "total_current_occurrence_debit", "total_current_occurrence_credit",
            "total_ending_balance_debit", "total_ending_balance_credit",
            "total_cumulative_occurrence_debit", "total_cumulative_occurrence_credit"
        ]
        # 期间 period_201512，找到叶科目 银行存款-基本户，试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                ctx = self.env.context.copy()
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                wizard_obj.with_env(env2).default_get(field_list)

        # init period
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                ctx = self.env.context.copy()
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                self.env.ref('base.main_company').start_date = '2015-12-12'
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                wizard_obj.with_env(env2).default_get(field_list)

    def test_check_trial_balance_wizard_default_get_diff_exists(self):
        ''' 测试 试算平衡 向导 default_get diff exists '''
        wizard_obj = self.env['check.trial.balance.wizard']
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 修改当期 一个凭证行的贷方金额，使贷方金额不等于借方金额
        self.env.ref('finance.voucher_12_2_credit').credit = 4999
        # 修改上期 一个凭证行的贷方金额，使贷方金额不等于借方金额
        self.env.ref('finance.voucher_12').voucher_id = '201511'
        self.env.ref('finance.voucher_line_12_credit').credit = 1000002
        # 创建科目余额表
        report.create_trial_balance()
        field_list = [
            "total_year_init_debit", "total_year_init_credit",
            "total_initial_balance_debit", "total_initial_balance_credit",
            "total_current_occurrence_debit", "total_current_occurrence_credit",
            "total_ending_balance_debit", "total_ending_balance_credit",
            "total_cumulative_occurrence_debit", "total_cumulative_occurrence_credit"
        ]
        # 期间 period_201512，找到叶科目 银行存款-基本户，试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                ctx = self.env.context.copy()
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                wizard_obj.with_env(env2).default_get(field_list)

        # init period
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                ctx = self.env.context.copy()
                ctx['active_id'] = trial.id
                ctx['active_ids'] = [trial.id]
                self.env.ref('base.main_company').start_date = '2015-12-12'
                env2 = self.env(self.env.cr, self.env.uid, ctx)
                wizard_obj.with_env(env2).default_get(field_list)

    def test_check_trial_balance(self):
        ''' 测试 试算平衡 check_trial_balance '''
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                if trial.period_id == self.period_201512:
                    trial.check_trial_balance(self.period_201512)

    def test_check_trial_balance_init_period(self):
        ''' 测试 试算平衡 check_trial_balance init period '''
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，找到叶科目 银行存款-基本户，试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                self.env.ref('base.main_company').start_date = '2015-12-12'
                if trial.period_id == trial.period_id.get_init_period():
                    trial.check_trial_balance(trial.period_id.get_init_period())

    def test_check_trial_balance_diff_exists(self):
        ''' 测试 试算平衡 check_trial_balance diff exists '''
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 修改当期 一个凭证行的贷方金额，使贷方金额不等于借方金额
        self.env.ref('finance.voucher_12_2_credit').credit = 4999
        # 修改上期 一个凭证行的贷方金额，使贷方金额不等于借方金额
        self.env.ref('finance.voucher_12').voucher_id = '201511'
        self.env.ref('finance.voucher_line_12_credit').credit = 1000002
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，init_period 试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                if trial.period_id == self.period_201512:
                    with self.assertRaises(UserError):
                        trial.check_trial_balance(self.period_201512)

    def test_check_trial_balance_diff_exists_init_period(self):
        ''' 测试 试算平衡 check_trial_balance diff exists init period '''
        report = self.env['create.trial.balance.wizard'].create(
            {'period_id': self.period_201512.id})
        # 修改当期 一个凭证行的贷方金额，使贷方金额不等于借方金额
        self.env.ref('finance.voucher_12_2_credit').credit = 4999
        # 修改上期 一个凭证行的贷方金额，使贷方金额不等于借方金额
        self.env.ref('finance.voucher_12').voucher_id = '201511'
        self.env.ref('finance.voucher_line_12_credit').credit = 1000002
        # 创建科目余额表
        report.create_trial_balance()
        # 期间 period_201512，init_period 试算平衡
        for trial in self.env['trial.balance'].search([]):
            if trial.subject_name_id.id == self.env.ref('finance.account_bank').id:
                self.env.ref('base.main_company').start_date = '2015-12-12'
                if trial.period_id == trial.period_id.get_init_period():
                    with self.assertRaises(UserError):
                        trial.check_trial_balance(trial.period_id.get_init_period())

    def test_vouchers_summary(self):
        ''' 测试总账和明细账'''
        report = self.env['create.vouchers.summary.wizard'].create(
            {'period_begin_id': self.period_id,
             'period_end_id': self.period_id,
             'subject_name_id': self.env.ref('finance.account_fund').id,
             'subject_name_end_id': self.env.ref('finance.account_fund').id,
             }
        )
        # 会计期间相同时报错
        report.period_end_id = self.env.ref('finance.period_201512')
        report.onchange_period()
        with self.assertRaises(UserError):
            report.create_general_ledger_account()
        # 上一期间未结账报错
        with self.assertRaises(UserError):
            report.create_vouchers_summary()
        with self.assertRaises(UserError):
            report.create_general_ledger_account()
        # 正常流程
        report.period_end_id = self.period_id
        # 结转2015年12月的期间
        month_end = self.env['checkout.wizard'].create(
            {'date': '2015-12-31'})
        month_end.onchange_period_id()
        month_end.button_checkout()
        report.create_vouchers_summary()
        report.create_general_ledger_account()

        report.period_end_id = self.env.ref('finance.period_201602')
        report.create_vouchers_summary()
        report.create_general_ledger_account()
        # 没有生成科目余额表的情况
        trial_balance_obj = self.env['trial.balance'].search([
            ('period_id', '=', self.env.ref('finance.period_201512').id),
            ('subject_name_id', '=', report.subject_name_id.id)])
        trial_balance_obj.unlink()
        report.create_vouchers_summary()
        report.create_general_ledger_account()

        # 执行 _default_end_period_id，_default_begin_period_id，
        # _default_subject_name_id，_default_subject_name_end_id
        report_default = self.env['create.vouchers.summary.wizard'].create({})
        report_default.create_vouchers_summary()

        # 执行 明细账 无下一期间，退出循环
        report_default = self.env['create.vouchers.summary.wizard'].create({})
        report_default.period_begin_id = self.env.ref('finance.period_201412')
        report_default.create_vouchers_summary()

    def test_vouchers_summary_onchange_period(self):
        ''' 测试总账和明细账 onchange_period '''
        report_default = self.env['create.vouchers.summary.wizard'].create({})
        report_default.period_begin_id = self.env.ref(
            'finance.period_201512').id
        report_default.period_end_id = self.env.ref('finance.period_201411').id
        report_default.onchange_period()
        report_default.create_vouchers_summary()

    def test_create_general_ledger_account(self):
        ''' 测试总账 '''
        report = self.env['create.vouchers.summary.wizard'].create(
            {'period_begin_id': self.period_id,
             'period_end_id': self.period_id,
             'subject_name_id': self.env.ref('finance.account_fund').id,
             'subject_name_end_id': self.env.ref('finance.account_fund').id,
             })
        # 当前期间已关闭
        self.period_201512.is_closed = True
        self.env.ref('finance.period_201601').is_closed = True
        report.create_general_ledger_account()
        # 执行 总账 无下一期间，退出循环
        report.period_begin_id = self.env.ref('finance.period_201412')
        report.create_general_ledger_account()

    def test_get_initial_balance(self):
        '''取得期初余额'''
        wizard = self.env['create.vouchers.summary.wizard'].create(
            {'period_begin_id': self.period_201411.id,
             'period_end_id': self.period_201411.id,
             'subject_name_id': self.env.ref('finance.account_fund').id,
             'subject_name_end_id': self.env.ref('finance.account_fund').id,
             }
        )
        wizard.get_initial_balance(self.period_201411, wizard.subject_name_id)

        # get_initial_balance period 不存在
        wizard.get_initial_balance(False, wizard.subject_name_id)

    def test_get_current_occurrence_amount(self):
        '''测试 本期的科目的 voucher_line的明细记录'''
        wizard = self.env['create.vouchers.summary.wizard'].create(
            {'period_begin_id': self.period_201512.id,
             'period_end_id': self.period_201512.id,
             'subject_name_id': self.env.ref('finance.account_cash').id,
             'subject_name_end_id': self.env.ref('finance.account_bank').id,
             })
        wizard.get_current_occurrence_amount(
            self.period_201512, self.env.ref('finance.account_bank'))

    def test_view_detail_voucher(self):
        '''在明细账上查看凭证明细按钮'''
        report = self.env['create.vouchers.summary.wizard'].create(
            {'period_begin_id': self.period_id,
             'period_end_id': self.period_id,
             'subject_name_id': self.env.ref('finance.account_fund').id,
             'subject_name_end_id': self.env.ref('finance.account_fund').id,
             })
        # 结转2015年12月的期间
        month_end = self.env['checkout.wizard'].create(
            {'date': '2015-12-31'})
        month_end.onchange_period_id()
        month_end.button_checkout()
        result = report.create_vouchers_summary()
        ids = result['domain'][0][2]
        for line in self.env['vouchers.summary'].browse(ids):
            if line.voucher_id:
                line.view_detail_voucher()

    def test_get_year_balance(self):
        '''根据期间和科目名称 计算出本期合计 和本年累计 (已经关闭的期间)'''
        wizard = self.env['create.vouchers.summary.wizard'].create(
            {'period_begin_id': self.period_201411.id,
             'period_end_id': self.period_201411.id,
             'subject_name_id': self.env.ref('finance.account_fund').id,
             'subject_name_end_id': self.env.ref('finance.account_fund').id,
             }
        )
        wizard.get_year_balance(self.period_201411, wizard.subject_name_id)
        voucher = self.env['checkout.wizard'].create({
            'date': '2015-12-31'})
        voucher.onchange_period_id()
        voucher.button_checkout()
        trial_wizard = self.env['create.vouchers.summary.wizard'].create({
            'period_begin_id': self.env.ref('finance.period_201512').id,
            'period_end_id': self.env.ref('finance.period_201601').id,
            'subject_name_id': self.env.ref('finance.account_income').id,
            'subject_name_end_id': self.env.ref('finance.account_income').id,
        })
        trial_wizard.create_vouchers_summary()

    def test_balance_sheet(self):
        ''' 测试资产负债表 '''
        report = self.env['create.balance.sheet.wizard'].create(
            {'period_id': self.period_id})

        with self.assertRaises(UserError):
            report.create_balance_sheet()
        with self.assertRaises(UserError):
            report.create_profit_statement()
        # 结转2015年12月的期间
        month_end = self.env['checkout.wizard'].create(
            {'date': '2015-12-31'})
        month_end.onchange_period_id()
        month_end.button_checkout()
        report.create_balance_sheet()
        report.create_profit_statement()
        self.env.ref('finance.account_cost').balance_directions = 'out'
        report.create_profit_statement()
        balance_sheet_objs = self.env['profit.statement'].search([])
        for balance_sheet_obj in balance_sheet_objs:
            balance_sheet_obj.cumulative_occurrence_balance_formula = ''
        report.create_profit_statement()

    def test_balance_sheet_default_period(self):
        ''' 测试资产负债表  wizard no period'''
        self.env['create.balance.sheet.wizard'].create({})

    def test_balance_sheet_compute_balance(self):
        ''' 测试资产负债表  compute balance'''
        report = self.env['create.balance.sheet.wizard'].create(
            {'period_id': self.period_id})
        self.env.ref('finance.bs_1').balance_formula = '1001'
        # 结转2015年12月的期间
        month_end = self.env['checkout.wizard'].create({'date': '2015-12-31'})

        month_end.onchange_period_id()
        month_end.button_checkout()
        report.create_balance_sheet()


class TestCheckoutWizard(TransactionCase):

    def setUp(self):
        super(TestCheckoutWizard, self).setUp()
        self.voucher_15_12 = self.env.ref('finance.voucher_12')
        self.checkout_voucher = self.env.ref('finance.voucher_12_1')
        self.period_15_12 = self.env.ref('finance.period_201512')

    def test_button_checkout(self):
        '''结账按钮,及新建wizard时的onchange'''
        checkout_obj = self.env['checkout.wizard']
        wizard = checkout_obj.create({'date': '2016-01-02'})
        # onchange 拿到会计期间
        wizard.onchange_period_id()
        self.assertTrue(wizard.period_id.name == '201601')
        # 上期间未关闭报错
        with self.assertRaises(UserError):
            wizard.button_checkout()
        wizard.date = '2015-12-31'
        wizard.onchange_period_id()
        # 本期间已结账报错
        self.period_15_12.is_closed = True
        with self.assertRaises(UserError):
            wizard.button_checkout()
        self.period_15_12.is_closed = False
        # 期间内凭证未审核报错
        with self.assertRaises(UserError):
            wizard.button_checkout()
        # 正常流程
        self.voucher_15_12.voucher_done()
        self.checkout_voucher.voucher_done()
        wizard.button_checkout()
        # 费用大于收入
        wizard.button_counter_checkout()
        self.env.ref('finance.voucher_12_2_debit').debit = 100000
        self.env.ref('finance.voucher_12_2_credit').credit = 100000
        wizard.button_checkout()
        # 检查下一个会计期间
        self.env.ref('finance.voucher_1').voucher_done()
        self.env.ref('finance.voucher_2').voucher_done()
        self.env.ref('finance.voucher_4').voucher_done()
        self.env.ref('finance.voucher_14_12').voucher_done()
        wizard.date = '2016-01-31'
        wizard.onchange_period_id()
        wizard.button_checkout()
        wizard.date = '2016-02-28'
        wizard.onchange_period_id()
        wizard.button_checkout()
        wizard.date = '2014-12-28'
        wizard.onchange_period_id()
        wizard.button_checkout()
        # 反结账时下一期间已关闭
        next_period = self.env['create.trial.balance.wizard'].compute_next_period_id(
            wizard.period_id)
        next_period.is_closed = True
        with self.assertRaises(UserError):
            wizard.button_counter_checkout()
        next_period.is_closed = False
        # 重复反结账
        wizard.button_counter_checkout()
        with self.assertRaises(UserError):
            wizard.button_counter_checkout()
        # 公司科目未配置报错
        company_pro = self.env.ref('base.main_company')
        company_pro.profit_account = False
        with self.assertRaises(UserError):
            wizard.button_checkout()
        company_pro.profit_account = self.env.ref('finance.account_profit')
        company_pro.remain_account = False
        with self.assertRaises(UserError):
            wizard.button_checkout()

    def test_button_checkout_period_month_notEuqal_12(self):
        ''' 结账按钮, 下一个期间不存在  month 不等于 12 '''
        wizard = self.env['checkout.wizard'].create({'date': '2016-05-13'})
        self.voucher_15_12.date = '2016-05-12'
        self.voucher_15_12.voucher_done()
        wizard.onchange_period_id()
        self.env.ref('finance.period_201604').is_closed = True
        wizard.button_checkout()

    def test_recreate_voucher_name(self):
        '''按用户设置重排结账会计期间凭证号（会计要求凭证号必须连续）'''
        # FIXME: 没有成功
        self.env['ir.default'].set(
            'finance.config.settings', 'defaul_auto_reset', True)
        # 结转2015年12月的期间
        wizard = self.env['checkout.wizard'].create(
            {'date': '2015-12-31'})
        self.voucher_15_12.voucher_done()
        self.checkout_voucher.voucher_done()
        wizard.button_checkout()

    def test_recreate_voucher_name_1(self):
        ''' Test: recreate_voucher_name 按年重排 '''
        wizard = self.env['checkout.wizard'].create(
            {'date': '2015-12-31'})
        self.env['ir.default'].set('finance.config.settings', 'defaul_reset_period', 'year')
        self.env['ir.default'].set('finance.config.settings', 'defaul_auto_reset', True)
        self.env['ir.default'].set('finance.config.settings', 'defaul_reset_init_number', 2)
        wizard.period_id = self.env.ref('finance.period_201512')
        self.voucher_15_12.voucher_done()
        self.checkout_voucher.voucher_done()
        wizard.button_checkout()

class TestReportVoucher(TransactionCase):
    def test_action_report(self):
        arpw = ReportVoucher
        arpw._rmb_upper(self,1000)
        arpw._rmb_format(self,1000)
        arpw._rmb_format(self,0.001)
        arpw._paginate(self,[190, 2092, 34934, 5405])


class TestReportAuxiliaryAccounting(TransactionCase):
    ''' 测试 辅助核算余额表 '''

    def setUp(self):
        super(TestReportAuxiliaryAccounting, self).setUp()
        self.voucher_15_12 = self.env.ref('finance.voucher_12')
        self.checkout_voucher = self.env.ref('finance.voucher_12_1')
        self.period_15_12 = self.env.ref('finance.period_201512')

    def test_view_voucher_line_detail(self):
        ''' 测试 辅助核算余额表 查看明细 按钮 '''
        # 创建 辅助核算项目
        auxiliary_id = self.env['auxiliary.financing'].create({
            'name': 'gooderp project',
            'code': '20160001',
            'type': 'project',
        })

        self.env.ref(
            'finance.voucher_line_12_debit').auxiliary_id = auxiliary_id.id
        self.env['report.auxiliary.accounting'].view_voucher_line_detail()
