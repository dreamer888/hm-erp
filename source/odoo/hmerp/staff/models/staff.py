from odoo import fields, models, api, tools, modules, _
from datetime import datetime
from odoo.exceptions import UserError
import re
from random import randint

class ResUsers(models.Model):
    _inherit = 'res.users'

    staff_ids = fields.One2many('staff', 'user_id', '关联员工')
    staff_id = fields.Many2one('staff', '公司员工',
                            compute='_compute_staff_id',
                            search='_search_company_staff',
                            store=True,)
    staff_count = fields.Integer(compute='_compute_staff_count')

    @api.depends('staff_ids')
    def _compute_staff_id(self):
        for line in self:
            self.staff_id = False
            if self.staff_ids and len(self.staff_ids)==1:
                self.staff_id = self.staff_ids[0].id

    def _search_company_staff(self, operator, value):
        staff = self.env['staff'].search([
            ('name', operator, value),
            '|',
            ('company_id', '=', self.env.company.id),
            ('company_id', '=', False)
        ], order='company_id ASC')
        return [('id', 'in', staff.mapped('user_id').ids)]

    def action_create_staff(self):
        self.ensure_one()
        self.env['staff'].create(dict(
            name=self.name,
            company_id=self.env.company.id,
            **self.env['staff']._sync_user(self)
        ))

    @api.depends('staff_ids')
    def _compute_staff_count(self):
        for user in self.with_context(active_test=False):
            user.staff_count = len(user.staff_ids)

class StaffDepartment(models.Model):
    _name = "staff.department"
    _description = '员工部门'
    _inherits = {'auxiliary.financing': 'auxiliary_id'}

    auxiliary_id = fields.Many2one(
        string='辅助核算',
        comodel_name='auxiliary.financing',
        ondelete='cascade',
        required=True,
    )
    dtype = fields.Selection(
        [("sell", "销售"), ("admin", "管理"), ("develop", "研发"), ("produce", "制造")],
        string='部门类别', default="admin", required=True)
    manager_id = fields.Many2one('staff', '部门经理')
    member_ids = fields.One2many('staff', 'department_id', '部门成员')
    parent_id = fields.Many2one('staff.department', '上级部门')
    child_ids = fields.One2many('staff.department', 'parent_id', '下级部门')
    jobs_ids = fields.One2many('staff.job', 'department_id', '职位')
    note = fields.Text('备注')
    active = fields.Boolean('启用', default=True)

    @api.constrains('parent_id')
    def _check_parent_id(selfs):
        '''上级部门不能选择自己和下级的部门'''
        for self in selfs:
            if self.parent_id:
                staffs = self.env['staff.department'].search(
                    [('parent_id', '=', self.id)])
                if self.parent_id in staffs:
                    raise UserError('上级部门不能选择他自己或者他的下级部门')

    def view_detail(self):
        for child_department in self:
            context = {'default_name': child_department.name,
                       'default_manager_id': child_department.manager_id.id,
                       'default_parent_id': child_department.parent_id.id}
            res_id = self.env['staff.department'].search(
                [('id', '=', child_department.id)])
            view_id = self.env.ref('staff.view_staff_department_form').id

            return {
                'name': '部门/' + child_department.name,
    
                'view_mode': 'form',
                'res_model': 'staff.department',
                'res_id': res_id.id,
                'view_id': False,
                'views': [(view_id, 'form')],
                'type': 'ir.actions.act_window',
                'context': context,
                'target': 'current',
            }


class StaffJob(models.Model):
    _name = "staff.job"
    _description = '员工职位'

    name = fields.Char('职位', required=True)
    note = fields.Text('描述')
    account_id = fields.Many2one('finance.account', '计提工资科目')
    department_id = fields.Many2one('staff.department', '部门')
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_uniq', 'unique(name,department_id)', '同部门的职位不能重复！')
    ]


class StaffEmployeeCategory(models.Model):
    _name = "staff.employee.category"
    _description = '员工层级'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('名称',required=True)
    parent_id = fields.Many2one('staff.employee.category', '上级标签', index=True)
    chield_ids = fields.One2many(
        'staff.employee.category', 'parent_id', '下级标签')
    employee_ids = fields.Many2many('staff',
                                    'staff_employee_category_rel',
                                    'category_id',
                                    'emp_id', '员工')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    color = fields.Integer(string='分类颜色', default=_get_default_color)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "分类标签已经存在!"),
    ]

class Staff(models.Model):
    _inherit = 'staff'
    _inherits = {'auxiliary.financing': 'auxiliary_id'}
    _order = 'department_id, work_no'

    @api.onchange('job_id')
    def onchange_job_id(self):
        '''选择职位时带出部门和部门经理'''
        if self.job_id:
            self.department_id = self.job_id.department_id
            self.parent_id = self.job_id.department_id.manager_id

    @api.constrains('work_email')
    def _check_work_email(selfs):
        ''' 验证 work_email 合法性 '''
        for self in selfs:
            if self.work_email:
                res = re.match('^[a-zA-Z0-9_-_.]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$', self.work_email)
                if not res:
                    raise UserError('请检查邮箱格式是否正确: %s' % self.work_email)

    def _sync_user(self, user):
        vals = dict(
            image_medium=user.image_1920,
            work_email = user.email if len(user.email)>1  else '',
            user_id=user.id,
        )
        return vals

    auxiliary_id = fields.Many2one(
        string='辅助核算',
        comodel_name='auxiliary.financing',
        ondelete='restrict',
        required=True,
    )
    category_ids = fields.Many2many('staff.employee.category',
                                    'staff_employee_category_rel',
                                    'emp_id',
                                    'category_id', string='标签')
    work_email = fields.Char(string='办公邮箱')
    work_phone = fields.Char(string='办公电话')

    image_medium = fields.Image(string='头像',attachment=True)

    # 个人信息
    birthday = fields.Date(string='生日')
    identification_id = fields.Char(string='证照号码')
    is_arbeitnehmer = fields.Boolean(string='是否雇员', default='1')
    is_investoren = fields.Boolean(string='是否投资者')
    is_bsw = fields.Boolean(string='是否残疾烈属孤老')
    type_of_certification = fields.Selection([
        ('ID', '居民身份证'),
        ('Military_ID', '军官证'),
        ('Soldiers_Card', '士兵证'),
        ('Police_badge', '武警警官证'),
        ('Passport_card', '护照'),
    ], string='证照类型', default='ID', required=True)
    gender = fields.Selection([
                              ('male', '男'),
                              ('female', '女')
                              ], string='性别')
    marital = fields.Selection([
        ('single', '单身'),
        ('married', '已婚'),
        ('widower', '丧偶'),
        ('divorced', '离异')
    ], string='婚姻状况')
    contract_ids = fields.One2many('staff.contract', 'staff_id', string='合同')
    active = fields.Boolean(string='启用', default=True)
    # 公开信息
    work_mobile = fields.Char(string='办公手机')
    department_id = fields.Many2one('staff.department', string='部门')
    parent_id = fields.Many2one('staff', string='部门经理')
    job_id = fields.Many2one('staff.job', string='职位')
    notes = fields.Text(string='其他信息')
    emergency_contact = fields.Char(string='紧急联系人')
    emergency_call = fields.Char(string='紧急联系方式')
    bank_name = fields.Char(string='工资卡号')
    bank_num = fields.Char(string='工资卡开户行')

    @api.model
    def staff_contract_over_date(self):
        # 员工合同到期，发送邮件给员工 和 部门经理（如果存在）
        now = datetime.now().strftime("%Y-%m-%d")
        for Staff in self.search([]):
            if not Staff.contract_ids:
                continue

            for contract in Staff.contract_ids:
                if now == contract.over_date:
                    self.env.ref('staff.contract_over_due_date_employee').send_mail(
                        self.env.user.id)
                    if Staff.parent_id and Staff.parent_id.work_email:
                        self.env.ref('staff.contract_over_due_date_manager').send_mail(
                            self.env.user.id)

        return

    # ===========================
    # @Time    : 2020/12/24 16:23
    # @Author  : Jason Zou
    # @Email   : zou.jason@qq.com
    # 以下扩展员工个人信息
    # ===========================
    work_no = fields.Char(string='员工工号')
    work_date = fields.Date(string='参加工作日期', )
    join_date = fields.Date(string='加入本司日期', )
    training_date = fields.Date(string='新员工培训日期', )
    confirm_date = fields.Date(string='转正日期', )
    spouse_complete_name = fields.Char(string='配偶全名', )
    spouse_birthdate = fields.Date(string='配偶生日', )
    km_home_work = fields.Char(string='家和公司之间的距离', )
    contract_category_id = fields.Many2one('staff.type',
                                           string='合同类别',
                                           ondelete='restrict',
                                           domain=[('type', '=', 'contract_category')],
                                           context={'type': 'contract_category'})
    confident_agreement_id = fields.Many2one('staff.type',
                                             string='保密协议类别',
                                             ondelete='restrict',
                                             domain=[('type', '=', 'confident_agreement')],
                                             context={'type': 'confident_agreement'})
    job_type_id = fields.Many2one('staff.type',
                                  string='岗位类型',
                                  ondelete='restrict',
                                  domain=[('type', '=', 'job_type')],
                                  context={'type': 'job_type'})

    reimbursement_card = fields.Char(string='报销卡号', )
    account_reimbursement_card = fields.Char(string='报销卡开户行', )

    professional_title_id = fields.Many2one('staff.type',
                                            string='职称',
                                            ondelete='restrict',
                                            domain=[('type', '=', 'professional_title')],
                                            context={'type': 'professional_title'})
    graduation_certificate_id = fields.Many2one('staff.type',
                                                string='证书',
                                                ondelete='restrict',
                                                domain=[('type', '=', 'graduation_certificate')],
                                                context={'type': 'graduation_certificate'})

    children = fields.Char(string='子女数', )
    child_one = fields.Char(string='子女1姓名', )
    child_one_birthday = fields.Date(string='子女1出生日期', )
    child_two = fields.Char(string='子女2姓名', )
    child_two_birthday = fields.Date(string='子女2出生日期', )

    relationship_one_id = fields.Many2one('staff.type',
                                          string='关系',
                                          ondelete='restrict',
                                          domain=[('type', '=', 'relationship_one')],
                                          context={'type': 'relationship_one'})
    second_contact = fields.Char(string='第二紧急联系人', )
    relationship_two_id = fields.Many2one('staff.type',
                                          string='第二紧急联系人关系',
                                          ondelete='restrict',
                                          domain=[('type', '=', 'relationship_two')],
                                          context={'type': 'relationship_two'})
    second_contact_tel = fields.Char(string='第二紧急联系人电话', )
    archives_place = fields.Char(string='档案存放地', )

    leaving_reason_id = fields.Many2one('staff.type',
                                        string='离职原因',
                                        ondelete='restrict',
                                        domain=[('type', '=', 'leaving_reason')],
                                        context={'type': 'leaving_reason'})
    last_working = fields.Date(string='最后工作日', )
    salary_date = fields.Date(string='工资结算日', )
    duration_agreement = fields.Char(string='培训协议期限', )

    political_outlook_id = fields.Many2one('staff.type',
                                           string='政治面貌',
                                           ondelete='restrict',
                                           domain=[('type', '=', 'political_outlook')],
                                           context={'type': 'political_outlook'})
    nation_id = fields.Many2one('staff.type',
                                string='民族',
                                ondelete='restrict',
                                domain=[('type', '=', 'nation_ch')],
                                context={'type': 'nation_ch'})
    native_place = fields.Char(string='籍贯', )
    household_registration_id = fields.Many2one('staff.type',
                                                string='户籍类型',
                                                ondelete='restrict',
                                                domain=[('type', '=', 'household_registration')],
                                                context={'type': 'household_registration'})
    actual_residence = fields.Char(string='实际居住地住址', )

    highest_education_id = fields.Many2one('staff.type',
                                           string='最高学历',
                                           ondelete='restrict',
                                           domain=[('type', '=', 'highest_education')],
                                           context={'type': 'highest_education'})
    major_title_id = fields.Many2one('staff.type',
                                     string='专业',
                                     ondelete='restrict',
                                     domain=[('type', '=', 'major_title')],
                                     context={'type': 'major_title'})
    university_graduated_id = fields.Many2one('staff.type',
                                              string='毕业院校',
                                              ondelete='restrict',
                                              domain=[('type', '=', 'university_graduated')],
                                              context={'type': 'university_graduated'})
    learning_form_id = fields.Many2one('staff.type',
                                       string='学历性质',
                                       ondelete='restrict',
                                       domain=[('type', '=', 'learning_form')],
                                       context={'type': 'learning_form'})
    graduation_date = fields.Date(string='毕业时间', )

    social_payment_address_id = fields.Many2one('staff.type',
                                                string='社保公积金缴纳地点',
                                                ondelete='restrict',
                                                domain=[('type', '=', 'social_payment_address')],
                                                context={'type': 'social_payment_address'})
    commercial_insurance = fields.Char(string='商保号', )
    social_security_account = fields.Char(string='社保账号', )
    provident_fund_account = fields.Char(string='公积金账号', )

    @api.model
    def create(self, vals):
        if vals.get('user_id'):
            user = self.env['res.users'].browse(vals['user_id'])
            vals.update(self._sync_user(user))
            vals['name'] = vals.get('name', user.name)
        return super().create(vals)

    def write(self, vals):
        if vals.get('user_id'):
            vals.update(self._sync_user(self.env['res.users'].browse(vals['user_id'])))
        return super().write(vals)
