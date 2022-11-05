from odoo.tests.common import TransactionCase
from psycopg2 import IntegrityError
from odoo.exceptions import UserError, ValidationError
import datetime
from odoo.tools import mute_logger
from odoo import fields
import pytz


class TestCore(TransactionCase):

    def test_partner(self):
        ''' 测试删除已有客户的分类报错 '''
        # return          # 测试已通过，但会在log里报ERROR，所以暂时去掉
        with mute_logger('odoo.sql_db'):
            with self.assertRaises(IntegrityError):
                self.env.ref('core.customer_category_1').unlink()

    def test_partner_name_search(self):
        """
        partner在many2one字段中支持按编号搜索
        """
        partner = self.env.ref('core.jd')
        # 使用 name 来搜索京东
        result = self.env['partner'].name_search('京东')
        real_result = [(partner.id, partner.name)]
        self.assertEqual(result, real_result)
        # 使用 code 来搜索京东
        res = self.env['partner'].name_search('jd')
        self.assertEqual(res, real_result)

        # 编号 ilike
        partner.code = '京东'
        res = self.env['partner'].name_search('京')
        self.assertEqual(res, real_result)

    def test_partner_write(self):
        ''' 测试 业务伙伴应收/应付余额不为0时，不允许取消对应的客户/供应商身份 '''
        partner = self.env.ref('core.jd')
        partner.receivable = 100
        with self.assertRaises(UserError):
            partner.c_category_id = False

        partner = self.env.ref('core.lenovo')
        partner.payable = 100
        with self.assertRaises(UserError):
            partner.s_category_id = False

    def test_res_currency(self):
        """测试阿拉伯数字转换成中文大写数字的方法"""
        self.env['res.currency'].rmb_upper(10000100.3)
        # 测试输入value为负时的货币大写问题
        self.assertTrue(
            self.env['res.currency'].rmb_upper(-10000100.3) == '负壹仟万零壹佰元叁角整')

    def test_compute_days_qualify(self):
        """计算资质到期天数。"""
        partner = self.env.ref('core.jd')
        partner.date_qualify = self.to_local(fields.Datetime.now()) + datetime.timedelta(days=1)
        self.assertEqual(partner.days_qualify, 1)

    def to_local(self, date):
        if date.__class__.__name__ == 'date':
            return date
        if date.microsecond > 0:
            return datetime.datetime.strptime(str(date), '%Y-%m-%d %H:%M:%S.%f').replace(
                tzinfo=pytz.timezone('UTC')).astimezone(pytz.timezone(self.env.user.tz or 'UTC'))
        return datetime.datetime.strptime(str(date), '%Y-%m-%d %H:%M:%S').replace(
            tzinfo=pytz.timezone('UTC')).astimezone(pytz.timezone(self.env.user.tz or 'UTC'))

    def test_check_category_exists(self):
        ''' test_check_category_exists '''
        partner = self.env.ref('core.jd')
        with self.assertRaises(UserError):
            partner.c_category_id = False


class TestResUsers(TransactionCase):

    def test_write(self):
        '''修改管理员权限'''
        user_demo = self.env.ref('base.user_demo')
        user_demo.groups_id = [(4, self.env.ref('base.group_erp_manager').id)]
        user_admin = self.env.ref('base.user_admin').with_user(user_demo)
        with self.assertRaises(UserError):
            user_admin.name = 'adsf'
        with self.assertRaises(UserError):
            user_admin.groups_id = [(3, self.env.ref('base.group_erp_manager').id)]


class TestBusinessData(TransactionCase):
    def test_business_data_table(self):
        ''' 选择model填充table名'''
        business_data_table = self.env['business.data.table']
        business_data_table_row = business_data_table.create(
            {'name': 'home.report.type'})
        business_data_table_row.onchange_model()


class TestResCompany(TransactionCase):

    def test_get_logo(self):
        ''' 取默认logo '''
        self.env['res.company'].create({
            'name': 'demo company',
            'partner_id': self.env.ref('core.zt').id
        })

    def test_check_email(self):
        ''' test check email '''
        company = self.env['res.company'].create({
            'name': 'demo company',
            'partner_id': self.env.ref('core.zt').id
        })
        # 邮箱格式正确
        company.email = '75039960@qq.com'

        # 邮箱格式不正确，报错
        with self.assertRaises(UserError):
            company.email = 'gooderp'
