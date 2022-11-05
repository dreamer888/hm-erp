from odoo import fields, api, models


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _description = '工作中心'

    code = fields.Char('代号', required=True, index=True)
    name = fields.Char('工作中心', required=True)
    department_id = fields.Many2one('staff.department', '归属部门', ondelete='cascade')
    remark = fields.Char('备注')
