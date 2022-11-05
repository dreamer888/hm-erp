from odoo import fields, api, models
from odoo.exceptions import UserError


class MrpPlmTaskQc(models.Model):
    _name = "mrp.plm.task.qc"
    _description = "生产检验报告"

    name = fields.Char('工序质检报告', required=True)
    company_id = fields.Many2one('res.company', '公司', default=lambda self: self.env.company, required=True, index=True, readonly=True)
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states={'done': [('readonly', True)]}, ondelete='cascade')
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states={'done': [('readonly', True)]},
                              help='单据经办人')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心', states={'done': [('readonly', True)]})
    goods_id = fields.Many2one('goods', '加工商品', readonly=True)
    goods_uom_id = fields.Many2one('uom', '单位', index=True, required=True, readonly=True, ondelete='cascade')
    plm_task_id = fields.Many2one('mrp.plm.task', '生产任务单', readonly=True, help='关联生产任务ID')   
    plm_ous_id = fields.Many2one('mrp.plm.ous', '工序委外订单', readonly=True, help='关联生产任务ID')
    plm_task_conf_id = fields.Many2one('mrp.plm.task.conf', '生产任务单', readonly=True, help='关联生产报工ID')    
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, help='关联生产加工单ID')    
    plm_proc_line_id = fields.Many2one('mrp.plm.proc.line', '工序来源行', readonly=True, help='关联生产加工单工艺明细行ID')
    next_task_id = fields.Many2one('mrp.plm.task', '转下工序任务', readonly=True)
    next_ous_id = fields.Many2one('mrp.plm.ous', '转下工序委外任务', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', compute='_compute_mrp_proc_id', readonly=True)
    next_mrp_proc_id = fields.Many2one('mrp.proc', '转下工序', readonly=True, compute='_compute_next_proc_id')
    next_mrp_proc_get_way = fields.Char('转下工序获取方式', compute='_compute_next_proc_id', readonly=True)
    qty = fields.Float('质检数量', digits='Quantity', states={'done': [('readonly', True)]})
    qty_ok = fields.Float('合格数量', digits='Quantity', compute='_compute_qty', readonly=True)
    qty_bad = fields.Float('不合格数量', digits='Quantity', compute='_compute_qty', readonly=True)
    qty_dealing = fields.Float('不良处理数量', digits='Quantity', compute='_compute_plm_task_defectdealing', readonly=True)
    qty_pending = fields.Float("待质检数量", digits='Quantity', compute="_compute_qty_pending",readonly=True)
    plm_task_dealing_ids = fields.One2many('mrp.plm.task.defectdealing', 'plm_task_qc_id', readonly=True)
    plm_task_defectdealing_count = fields.Integer(compute='_compute_plm_task_defectdealing', readonly=True)
    dealing_line_id = fields.Many2one('mrp.plm.task.defectdealing.line', '生产不良返工明细', readonly=True, help='关联生产不良处返工明细行id')
    ous_dealing_line_id = fields.Many2one('mrp.plm.ous.defectdealing.line', '委外不良返工明细', readonly=True, help='关联委外不良处返工明细行id')
    
    state = fields.Selection([
                   ('draft', '草稿'),
                   ('done', '已确认')], string='状态',
                   default='draft', readonly=True)
    line_ids = fields.One2many('mrp.plm.task.qc.line', 'qc_id', '质检不良明细', states={'done': [('readonly', True)]})

    @api.depends('plm_task_dealing_ids')
    def _compute_plm_task_defectdealing(self):
        for line in self:
            line.plm_task_defectdealing_count = len([l for l in line.plm_task_dealing_ids])
            line.qty_dealing = sum(l.qty for l in line.plm_task_dealing_ids.filtered(lambda l1: l1.state == 'done'))

    @api.depends('line_ids')
    def _compute_qty(self):
        for line in self:
            line.qty_ok = line.qty - sum(l.qty for l in line.line_ids)
            line.qty_bad = sum(l.qty for l in line.line_ids)

    @api.depends('plm_proc_line_id', 'dealing_line_id', 'ous_dealing_line_id')
    def _compute_mrp_proc_id(self):
        for t in self:
            t.mrp_proc_id = False
            if t.dealing_line_id:
                t.mrp_proc_id = t.dealing_line_id.mrp_proc_id
            elif t.ous_dealing_line_id:
                t.mrp_proc_id = t.ous_dealing_line_id.mrp_proc_id
            elif t.plm_proc_line_id:
                t.mrp_proc_id = t.plm_proc_line_id.mrp_proc_id

    @api.depends('next_task_id')
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

    @api.depends('plm_task_conf_id')
    def _compute_qty_pending(self):
        for l in self:
            l.qty_pending = 0
            if l.plm_task_conf_id:
                l.qty_pending = l.plm_task_conf_id.qty - l.plm_task_conf_id.qty_qc

    @api.onchange('line_ids')
    def onchange_line_ids(self):
        self._compute_qty()        

    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('质检报告%s,请不要重复确认！' % l.name)
            if l.qty < l.qty_bad:
                raise UserError('质检报告%s,不良数量大于质检数量 ！' % l.name)
            l.write({
                'state': 'done',
            })
            if l.plm_task_conf_id:
                l.plm_task_conf_id._compute_qc()
                if l.plm_task_conf_id.qty < l.plm_task_conf_id.qty_qc:
                    raise UserError('质检报告%s,质检数大于报工数！' % l.name)
                l.plm_task_conf_id._create_task_qc()
            l._create_plm_task_defectdealing()

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })
            dealing_ids = self.env['mrp.plm.task.defectdealing'].search([('plm_task_qc_id', '=', l.id)])
            if len(dealing_ids) > 0:
                dealing_ids.unlink()
    
    def _create_plm_task_defectdealing(self):
        """
        """
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_scrap = sum(l1.qty for l1 in l.line_ids.filtered(lambda l2: l2.disposal_mode == 'scrap'))
            qty_replan = sum(l1.qty for l1 in l.line_ids.filtered(lambda l2: l2.disposal_mode == 'replan'))
            qty_rework = l.qty_bad - qty_scrap - qty_replan
            if l.qty_bad > l.qty_dealing:
                mrp_plm_id = rec.env['mrp.plm.task.defectdealing'].create({
                    'company_id': l.company_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'plm_task_id': l.plm_task_id.id,
                    'plm_task_qc_id': l.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'qty': l.qty_bad - l.qty_dealing,
                    'qty_rework': qty_rework,
                    'qty_scrap': qty_scrap,
                    'qty_replan': qty_replan
                })

    def action_view_plm_task_defectdealing(self):
        self.ensure_one()
        action = {
            'name': '不良处理',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.task.defectdealing',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_dealing_ids = [plm_dealing.id for plm_dealing in self.plm_task_dealing_ids]
        # choose the view_mode accordingly
        if len(plm_dealing_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_dealing_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_dealing_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_task_defectdealing_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_dealing_ids and plm_dealing_ids[0] or False
        return action
    
    def unlink(self):
        for l in self:
            if not l.state == 'draft':
                raise UserError('%s %s, 不为草稿状态，不许删除' % (self._description , l.name))
        super().unlink()


class MrpPlmTaskQcLine(models.Model):
    _name = "mrp.plm.task.qc.line"
    _description = "工序不良明细"

    qc_id = fields.Many2one('mrp.plm.task.qc', '工序质检报告', help='绑定质检报告id')
    mrp_proc_cause_id = fields.Many2one('mrp.proc.cause', string='不良原因')
    mrp_proc_cause_type_id = fields.Selection('工序不良类别', related='mrp_proc_cause_id.cause_type', readonly=True)
    qty = fields.Float('不良数量', required=True, digits='Quantity')
    disposal_mode = fields.Selection([
        ('rework', '返工'),
        ('scrap', '报废'),
        ('replan', '重工')], string='处置方式', required=True)