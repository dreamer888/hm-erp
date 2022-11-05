from odoo import fields, api, models


class MrpProcCause(models.Model):
    _name = "mrp.proc.cause"
    _description = "工序不良原因"

    name = fields.Char('名称', required=True)
    mrp_proc_type_id = fields.Many2one('mrp.proc.type', '工序类别', index=True, ondelete='cascade', 
                                       help='用于按工序类绑定不良原因')
    cause_type = fields.Selection([('Industrial waste', '工废'),('Material waste', '料废')], 
                                  default='Industrial waste', string='不良类型', required=True)
    remark = fields.Char('备注')