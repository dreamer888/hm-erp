from odoo import api, fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    employee_ids = fields.One2many('staff', 'user_id', '对应员工')
    team_id = fields.Many2one('team', '所属团队')
    notification_type = fields.Selection(default="inbox")

    @api.model
    def create(self, vals):
        if not vals.get('email'):
            vals.update({
                'email': '@'
            })
        return super(ResUsers, self).create(vals)

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        # 如果普通用户修改管理员，则报错
        if self.env.user.id > 2:
            for record in self:
                if record.id < 3:
                    raise UserError('系统用户不可修改')
        # 如果管理员将自己的系统管理权限去掉，则报错
        else:
            if not self.env.ref('base.user_admin').has_group('base.group_erp_manager'):
                raise UserError('不能删除管理员的管理权限')
        return res


class Team(models.Model):
    _name = 'team'
    _description = '团队'

    name = fields.Char('名称')
    leader_id = fields.Many2one('res.users', '队长')
    member_ids = fields.One2many('res.users','team_id','队员')
