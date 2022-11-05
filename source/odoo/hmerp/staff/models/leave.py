
from odoo import api, fields, models
from odoo.exceptions import UserError
import time
import datetime

# 请假单确认状态可选值
LEAVE_STATES = [
    ('draft', '未确认'),
    ('done', '已确认'), ]


class StaffLeave(models.Model):
    _name = 'staff.leave'
    _description = '请假单'
    _inherit = ['mail.thread']

    @api.model
    def _set_staff_id(self):
        return self.env.uid

    name = fields.Text(string='请假缘由',
                       readonly=True,
                       states={'draft': [('readonly', False)]},
                       )
    user_id = fields.Many2one('res.users',
                              string='请假人',
                              default=_set_staff_id,
                              readonly=True,
                              states={'draft': [('readonly', False)]}
                              )
    date_start = fields.Datetime(string='离开时间',
                                 readonly=True,
                                 states={'draft': [('readonly', False)]}
                                 )
    date_stop = fields.Datetime(string='回来时间',
                                readonly=True,
                                states={'draft': [('readonly', False)]})
    leave_type = fields.Selection([('no_pay', '无薪'), ('with_pay', '带薪'),
                                   ('compensation_day', '补偿日数'), ('sick_leave', '病假')],
                                  required=True, string='准假类型', readonly=True,
                                  states={'draft': [('readonly', False)]})
    leave_dates = fields.Float('请假天数', readonly=True,
                               states={'draft': [('readonly', False)]})
    state = fields.Selection(LEAVE_STATES, '状态', readonly=True,
                             help="请假单的状态", index=True, copy=False,
                             default='draft')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def leave_done(self):
        '''确认请假单'''
        for l in self:
            if l.state == 'done':
                raise UserError('请不要重复确认！')
            l.state = 'done'

    def leave_draft(self):
        '''撤销确认请假单'''
        for l in self:
            if l.state == 'draft':
                raise UserError('请不要重复撤销 %s' % self._description)
            l.state = 'draft'

    @api.constrains('leave_dates')
    def check_leave_dates(self):
        for l in self:
            if l.leave_dates <= 0:
                raise UserError('请假天数不能小于或等于零')
