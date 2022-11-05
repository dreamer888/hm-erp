from odoo import api, fields, models
from odoo.exceptions import UserError


class MrpProcClass(models.Model):
    _name = "mrp.proc.class"
    _description = "工序等级"

    code = fields.Char('代号', required=True, index=True, default='')
    name = fields.Char('名称', required=True, index=True, default='')

    price = fields.Float('等级标准')
    remark = fields.Char('备注', default='')