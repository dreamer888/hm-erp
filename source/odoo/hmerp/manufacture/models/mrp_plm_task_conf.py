from odoo import fields, api, models
from odoo.exceptions import UserError


class MrpPlmTaskConf(models.Model):
    _name = "mrp.plm.task.conf"
    _description = "生产报工"

    name = fields.Char('单据号码', required=True)
    date = fields.Date('单据日期', required=True, copy=False, default=fields.Date.context_today,
                    help='单据创建日期，默认为当前天')
    company_id = fields.Many2one('res.company', '公司', default=lambda self: self.env.company, required=True, index=True, readonly=True)
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states={'done': [('readonly', True)]}, ondelete='cascade')
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states={'done': [('readonly', True)]},
                              help='单据经办人')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心', states={'done': [('readonly', True)]})
    goods_id = fields.Many2one('goods', '加工商品', readonly=True)
    goods_uom_id = fields.Many2one('uom', '单位', index=True, required=True, ondelete='cascade', readonly=True)
    plm_task_id = fields.Many2one('mrp.plm.task', '生产任务单', readonly=True, help='关联生产加工单ID')    
    plm_ous_id = fields.Many2one('mrp.plm.ous', '工序委外订单', readonly=True, help='关联生产任务ID')
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, help='关联生产加工单ID')
    plm_proc_line_id = fields.Many2one('mrp.plm.proc.line', '工序来源行', readonly=True, help='关联生产加工单工艺明细行ID')
    next_task_id = fields.Many2one('mrp.plm.task', '转下工序任务', readonly=True)
    next_ous_id = fields.Many2one('mrp.plm.ous', '转下工序委外任务', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', compute='_compute_mrp_proc_id', readonly=True)
    next_mrp_proc_id = fields.Many2one('mrp.proc', '转下工序', compute='_compute_next_proc_id', readonly=True)
    next_mrp_proc_get_way = fields.Char('转下工序获取方式', compute='_compute_next_proc_id', readonly=True)
    qty = fields.Float('报工数量', digits='Quantity', states={'done': [('readonly', True)]})
    qty_pending = fields.Float("待报工数", compute="_compute_qty_pending",readonly=True, digits='Quantity')
    plm_task_qc_ids = fields.One2many('mrp.plm.task.qc', 'plm_task_conf_id', readonly=True)
    plm_task_qc_count = fields.Integer(compute='_compute_qc', copy=False, readonly=True)
    dealing_line_id = fields.Many2one('mrp.plm.task.defectdealing.line', '生产不良返工明细', readonly=True, help='关联生产不良处返工明细行id')
    ous_dealing_line_id = fields.Many2one('mrp.plm.ous.defectdealing.line', '委外不良返工明细', readonly=True, help='关联委外不良处返工明细行id')
    qty_qc = fields.Float('质检数量', digits='Quantity', compute='_compute_qc')
    qty_ok = fields.Float('质检数量', digits='Quantity', compute='_compute_qc')
    qty_bad = fields.Float('质检数量', digits='Quantity', compute='_compute_qc')
    
    state = fields.Selection([
                   ('draft', '草稿'),
                   ('done', '已确认')], string='状态', readonly=True, default='draft')

    @api.depends('plm_task_qc_ids')
    def _compute_qc(self):
        for l in self:
            l.qty_qc = sum(l1.qty for l1 in l.plm_task_qc_ids.filtered(lambda l2: l2.state == 'done'))
            l.qty_ok = sum(l1.qty_ok for l1 in l.plm_task_qc_ids.filtered(lambda l2: l2.state == 'done'))
            l.qty_bad = sum(l1.qty_bad for l1 in l.plm_task_qc_ids.filtered(lambda l2: l2.state == 'done'))
            l.plm_task_qc_count = len([l1 for l1 in l.plm_task_qc_ids])

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

    @api.depends('plm_task_id')
    def _compute_qty_pending(self):
        for l in self:
            l.qty_pending = 0
            if l.plm_task_id:
                l.qty_pending = l.plm_task_id.qty_task - l.plm_task_id.qty_conf
    
    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('报工%s,请不要重复确认！' % l.name)
            l.write({
                'state': 'done',
            })
            if l.plm_task_id:
                l.plm_task_id._compute_task_conf()
                if l.plm_task_id.qty_conf > l.plm_task_id.qty_task:
                    raise UserError('报工%s,报工数大于任务数！' % l.name)
                l.plm_task_id._create_task_conf()
            if not l.plm_proc_line_id.need_qc:
                if l.plm_task_id.qty_task <= l.plm_task_id.qty_conf:
                    if l.plm_task_id.state != 'done':
                        l.plm_task_id.button_done()
        self._create_task_qc()

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })
            if l.plm_task_id:
                l.plm_task_id._compute_task_conf()
            if not l.plm_proc_line_id.need_qc:
                if l.plm_task_id.qty_task > l.plm_task_id.qty_conf:
                    if l.plm_task_id.state == 'done':
                        l.plm_task_id.button_start()
            qc_ids = self.env['mrp.plm.task.qc'].search([('plm_task_conf_id', '=', l.id)])
            if len(qc_ids) > 0:
                qc_ids.unlink()

    def action_view_plm_task_qc(self):
        self.ensure_one()
        action = {
            'name': '生产质检报告',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.task.qc',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_qc_ids = [plm_qc.id for plm_qc in self.plm_task_qc_ids]
        # choose the view_mode accordingly
        if len(plm_qc_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_qc_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_qc_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_task_qc_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_qc_ids and plm_qc_ids[0] or False
        return action

    def _create_task_qc(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            if l.plm_proc_line_id.need_qc == True and l.qty - l.qty_qc > 0:                
                mrp_plm_id = rec.env['mrp.plm.task.qc'].create({
                    'company_id': l.company_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_task_id': l.plm_task_id.id,
                    'plm_task_conf_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': l.qty - l.qty_qc
                })
    
    def unlink(self):
        for l in self:
            if not l.state == 'draft':
                raise UserError('%s %s, 不为草稿状态，不许删除' % (self._description , l.name))
        super().unlink()
