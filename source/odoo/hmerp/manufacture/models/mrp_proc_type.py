from odoo import api, fields, models
from odoo.exceptions import UserError


class MrpProcType(models.Model):
    _name = "mrp.proc.type"
    _description = "工序类别"

    code = fields.Char('代号', required=True, index=True, default='')
    name = fields.Char('名称', required=True, index=True, default='')
    department_id = fields.Many2one('staff.department', '加工部门', index=True, ondelete='cascade')
    up_id = fields.Many2one('mrp.proc.type', '上级类别')
    node = fields.Selection([('view', u'节点'), ('normal', u'常规')],
                            u'类型', required=True, default='normal',
                            help=u'工序类别，分为节点和常规，只有节点的分类才可以建下级工序分类，常规分类不可作为上级工序分类')
    remark = fields.Char('备注', default='')

