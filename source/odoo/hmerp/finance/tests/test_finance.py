from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo import fields, models, api
from odoo.tools import float_compare, float_is_zero
import calendar


class TestVoucher(TransactionCase):

    def test_approve(self):
        '''测试审核反审核报错'''
        voucher = self.env.ref('finance.voucher_1')
        # 正常审批
        voucher.voucher_done()
        self.assertTrue(voucher.state == 'done')
        # 已审批的凭证不可以删除
        with self.assertRaises(UserError):
            voucher.unlink()
        for line in voucher.line_ids:
            with self.assertRaises(UserError):
                line.unlink()
        # 重复审批
        with self.assertRaises(UserError):
            voucher.voucher_done()
        # 正常反审批
        voucher.voucher_draft()
        self.assertTrue(voucher.state == 'draft')
        # 重复反审批
        with self.assertRaises(UserError):
            voucher.voucher_draft()
        # 会计期间已关闭时的审批
        voucher.period_id.is_closed = True
        with self.assertRaises(UserError):
            voucher.voucher_done()
        # 会计期间已关闭时的反审批
        voucher.period_id.is_closed = False
        voucher.voucher_done()
        voucher.period_id.is_closed = True
        with self.assertRaises(UserError):
            voucher.voucher_draft()

    def test_voucher_can_be_draft(self):
        '''测试反审核报错'''
        voucher = self.env.ref('finance.voucher_1')
        voucher.voucher_done()
        voucher.voucher_can_be_draft()

    def test_voucher_done_costs_types_out(self):
        '''费用类科目只能在借方记账'''
        voucher = self.env['voucher'].create({
            'date': '2017-01-01',
            'line_ids': [(0, 0, {
                'name': '收利息',  # 贷方行
                'account_id': self.env.ref('finance.small_business_chart5603002').id,
                'debit': 0,
                'credit': 1.0,
            }),
                (0, 0, {
                    'name': '收利息',  # 借方行
                    'account_id': self.env.ref('finance.account_bank').id,
                    'debit': 1.0,
                    'credit': 0,
                })]
        })
        voucher.voucher_done()

    def test_voucher_done_costs_types_in(self):
        '''收入类科目只能在贷方记账'''
        voucher = self.env['voucher'].with_context({'entry_manual':1}).create({
            'date': '2017-01-01',
            'line_ids': [(0, 0, {
                'name': '退款给客户',  # 贷方行
                'account_id': self.env.ref('finance.account_bank').id,
                'debit': 0,
                'credit': 50.0,
            }),
                (0, 0, {
                    'name': '退款给客户',  # 借方行
                    'account_id': self.env.ref('finance.account_income').id,
                    'debit': 50.0,
                    'credit': 0,
                })]
        })
        voucher.voucher_done()

    def test_restricted_account(self):
        ''' 测试受限的记账科目 '''
        account_debit = self.env.ref('finance.small_business_chart1801')
        account_debit.restricted_debit = True
        self.env.ref('finance.account_chart1002').restricted_credit = True
        account_credit = self.env.ref('finance.account_bank')

        with self.assertRaises(UserError):
            voucher = self.env['voucher'].with_context({'entry_manual':1}).create({
                'date': '2017-01-01',
                'line_ids': [(0, 0, {
                    'name': '受限科目记账',  # 贷方行
                    'account_id': account_credit.id,
                    'debit': 0,
                    'credit': 50.0,
                })]
            })
        with self.assertRaises(UserError):
            voucher = self.env['voucher'].with_context({'entry_manual':1}).create({
                'date': '2017-01-01',
                'line_ids': [(0, 0, {
                        'name': '受限科目记账',  # 借方行
                        'account_id': account_debit.id,
                        'debit': 50.0,
                        'credit': 0,
                    })]
            })
        self.env.ref('finance.voucher_1').with_context({'entry_manual':1}).write({'att_count':'15'})

    def test_line_unlink(self):
        '''测试可正常删除未审核的凭证行'''
        voucher = self.env.ref('finance.voucher_1')
        for line in voucher.line_ids:
            line.unlink()

    def test_vourcher_write(self):
        period_id = self.env.ref('finance.period_201601')
        voucher = self.env.ref('finance.voucher_1')
        voucher.state = 'done'
        voucher.period_id.is_closed = True
        with self.assertRaises(UserError):
            voucher.write({'period_id': period_id.id})
        self.env.context = dict(
            self.env.context, **{"call_module": 'checkout_wizard'})
        voucher.write({'period_id': period_id.id})

    def test_compute(self):
        '''新建凭证时计算字段加载'''
        voucher = self.env.ref('finance.voucher_1')
        self.assertTrue(voucher.period_id.name == '201601')
        self.assertTrue(voucher.amount_text == 50000.0)
        voucher.unlink()

    def test_check_balance(self):
        '''检查凭证借贷方合计平衡'''
        un_balance_voucher = self.env['voucher'].create({
            'line_ids': [(0, 0, {
                'account_id': self.env.ref('finance.account_cash').id,
                'name': '借贷方不平',
                'debit': 100,
            })]
        })
        with self.assertRaises(ValidationError):
            un_balance_voucher.voucher_done()

    def test_check_line(self):
        '''检查凭证行'''
        # 没有凭证行
        voucher_no_line = self.env['voucher'].create({
            'line_ids': False
        })
        with self.assertRaises(ValidationError):
            voucher_no_line.voucher_done()
        # 检查借贷方都为0
        voucher_zero = self.env['voucher'].create({
            'line_ids': [(0, 0, {
                'account_id': self.env.ref('finance.account_cash').id,
                'name': '借贷方全为0',
            })]
        })
        with self.assertRaises(ValidationError):
            voucher_zero.voucher_done()
        # 检查单行凭证行是否同时输入借和贷
        voucher = self.env['voucher'].create({
            'line_ids': [(0, 0, {
                'account_id': self.env.ref('finance.account_cash').id,
                'name': '借贷方同时输入',
                'debit': 100,
                'credit': 100,
            })]
        })
        with self.assertRaises(ValidationError):
            voucher.voucher_done()

    def test_voucher_line_default_get(self):
        line = self.env['voucher.line'].create({
            'account_id': self.env.ref('finance.account_cash').id,
            'name': '借贷方同时输入',
            'debit': 100,
            'credit': 100,
        })
        self.env['voucher'].with_context({'line_ids': {line.id}}).create({
            'line_ids': [(0, 0, {
                'account_id': self.env.ref('finance.account_cash').id,
                'name': '借贷方同时输入',
                'debit': 100,
                'credit': 100,
            })]
        })

    def test_default_voucher_date(self):
        voucher_obj = self.env['voucher']
        '''
        voucher_rows = self.env['voucher'].search([])
        voucher_rows.unlink()
        setting_row = self.env['finance.config.settings'].create({
            "defaul_period_domain": "can",
            "defaul_reset_init_number": 1,
            "defaul_auto_reset": True,
            "defaul_reset_period": "month",
            "defaul_voucher_date": "today", })
        setting_row.execute()
        setting_row.default_voucher_date = 'last'
        voucher_obj._default_voucher_date()
        '''
        voucher_obj.create({})

    def test_default_voucher_date_last(self):
        ''' 测试 defaul_voucher_date 等于 last '''
        voucher_obj = self.env['voucher']
        '''
        setting_row = self.env['finance.config.settings'].create({
            "defaul_period_domain": "can",
            "defaul_reset_init_number": 1,
            "defaul_auto_reset": True,
            "defaul_reset_period": "month",
            "defaul_voucher_date": "last", })
        setting_row.execute()
        '''
        self.env['ir.default'].set('finance.config.settings', 'defaul_voucher_date', 'last')
#        voucher_obj._default_voucher_date()
        voucher_obj.create({})


class TestVoucherLine(TransactionCase):
    def test_view_document(self):
        ''' Test: view document method '''
        self.env.ref('finance.voucher_line_1_debit').view_document()

    def test_post_view(self):
        ''' 只能往下级科目记账 '''
        with self.assertRaises(UserError):
            self.env.ref('finance.voucher_line_1_debit').account_id = self.env.ref('finance.account_chart1002')

class TestPeriod(TransactionCase):

    def test_get_period(self):
        period_obj = self.env['finance.period']
        # 如果对应会计期间不存在，则创建
        if not period_obj.search([('year', '=', '2100'),
                                  ('month', '=', '6')]):
            that_date = datetime.strptime('2100-06-20',"%Y-%m-%d")
            self.assertTrue(period_obj.get_period(that_date).name, '210006')
        period_obj.get_year_fist_period_id()
        period_row = period_obj.search(
            [('year', '=', '2016'), ('month', '=', '10')])
        if not period_row:
            period_row = period_obj.create({'year': '2016', 'month': '10'})
        self.assertTrue(("2016-10-01", "2016-10-31") ==
                        period_obj.get_period_month_date_range(period_row))
        period_row.is_closed = True
        with self.assertRaises(UserError):  # 得到对应时间的会计期间 ，期间已关闭
            that_date = datetime.strptime('2016-10-10',"%Y-%m-%d")
            period_obj.get_period(that_date)
        # datetime_str = datetime.now().strftime("%Y-%m-%d")
        # datetime_str_list = datetime_str.split('-')
        # period_row = self.env['finance.period'].search(
        #     [('year', '=', datetime_str_list[0])])
        # if period_row: # 在相应的年份 会计期间不存在
        #     period_row.unlink()
        # period_obj.get_year_fist_period_id()

    def test_compute_name_month_02(self):
        ''' 测试  compute_name 月份小于10 '''
        self.env['finance.period'].create({'year': '2007', 'month': '2'})

    def test_onchange_account_id(self):
        '''凭证行的科目变更影响到其他字段的可选值'''
        voucher = self.env.ref('finance.voucher_1')
        for line in voucher.line_ids:
            line.account_id = self.env.ref('finance.account_cash').id
            line.onchange_account_id()
            line.account_id = self.env.ref('finance.account_goods').id
            line.onchange_account_id()
            line.account_id = self.env.ref('finance.account_ar').id
            line.onchange_account_id()
            line.account_id = self.env.ref('finance.account_ap').id
            line.onchange_account_id()
            line.account_id = self.env.ref(
                'finance.small_business_chart2211004').id
            line.onchange_account_id()
            line.account_id = self.env.ref('finance.account_goods').id
            line.account_id.auxiliary_financing = 'goods'
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'customer'
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'supplier'
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'project'
            line.onchange_account_id()

    def test_period_compare(self):
        """测试会计期间比较的 代码 有三种情况 大于 小于 等于"""
        period_id = self.env.ref('finance.period_201601')
        last_period_id = self.env.ref('finance.period_201512')
        self.env['finance.period'].period_compare(period_id, period_id)
        self.env['finance.period'].period_compare(last_period_id, period_id)

'''
class TestFinanceConfigWizard (TransactionCase):

    def test_default(self):
        voucher_date_setting = self.env['finance.config.settings'].set_default_voucher_date(
        )
        period_domain_setting = self.env['finance.config.settings'].set_default_period_domain(
        )
        auto_reset_setting = self.env['finance.config.settings'].set_default_auto_reset(
        )
        reset_period_setting = self.env['finance.config.settings'].set_default_reset_period(
        )
        reset_init_number_setting = self.env['finance.config.settings'].set_default_reset_init_number(
        )
'''


class TestFinanceAccount(TransactionCase):

    def setUp(self):
        super(TestFinanceAccount, self).setUp()
        self.cash = self.env.ref('finance.account_cash')

    def test_name_get(self):
        name = self.cash.name_get()
        real_name = '%s %s' % (self.cash.code, self.cash.name)
        self.assertTrue(name[0][1] == real_name)

    # def test_name_get_in_voucher(self):
    #     """仅在凭证界面选择科目时显示出余额"""
    #     voucher = self.env.ref('finance.voucher_1')
    #     self.env['voucher.line'].create({
    #         'voucher_id': voucher.id,
    #         'name': u'测试科目显示出余额',
    #         'account_id': self.cash.with_context({'show_balance': True}).id,    # 给该字段传context没有成功
    #     })
    #     name = self.cash.name_get()
    #     real_name = '%s %s %s' % (self.cash.code, self.cash.name, self.cash.balance)
    #     self.assertTrue(name[0][1] == real_name)

    def test_name_search(self):
        '''会计科目按名字和编号搜索'''
        result = self.env['finance.account'].name_search('库存现金')
        real_result = [(self.cash.id,
                        self.cash.code + ' ' + self.cash.name)]

        self.assertEqual(result, real_result)

        # 搜索输入的是编号 code 1001
        result1 = self.env['finance.account'].name_search('1001')
        real_result1 = [(self.cash.id, self.cash.code + ' ' + self.cash.name)]
        self.assertEqual(result1, real_result1)

    def test_get_smallest_code_account(self):
        account = self.env['finance.account']
        account.get_smallest_code_account()

    def test_get_max_code_account(self):
        account = self.env['finance.account']
        account.get_max_code_account()

    def test_compute_balance(self):
        """计算会计科目的当前余额"""
        self.cash.compute_balance()
        self.cash.get_balance()
        self.assertEqual(self.cash.balance, 0)

    def test_unlink(self):
        ''' 测试删除科目 '''
        # 界面上删除预设科目报错
        with self.assertRaises(UserError):
            self.cash.with_context({'modify_from_webclient':1}).unlink()
        # 记过账的不能删除
        with self.assertRaises(UserError):
            self.env.ref('finance.account_bank').unlink()
        # 有下级科目的不能删除
        with self.assertRaises(UserError):
            self.env.ref('finance.account_chart1002').unlink()
        # 下级科目删光了就把上级科目改为可记账的科目
        self.env.ref('finance.small_business_chart5603').child_ids.unlink()

    def test_write(self):
        ''' 测试删除科目 '''
        # 界面上修改预设科目报错
        with self.assertRaises(UserError):
            self.cash.source = 'init'
            self.cash.with_context({'modify_from_webclient': 1}).write({'source': 'init'})
        # 界面上记过账科目不能修改
        account_bank = self.env.ref('finance.account_bank')
        with self.assertRaises(UserError):
            account_bank.source = ''
            account_bank.with_context({'modify_from_webclient': 1}).write({'source': 'init'})
    def test_add_child(self):
        ''' 测试增加子科目 '''
        # 末级科目增加子科目
        self.cash.button_add_child()
        income = self.env.ref('finance.account_income')
        wizard = self.env['wizard.account.add.child'].with_context(
            {'active_id': income.id}
            ).create({
            'account_code': '01',
            'account_name': '纸币',
        })
        wizard.create_account()
        # 非末级科目增加子科目
        wizard = self.env['wizard.account.add.child'].with_context(
            {'active_id':self.env.ref('finance.small_business_chart1701').id}).create({
            'account_code': '08',
            'account_name': '',
        })
        wizard.create_account()
        # 修改下级编码
        wizard.account_code = '02'
        wizard._onchange_account_code()
        # 必须是数字
        wizard.account_code = '02a'
        wizard._onchange_account_code()
        # 必须是2位
        wizard.account_code = '021'
        wizard._onchange_account_code()

        # 选择的科目层级已经是最低层级科目了，不能建立在它下面建立下级科目！ 报错
        self.env['ir.default'].set('finance.config.settings', 'defaul_account_hierarchy_level', '2')
        business_chart170108 = self.env['finance.account'].search([('code', '=', '170108')])
        with self.assertRaises(UserError):
            wizard = self.env['wizard.account.add.child'].with_context({'active_id': business_chart170108.id}). \
                create({
                'account_code': '01',
                'account_name': 'test'
            })
            wizard.create_account()

    def test_add_child_multi(self):
        with self.assertRaises(UserError):
            wizard = self.env['wizard.account.add.child'].with_context(
                {'active_ids':[self.cash.id,
                            self.env.ref('finance.small_business_chart1701').id]}
                ).create({
                'account_code':'01',
                'account_name':'纸币',
            })

class TestVoucherTemplateWizard(TransactionCase):
    def setUp(self):
        super(TestVoucherTemplateWizard, self).setUp()
        self.voucher = self.env.ref('finance.voucher_1')
        self.voucher_template_wizard = self.env['voucher.template.wizard'].create({
            'name': '测试模板', 'voucher_id': self.voucher.id,
        })

    def test_save_as_template(self):
        """凭证模板相关功能"""
        self.voucher_template_wizard.save_as_template()
        self.voucher_template_wizard.is_change_old_template = True
        old_template_id = self.env['voucher.template'].search(
            [])[0].id if self.env['voucher.template'].search([]) else False
        self.voucher_template_wizard.old_template_id = old_template_id
        self.voucher_template_wizard.save_as_template()

    def test_onchange_template_id(self):
        """凭证上模板字段的onchange"""
        old_template_id = self.env['voucher.template'].search([])[0].id if self.env[
            'voucher.template'].search([]) else False
        self.voucher.template_id = old_template_id
        self.voucher.onchange_template_id()


class TestVoucherTemplateLine(TransactionCase):
    def setUp(self):
        super(TestVoucherTemplateLine, self).setUp()
        self.voucher = self.env.ref('finance.voucher_1')
        self.voucher_template_wizard = self.env['voucher.template.wizard'].create({
            'name': '测试模板', 'voucher_id': self.voucher.id,
        })

    def test_onchange_account_id(self):
        """ 凭证模板行上会计科目字段的onchange测试 """
        self.voucher_template_wizard.save_as_template()
        template = self.env['voucher.template'].search([])[0] if self.env[
            'voucher.template'].search([]) else False
        for line in template.line_ids:
            # 会计科目不存在
            line.account_id = False
            line.onchange_account_id()

            line.account_id = self.env.ref('finance.small_business_chart1403').id
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'goods'
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'customer'
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'supplier'
            line.onchange_account_id()
            line.account_id.auxiliary_financing = 'project'
            line.onchange_account_id()
            break

class TestCheckoutWizard(TransactionCase):
    def setUp(self):
        super(TestCheckoutWizard, self).setUp()

    def test_recreate_voucher_name(self):
        ''' 测试 按用户设置重排结账会计期间凭证号（会计要求凭证号必须连续） '''
        checkout_wizard_obj = self.env['checkout.wizard']
        period_id = self.env.ref('finance.period_201601')
        last_period_id = self.env.ref('finance.period_201512')

        # 按月 重排结账会计期间凭证号
        setting_row_month = self.env['finance.config.settings'].create({"defaul_period_domain": "can",
                                                                        "defaul_reset_init_number": 1,
                                                                        "defaul_auto_reset": True,
                                                                        "defaul_voucher_date": "today"})
        setting_row_month.execute()
        checkout_wizard_obj.recreate_voucher_name(last_period_id)

        # 按年 重排结账会计期间凭证号
        setting_row_year = self.env['finance.config.settings'].create({"defaul_period_domain": "can",
                                                                       "defaul_reset_init_number": 1,
                                                                       "defaul_auto_reset": True,
                                                                       "defaul_reset_period": "year",
                                                                       "defaul_voucher_date": "today"})
        setting_row_year.execute()
        # 按年重置 上一个期间存在 但未结账
        with self.assertRaises(UserError):
            checkout_wizard_obj.recreate_voucher_name(period_id)

        # 按年重置 上一个期间存在 已结账 两个期间的年相同
        last_period_id.is_closed = True
        checkout_wizard_obj.recreate_voucher_name(period_id)
        # 按年重置 上一个期间存在 已结账 两个期间的年不相同
        period_id = self.env.ref('finance.period_201603')
        last_period_id = self.env.ref('finance.period_201602')
        self.env.ref('finance.period_201601').is_closed = True
        self.env.ref('finance.period_201512').is_closed = True
        last_period_id.is_closed = True
        checkout_wizard_obj.recreate_voucher_name(period_id)

        # 按年重置 上一个期间不存在
        period_id = self.env.ref('finance.period_201411')
        checkout_wizard_obj.recreate_voucher_name(period_id)

    def test_recreate_voucher_name_unEqual_nextVoucherName(self):
        ''' 测试 按月重排结账会计期间凭证号  凭证号不连续,更新凭证号 '''
        checkout_wizard_obj = self.env['checkout.wizard']
        period_id = self.env.ref('finance.period_201601')

        # 按月 重排结账会计期间凭证号
        setting_row_month = self.env['finance.config.settings'].create({"defaul_period_domain": "can",
                                                                        "defaul_reset_init_number": 1,
                                                                        "defaul_auto_reset": True,
                                                                        "defaul_voucher_date": "today"})
        setting_row_month.execute()
        self.env.ref('finance.period_201512').is_closed = True
        checkout_wizard_obj.recreate_voucher_name(period_id)

    def test_get_last_date(self):
        ''' Test: _get_last_date '''
        datetime_str_list = datetime.now().strftime("%Y-%m-%d").split('-')
        day = calendar.monthrange(int(datetime_str_list[0]), int(datetime_str_list[1]))

        c_w = self.env['checkout.wizard'].create({})
        self.assertEqual(c_w.date.strftime("%Y-%m-%d"),
                         '-'.join([datetime_str_list[0], datetime_str_list[1], str(day[1])]))


class TestMonthProductCost(TransactionCase):

    def setUp(self):
        super(TestMonthProductCost, self).setUp()
        self.period_id = self.env.ref('finance.period_201601')

    def test_generate_issue_cost(self):
        """本月成本结算 相关逻辑的测试"""
        checkout_wizard_row = self.env['checkout.wizard'].create(
            {'date': '2016-01-31', 'period_id': self.period_id.id})
        with self.assertRaises(UserError):
            checkout_wizard_row.button_checkout()
