
from odoo import api, fields, models
from odoo.tools import float_is_zero
from odoo.exceptions import UserError

# 状态可选值
TASK_STATES = [
    ('todo', '新建'),
    ('doing', '正在进行'),
    ('done', '已完成'),
    ('cancel', '已取消'),
]

AVAILABLE_PRIORITIES = [
    ('0', '一般'),
    ('1', '低'),
    ('2', '中'),
    ('3', '高'),
]


class Project(models.Model):
    _name = 'project'
    _description = '项目'
    _inherits = {'auxiliary.financing': 'auxiliary_id'}
    _inherit = ['mail.thread']

    @api.depends('task_ids.hours')
    def _compute_hours(self):
        '''计算项目的实际工时'''
        for Project in self:
            for Task in Project.task_ids:
                Project.hours += Task.hours

    type_id = fields.Many2one(
        string='分类',
        comodel_name='core.value',
        ondelete='restrict',
        domain=[('type', '=', 'project_type')],
        context={'type': 'project_type'},
    )
    auxiliary_id = fields.Many2one(
        string='辅助核算',
        comodel_name='auxiliary.financing',
        ondelete='cascade',
        required=True,
    )

    task_ids = fields.One2many(
        string='任务',
        comodel_name='task',
        inverse_name='project_id',
    )

    customer_id = fields.Many2one(
        string='客户',
        comodel_name='partner',
        ondelete='restrict',
    )

    invoice_ids = fields.One2many(
        string='发票行',
        comodel_name='project.invoice',
        inverse_name='project_id',
    )

    plan_hours = fields.Float('计划工时',
                              track_visibility='onchange')
    hours = fields.Float('实际工时',
                         compute=_compute_hours,
                         store=True)
    address = fields.Char('地址')
    note = fields.Text('备注')
    active = fields.Boolean('启用', default=True)


class ProjectInvoice(models.Model):
    _name = 'project.invoice'
    _description = '项目的发票'

    @api.depends('tax_rate', 'amount')
    def _compute_tax_amount(self):
        '''计算税额'''
        self.ensure_one()
        if self.tax_rate > 100:
            raise UserError('税率不能输入超过100的数\n当前税率:%s' % self.tax_rate)
        if self.tax_rate < 0:
            raise UserError('税率不能输入负数\n当前税率:%s' % self.tax_rate)
        self.tax_amount = self.amount / (100 + self.tax_rate) * self.tax_rate

    project_id = fields.Many2one(
        string='项目',
        comodel_name='project',
        ondelete='cascade',
    )

    tax_rate = fields.Float(
        string='税率',
        default=lambda self: self.env.user.company_id.output_tax_rate,
        help='默认值取公司销项税率',
    )

    tax_amount = fields.Float(
        string='税额',
        compute=_compute_tax_amount,
    )

    amount = fields.Float(
        string='含税金额',
        help='含税金额',
    )

    date_due = fields.Date(
        string='到期日',
        default=lambda self: fields.Date.context_today(self),
        required=True,
        help='收款截止日期',
    )

    invoice_id = fields.Many2one(
        string='发票号',
        comodel_name='money.invoice',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='产生的发票号',
    )
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company
    )

    def _get_invoice_vals(self, category_id, project_id, amount, tax_amount):
        '''返回创建 money_invoice 时所需数据'''
        return {
            'name': project_id.name,
            'partner_id': project_id.customer_id and project_id.customer_id.id,
            'category_id': category_id.id,
            'auxiliary_id': project_id.auxiliary_id.id,
            'date' : fields.Date.context_today(self),
            'amount': amount,
            'reconciled': 0,
            'to_reconcile': amount,
            'tax_amount': tax_amount,
            'date_due': self.date_due,
            'state': 'draft',
        }

    def make_invoice(self):
        '''生成结算单'''
        for line in self:
            invoice_id = False
            if not line.project_id.customer_id:
                raise UserError('生成发票前请输入客户')
            category = self.env.ref('money.core_category_sale')
            if not float_is_zero(self.amount, 2):
                invoice_id = self.env['money.invoice'].create(
                    self._get_invoice_vals(
                        category, line.project_id, line.amount, line.tax_amount)
                )
                line.invoice_id = invoice_id.id
            return invoice_id


class Task(models.Model):
    _name = 'task'
    _description = '任务'
    _inherit = ['mail.thread']
    _order = 'sequence, priority desc, id'

    @api.depends('timeline_ids.hours')
    def _compute_hours(self):
        """计算任务的实际工时"""
        for Task in self:
            for line in Task.timeline_ids:
                Task.hours += line.hours

    def _default_status_impl(self):
        """任务阶段默认值的实现方法"""
        status_id = self.env['task.status'].search(
            [('state', '=', 'todo')])
        return status_id and status_id[0]

    @api.model
    def _default_status(self):
        '''创建任务时，任务阶段默认为todo状态的阶段'''
        return self._default_status_impl()

    @api.depends('project_id.type_id')
    def _compute_project_type_id(self):
        for line in self:
            line.project_type_id = False
            if line.project_id:
                line.project_type_id = self.project_id.type_id

    name = fields.Char(
        string='名称',
        required=True,
    )

    user_id = fields.Many2one(
        string='指派给',
        comodel_name='res.users',
        track_visibility='onchange',
    )

    project_id = fields.Many2one(
        string='项目',
        comodel_name='project',
        ondelete='cascade',
    )
    project_type_id = fields.Many2one(
        string='分类',
        comodel_name='core.value',
        ondelete='restrict',
        compute=_compute_project_type_id,
        store=True)

    timeline_ids = fields.One2many(
        string='工作记录',
        comodel_name='timeline',
        inverse_name='task_id',
    )

    next_action = fields.Char(
        string='下一步计划',
        required=False,
        help='针对此任务下一步的计划',
        track_visibility='onchange',
    )

    next_datetime = fields.Datetime(
        string='下一步计划时间',
        help='下一步计划预计开始的时间',
        track_visibility='onchange',
    )

    status = fields.Many2one(
        'task.status',
        string='状态',
        default=_default_status,
        track_visibility='onchange',
        ondelete='restrict',
        domain="['|', ('project_type_id', '=', project_type_id), ('state','!=','doing')]",
    )
    plan_hours = fields.Float('计划工时')
    hours = fields.Float('实际工时',
                         compute=_compute_hours,
                         store=True)
    sequence = fields.Integer('顺序')
    is_schedule = fields.Boolean('列入计划')
    note = fields.Text('描述')
    priority = fields.Selection(AVAILABLE_PRIORITIES,
                                string='优先级',
                                default=AVAILABLE_PRIORITIES[0][0])
    color = fields.Integer('Color Index',
                           default=0)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company
    )
    tag_ids = fields.Many2many('core.value',
                               ondelete='restrict',
                               string='标签',
                               domain=[('type', '=', 'task_tag')],
                               context={'type': 'task_tag'})

    def assign_to_me(self):
        '''将任务指派给自己，并修改状态'''
        self.ensure_one()
        next_status = self.env['task.status'].search([('state', '=', 'doing')])
        self.user_id = self.env.user
        self.status = next_status and next_status[0]


class TaskStatus(models.Model):
    _name = 'task.status'
    _description = '任务阶段'
    _order = 'sequence, id'

    name = fields.Char('名称', required=True)
    project_type_id = fields.Many2one(
        string='项目分类',
        comodel_name='core.value',
        ondelete='restrict',
        domain=[('type', '=', 'project_type')],
    )
    state = fields.Selection(TASK_STATES,
                             string='任务状态',
                             index=True,
                             required=True,
                             default='doing')
    sequence = fields.Integer('顺序', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class Timesheet(models.Model):
    _name = 'timesheet'
    _description = '今日工作日志'

    date = fields.Date(
        string='日期',
        required=True,
        readonly=True,
        default=fields.Date.context_today)

    user_id = fields.Many2one(
        string='用户',
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        comodel_name='res.users',
    )

    timeline_ids = fields.One2many(
        string='工作记录',
        comodel_name='timeline',
        inverse_name='timesheet_id',
    )

    task_ids = fields.Many2many(
        string='待办事项',
        required=False,
        readonly=False,
        default=lambda self: [(4, t.id) for t in self.env['task'].search(
            [('user_id', '=', self.env.user.id),
             ('status.state', '=', 'doing')])],
        help=False,
        comodel_name='task',
        domain=[],
        context={},
        limit=None
    )
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company
    )
    color = fields.Integer('Color Index',
                           default=0)

    _sql_constraints = [
        ('user_uniq', 'unique(user_id,date)', '同一个人一天只能创建一个工作日志')
    ]

    def name_get(self):
        ret = []
        for s in self:
            ret.append((s.id, '%s %s' % (s.user_id.name, s.date)))
        return ret


class Timeline(models.Model):
    _name = 'timeline'
    _description = '工作记录'

    timesheet_id = fields.Many2one(
        string='记录表',
        comodel_name='timesheet',
        ondelete='cascade',
    )

    task_id = fields.Many2one(
        string='任务',
        required=True,
        readonly=False,
        comodel_name='task',
    )

    project_id = fields.Many2one(
        string='项目',
        related='task_id.project_id',
        store=True,
        ondelete='cascade',
    )

    user_id = fields.Many2one(
        string='指派给',
        comodel_name='res.users',
    )

    start_time = fields.Datetime('开始时间', default=fields.Datetime.now)
    end_time = fields.Datetime('结束时间', default=fields.Datetime.now)

    hours = fields.Float(
        string='小时数',
        default=0.5,
        digits=(16, 1),
        help='实际花的小时数',
    )

    just_done = fields.Text(
        string='具体工作内容',
        required=True,
        help='在此时长内针对此任务实际完成的工作内容',
    )

    need_help = fields.Char(
        string='需要的帮助',
    )
# TODO 以下三个字段用于更新task的同名字段
    next_action = fields.Char(
        string='下一步计划',
        required=False,
        help='针对此任务下一步的计划',
    )

    next_datetime = fields.Datetime(
        string='下一步计划时间',
        help='下一步计划预计开始的时间',
    )
    set_status = fields.Many2one('task.status',
                                 string='状态更新到')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company
    )
    color = fields.Integer('Color Index',
                           default=0)

    @api.model
    def create(self, vals):
        '''创建工作记录时，更新对应task的status等字段'''
        res = super(Timeline, self).create(vals)
        set_status = vals.get('set_status')
        task_id = vals.get('task_id')
        next_action = vals.get('next_action')
        next_datetime = vals.get('next_datetime')
        user_id = vals.get('user_id')
        Task = self.env['task'].search([('id', '=', task_id)])
        if set_status:
            Task.write({'status': set_status})
        if next_action:
            Task.write({'next_action': next_action})
        if next_datetime:
            Task.write({'next_datetime': next_datetime})
        if user_id:
            Task.write({'user_id': user_id})
        return res
