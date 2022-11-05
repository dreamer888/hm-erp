from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class TestStaff(TransactionCase):

    def test_get_image(self):
        '''拿到用户头像,职位的onchange'''
        user_lucy = self.env['res.users'].create({
            'name': 'Lucy',
            'login': 'lucy@osbzr.com',
        })
        staff_pro = self.env['staff'].create({
            'identification_id': 111111,
            'work_phone': 12345678901,
            'work_email': 'lucy@osbzr.com',
            'name': 'Lucy',
            'code': 'lucy',
            'type': 'member',
            'user_id': user_lucy.id,
            'job_id': self.env.ref('staff.staff_job_1').id})
        staff_pro.onchange_job_id()

    def test_staff_contract_over_date(self):
        '''测试：员工合同到期，发送邮件给员工 和 部门经理（如果存在）'''

        job = self.browse_ref('staff.ir_cron_module_remind_contract_over_date')
        job.interval_type = 'minutes'
        job.nextcall = (datetime.now() + timedelta(hours=8)
                        ).strftime('%Y-%m-%d %H:%M:%S')
        job.doall = True
        # not staff.contract_ids
        self.env['staff'].staff_contract_over_date()

        # has staff.contract_ids but no apartment manager
        staff_lily = self.env.ref('staff.lili')
        staff_lily.work_email = 'lili@sina.com.cn'
        staff_lily.contract_ids.create({'staff_id': staff_lily.id,
                                        'basic_wage': 123456,
                                        'over_date': datetime.now().strftime("%Y-%m-%d"),
                                        'job_id': self.env.ref('staff.staff_job_1').id})
        # has staff.contract_ids and apartment manager
        self.env.ref('staff.staff_1').work_email = 'admin@sina.com.cn'
        staff_lily.parent_id = self.env.ref('staff.staff_1').id
        self.env['staff'].staff_contract_over_date()

    def test_onchange_basic_wage(self):
        ''' 测试：选择基本工资时带出五险一金比例，计算出应交金额并填充 '''
        company = self.env.company
        company.endowment_ratio = 8
        # company.health_ratio = 2
        # company.unemployment_ratio = 0.5
        # company.housing_fund_ratio = 7
        # company.endowment_co_ratio = 20
        # company.health_co_ratio = 10
        # company.unemployment_co_ratio = 1
        # company.injury_ratio = 1
        # company.maternity_ratio = 0.5
        # company.housing_fund_co_ratio = 7

        lili_contract = self.env.ref('staff.contract_staff_lili')
        lili_contract.basic_wage = 13000
        lili_contract.onchange_basic_wage()

    def test_check_work_email(self):
        ''' Test: check work email  '''
        staff_lili = self.env.ref('staff.lili')
        # 测试邮箱格式正确
        staff_lili.work_email = 'gooderp@osbzr.com'
        # 测试邮箱格式不正确，报错
        with self.assertRaises(UserError):
            staff_lili.work_email = 'gooderp'


class TestStaffDepartment(TransactionCase):
    ''' 测试 部门 '''

    def test_check_parent_id(self):
        ''' 测试 上级部门不能选择自己和下级的部门 '''
        department_1 = self.env.ref('staff.department_1')
        department_2 = self.env['staff.department'].create({
            'name': '财务部',
            'code': 'dep_finance',
            'type': 'department',
            'parent_id': department_1.id,
        })
        with self.assertRaises(UserError):
            department_1.parent_id = department_2.id

    def test_view_detail(self):
        ''' 测试部门tree 打开部门 '''
        department_1 = self.env.ref('staff.department_1')
        department_1.view_detail()


class TestMailMessage(TransactionCase):

    def setUp(self):
        '''准备基本数据'''
        super(TestMailMessage, self).setUp()
        self.staff = self.browse_ref('staff.staff_1')

    def test_staff_birthday_message(self):
        '''测试：员工生日当天，whole company 会收到祝福信息'''

        # 设置了员工生日
        self.staff.birthday = datetime.now()
        job = self.browse_ref(
            'staff.ir_cron_module_update_notification_birthday')
        job.interval_type = 'minutes'
        job.nextcall = (datetime.now() + timedelta(hours=8)
                        ).strftime('%Y-%m-%d %H:%M:%S')
        job.doall = True
        self.env['mail.message'].staff_birthday_message()


class TestResUsers(TransactionCase):

    def test_check_user_id(self):
        ''' 测试 一个用户只能对应一个员工 '''
        # core 模块里
        user = self.env.ref('base.user_demo')
        self.env.ref('staff.lili').user_id = user.id

        with self.assertRaises(UserError):
            self.env.ref('staff.staff_1').user_id = user.id


class TestLeave(TransactionCase):
    ''' 测试 请假 '''

    def setUp(self):
        '''准备基本数据'''
        super(TestLeave, self).setUp()
        self.leave = self.browse_ref('staff.leave_1')

    def test_set_staff_id(self):
        ''' 测试 请假人 默认值 '''
        self.env['staff.leave'].create({
            'name': 'go back home',
            'leave_type': 'no_pay',
        })

    def test_leave_done(self):
        '''审核请假单'''
        self.leave.leave_done()
        self.assertTrue(self.leave.state == 'done')
        # 重复审核报错
        with self.assertRaises(UserError):
            self.leave.leave_done()

    def test_leave_draft(self):
        '''反审核请假单'''
        self.leave.leave_done()
        self.leave.leave_draft()
        self.assertTrue(self.leave.state == 'draft')
        # 重复反审核审核报错
        with self.assertRaises(UserError):
            self.leave.leave_draft()

    def test_check_leave_dates(self):
        '''请假天数不能小于或等于零'''
        with self.assertRaises(UserError):
            self.leave.leave_dates = 0
