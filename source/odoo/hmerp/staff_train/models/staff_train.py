# -*- coding: utf-8 -*-
"""
@Time    : 2020/12/28 09:03
@Author  : Jason Zou
@Email   : zou.jason@qq.com
定义hmERP培训项目及培训课程管理模块
"""

import ast
from datetime import timedelta, datetime
from random import randint

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError, AccessError, ValidationError, RedirectWarning
from odoo.tools.misc import format_date, get_lang
from odoo.osv.expression import OR


class StaffProgram(models.Model):
    _name = "staff.program"
    _description = "培训项目"
    _inherit = ['mail.thread']
    _order = "sequence, name, id"

    name = fields.Char(string="项目名称", index=True, required=True, tracking=True)
    description = fields.Html(string="项目摘要", )
    active = fields.Boolean(default=True, help="如果活动字段设置为False，则允许您隐藏项目而不删除它。")
    sequence = fields.Integer(default=10, help="给出显示项目列表时的顺序。")
    label_tasks = fields.Char(string='任务标签', help="用于项目任务的标签。", )
    color = fields.Integer(string='Color Index')
    user_id = fields.Many2one('res.users', string='项目主管', default=lambda self: self.env.user, tracking=True)
    start_date = fields.Date(string='开始日期', index=True, tracking=True)
    end_date = fields.Date(string='截止日期', index=True, tracking=True)

    train_Location = fields.Char(string='项目地点', )
    train_amount = fields.Float(string='项目预算', digits=(12, 2), )
    trainees = fields.Char(string='随训人员范围', )
    train_person_ids = fields.Many2many('staff', string='参训学员', required=True, help='请选择参训学员,来源：员工', )

    _sql_constraints = [
        ('program_date_greater', 'check(end_date >= start_date)', '错误！项目开始日期必须小于项目结束日期。')
    ]

    tasks = fields.One2many('staff.course', 'project_id', string="任务活动")
    task_count = fields.Integer(compute='_compute_task_count', string="附加课程数")
    task_ids = fields.One2many('staff.course', 'project_id', string='培训课程', )

    def _compute_task_count(self):
        task_data = self.env['staff.course'].\
            read_group([('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        result = dict((data['project_id'][0], data['project_id_count']) for data in task_data)
        for project in self:
            project.task_count = result.get(project.id, 0)

    def action_view_tasks(self):
        action = self.with_context(active_id=self.id, active_ids=self.ids) \
            .env.ref('staff_train.act_staff_program_2_staff_course_all') \
            .sudo().read()[0]
        action['display_name'] = self.name
        return action


class StaffCourse(models.Model):
    _name = "staff.course"
    _description = "培训课程"
    _inherit = ['mail.thread']
    _order = "priority desc, project_id, sequence"

    active = fields.Boolean(default=True)
    name = fields.Char(string='课程名称', tracking=True, required=True, index=True)
    description = fields.Html(string='课程摘要')
    priority = fields.Selection([
        ('0', '正常'),
        ('1', '重要'),
    ], default='0', index=True, string="优先级")
    sequence = fields.Integer(string='课程序号', index=True, help="显示任务列表时给出序列顺序。")
    tag_ids = fields.Many2many('staff.tag', string='标签', tracking=True,)
    start_date = fields.Date("课程开始日期", index=True, copy=False, tracking=True,)
    end_date = fields.Date(string='课程结束日期', index=True, copy=False, tracking=True,)
    project_id = fields.Many2one('staff.program', string='培训项目',
                                 store=True, readonly=False, index=True, tracking=True,
                                 change_default=True)
    planned_hours = fields.Float(string="课程计划时间(小时)", help='完成此课程的计划时间。', tracking=True)
    manager_id = fields.Many2one('res.users', string='课程主管', tracking=True,)
    course_teacher_id = fields.Many2one('res.users', string='课程讲师', required=True, tracking=True,
                                        help='请选择课程讲师,来源：员工', )
    color = fields.Integer(string='Color Index')
    state = fields.Selection([('draft', '草稿'),
                              ('ongoing', '进行中'),
                              ('done', '结项')], string='课程状态', default='draft', )


class StaffTags(models.Model):
    _name = "staff.tag"
    _description = "项目标签"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='名称', required=True)
    color = fields.Integer(string='颜色', default=_get_default_color)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "标签名称已存在!"),
    ]
