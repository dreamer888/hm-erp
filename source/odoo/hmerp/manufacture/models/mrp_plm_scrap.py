from odoo import fields, api, models
from odoo.exceptions import UserError


class MrpPlmScrap(models.Model):
    _name = "mrp.plm.scrap"
    _description = "生产报废"

    name = fields.Char('报废号码', required=True)
    partner_id = fields.Many2one('partner', '供应商', states={'done': [('readonly', True)]}, ondelete='restrict', help='供应商')
    company_id = fields.Many2one('res.company', '公司', default=lambda self: self.env.company, required=True, index=True, readonly=True)
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states={'done': [('readonly', True)]}, ondelete='cascade')
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states={'done': [('readonly', True)]},
                              help='单据经办人')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心', states={'done': [('readonly', True)]})
    goods_id = fields.Many2one('goods', '加工商品', readonly=True)
    goods_uom_id = fields.Many2one('uom', '单位', readonly=True, index=True, required=True, ondelete='cascade')
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, help='关联生产加工单ID')    
    plm_proc_line_id = fields.Many2one('mrp.plm.proc.line', '工序来源行', readonly=True, help='关联生产加工单工艺明细行ID')
    next_task_id = fields.Many2one('mrp.plm.task', '转下工序任务', readonly=True)
    next_ous_id = fields.Many2one('mrp.plm.ous', '转下工序委外任务', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', compute='_compute_mrp_proc_id', readonly=True)
    next_mrp_proc_id = fields.Many2one('mrp.proc', '转下工序', compute='_compute_next_proc_id', readonly=True)
    next_mrp_proc_get_way = fields.Char('转下工序获取方式', compute='_compute_next_proc_id', readonly=True)
    qty = fields.Float('报废数量', readonly=True, digits='Quantity')
    qty_pending = fields.Float('待报废数量', compute='_compute_qty_pending', copy=False, readonly=True, digits='Quantity')
    dealing_id = fields.Many2one('mrp.plm.task.defectdealing', '不良处理单', readonly=True, help='关联不良处理单返工任务来源')
    ous_dealing_id = fields.Many2one('mrp.plm.ous.defectdealing', '不良处理单', readonly=True, help='关联不良处理单返工任务来源')
    state = fields.Selection([
                   ('draft', '草稿'),
                   ('done', '已确认')], string='状态', readonly=True,
                   default='draft')

    @api.depends('dealing_id', 'ous_dealing_id')
    def _compute_mrp_proc_id(self):
        for t in self:
            t.mrp_proc_id = False
            if t.dealing_id:
                t.mrp_proc_id = t.dealing_id.mrp_proc_id
            elif t.ous_dealing_id:
                t.mrp_proc_id = t.ous_dealing_id.mrp_proc_id
    
    @api.depends('next_task_id', 'next_ous_id')
    def _compute_next_proc_id(self):
        for t in self:
            t.next_mrp_proc_id = False
            t.next_mrp_proc_get_way = False
            if t.next_task_id:
                t.next_mrp_proc_id = t.next_task_id.mrp_proc_id
                t.next_mrp_proc_get_way = t.next_task_id.mrp_proc_id.get_way
            elif t.next_ous_id:
                t.next_mrp_proc_id = t.next_ous_id.mrp_proc_id
                t.next_mrp_proc_get_way = t.next_ous_id.mrp_proc_id.get_way

    @api.depends('dealing_id')
    def _compute_qty_pending(self):
        for l in self:
            if l.dealing_id:
                l.qty_pending = l.dealing_id.qty_scrap - l.dealing_id.qty_scrap_to
            elif l.ous_dealing_id:
                l.qty_pending = l.ous_dealing_id.qty_scrap - l.ous_dealing_id.qty_scrap_to

    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('报工%s,请不要重复确认！' % l.name)
            l.write({
                'state': 'done',
            })
            if l.dealing_id:
                l.dealing_id._compute_to_info()
            if l.ous_dealing_id:
                l.ous_dealing_id._compute_to_info()
            l._compute_qty_pending()
            if l.qty_pending < 0:
                raise UserError('%s %s, 大于来源可报废数量' % (l._description, l.name))

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })