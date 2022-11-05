from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpPlmTask(models.Model):
    _name = 'mrp.plm.task'
    _description = '生产任务单'
    name = fields.Char('任务单号', required=True)
    company_id = fields.Many2one('res.company', '公司', default=lambda self: self.env.company, required=True, index=True, readonly=True)
    date = fields.Date('单据日期', required=True, states={'done': [('readonly', True)]},
                       default=lambda self: fields.Date.context_today(self),
                       index=True, copy=False, help="默认是订单创建日期")
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states={'done': [('readonly', True)]}, ondelete='cascade')
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states={'done': [('readonly', True)]},
                              help='单据经办人')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心', states={'done': [('readonly', True)]})
    goods_id = fields.Many2one('goods', '加工商品', readonly=True)
    goods_uom_id = fields.Many2one('uom', '单位', index=True, readonly=True, required=True, ondelete='cascade')
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, help='关联生产加工单ID')    
    plm_proc_line_id = fields.Many2one('mrp.plm.proc.line', '工序来源行', readonly=True, help='关联生产加工单工艺明细行ID')
    next_task_id = fields.Many2one('mrp.plm.task', '转下工序任务', readonly=True)
    next_ous_id = fields.Many2one('mrp.plm.ous', '转下工序委外任务', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', compute='_compute_mrp_proc_id', readonly=True)
    next_mrp_proc_id = fields.Many2one('mrp.proc', '转下工序', compute='_compute_next_proc_id', readonly=True)
    next_mrp_proc_get_way = fields.Char('转下工序获取方式', compute='_compute_next_proc_id', readonly=True)
    qty_task = fields.Float('生产数量', states={'done': [('readonly', True)]}, digits='Quantity')
    task_conf_ids = fields.One2many('mrp.plm.task.conf', 'plm_task_id', readonly=True)
    qty_conf = fields.Float('报工数量', compute='_compute_task_conf', copy=False, readonly=True, digits='Quantity')
    task_conf_count = fields.Integer(compute='_compute_task_conf', store=False, string='生产报工数量', default=0)
    dealing_id = fields.Many2one('mrp.plm.task.defectdealing', '生产不良处理', readonly=True, help='关联生产不良处id')
    dealing_line_id = fields.Many2one('mrp.plm.task.defectdealing.line', '生产不良返工明细', readonly=True, help='关联生产不良处理返工明细行id')
    ous_dealing_id = fields.Many2one('mrp.plm.ous.defectdealing', '委外不良处理', readonly=True, help='关联委外不良处理id')
    ous_dealing_line_id = fields.Many2one('mrp.plm.ous.defectdealing.line', '委外不良返工明细', readonly=True, help='关联委外不良处理返工明细行id')
    rework_task_id = fields.Many2one('mrp.plm.task', '关联生产任务', readonly=True, help='关联由不良处理单的来源生产任务ID')
    rework_task_ids = fields.One2many('mrp.plm.task', 'rework_task_id', readonly=True, help='质检不良处理单中返工产生的生产任务单')
    rework_ous_id = fields.Many2one('mrp.plm.ous', '关联生产任务', readonly=True, help='关联由不良处理单的来源生产任务ID')
    rework_ous_ids = fields.One2many('mrp.plm.ous', 'rework_ous_id', readonly=True, help='质检不良处理单中返工产生的生产任务单')
    date_planned_start = fields.Datetime(
        '计划开工日期',
        compute='_compute_dates_planned',
        states={'done': [('readonly', True)]},
        store=True,
        tracking=True)
    date_planned_finished = fields.Datetime(
        '计划完工日期',
        compute='_compute_dates_planned',
        states={'done': [('readonly', True)]},
        store=True,
        tracking=True)

    date_start = fields.Datetime(
        '实际开工日期',
        states={'done': [('readonly', True)]})
    date_finished = fields.Datetime(
        '实际完工日期 End Date',
        states={'done': [('readonly', True)]})
    state = fields.Selection([
        ('draft', '草稿'),
        ('ready', '就绪'),
        ('pause', '暂停'),
        ('progress', '进行中'),
        ('done', '已完成'),
        ('cancel', '已取消')], string='Status',
        default='draft', readonly=True)
    
    worksheet = fields.Binary('Worksheet', states={'done': [('readonly', True)]})
    worksheet_google_slide = fields.Char('Worksheet URL', readonly=True)
    
    proc_mat_ids = fields.Many2many('mrp.plm.line', store=False, compute='_compute_proc_mat_ids')
    line_ids = fields.One2many('mrp.plm.task.line', 'plm_task_id', states={'done': [('readonly', True)]})

    @api.depends('plm_id')
    def _compute_proc_mat_ids(self):
        for l in self:
            mat_ids = []
            if l.plm_id:
                mat_ids = l.plm_id.line_ids.filtered(lambda l2:l2.mrp_proc_id == l.mrp_proc_id)    
            l.proc_mat_ids = mat_ids if mat_ids and len(mat_ids) > 0 else False

    @api.depends('plm_proc_line_id', 'dealing_line_id', 'ous_dealing_line_id')
    def _compute_mrp_proc_id(self):
        for t in self:
            t.mrp_proc_id = False
            if t.dealing_line_id:
                t.mrp_proc_id = t.plm_proc_line_id.mrp_proc_id
            elif t.ous_dealing_line_id:
                t.mrp_proc_id = t.ous_dealing_line_id.mrp_proc_id
            elif t.plm_proc_line_id:
                t.mrp_proc_id = t.plm_proc_line_id.mrp_proc_id

    @api.depends('task_conf_ids')
    def _compute_task_conf(self):
        for l in self:
            l.qty_conf = sum(c.qty for c in l.task_conf_ids.filtered(lambda line: line.state == 'done'))
            l.task_conf_count = len([l1 for l1 in l.task_conf_ids])
    
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

    @api.onchange('line_ids')
    def onchange_line_ids(self):
        for t in self:
            t.qty_conf = sum(((l.qty_conf if l.qty_conf > 0 else 0) for l in t.line_ids))

    def _compute_dates_planned(self):
        for workorder in self:
            workorder.date_planned_start = fields.Date.context_today(self)
            workorder.date_planned_finished = fields.Date.context_today(self)

    def button_ready(self):
        """
        """
        self.ensure_one()
        if self.state == 'ready':
            raise UserError('请不要重复确认！')
        self.write({
            'state': 'ready',
        })
    def button_start(self):
        """
        """
        self.ensure_one()
        if self.state == 'progress':
            raise UserError('请不要重复确认！')
        self.write({
            'state': 'progress',
        })
        self._create_task_conf()

    def button_done(self):
        """
        """
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复完成！')
        self.write({
            'state': 'done',
        })

    def button_pause(self):
        """
        """
        self.ensure_one()
        if self.state == 'pause':
            raise UserError('请不要重复暂停！')
        self.write({
            'state': 'pause',
        })

    def button_draft(self):
        """
        """
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤回！')
        self.write({
            'state': 'draft',
        })
        plm_task_conf = self.env['mrp.plm.task.conf'].search(
            [('plm_task_id', '=', self.id)])
        plm_task_conf.unlink()

    def _create_task_conf(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            draft_count = len([l1 for l1 in l.task_conf_ids.filtered(lambda _l: _l.state == 'draft')])
            if draft_count == 0 and l.qty_task > l.qty_conf:
                mrp_plm_id = rec.env['mrp.plm.task.conf'].create({
                    'company_id': l.company_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_task_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': l.qty_task - l.qty_conf
                })

    def action_view_plm_task_conf(self):
        self.ensure_one()
        action = {
            'name': '生产报工',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.task.conf',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_conf_ids = [plm_conf.id for plm_conf in self.task_conf_ids]
        # choose the view_mode accordingly
        if len(plm_conf_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_conf_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_conf_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_task_conf_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_conf_ids and plm_conf_ids[0] or False
        return action

    def unlink(self):
        for l in self:
            if not l.state == 'draft':
                raise UserError('%s %s, 不为草稿状态，不许删除' % (self._description , l.name))
        super().unlink()

class MrpPlmTaskLine(models.Model):
    _name = 'mrp.plm.task.line'
    _description = '生产任务计划明细'
    _order = 'date_start'

    plm_task_id = fields.Many2one('mrp.plm.task', '生产任务单', help='关联生产任务单头ID')
    qty = fields.Float('计划任务数量', digits='Quantity')
    qty_times = fields.Float('计划占用工时', digits='Quantity')
    qty_conf = fields.Float('完工数量', digits='Quantity')
    date_start = fields.Datetime('开工日期')
    date_finished = fields.Datetime('完工时间')
    times = fields.Float('实际生产工时', digits='Quantity', readonly=True)

    @api.onchange('qty_conf')
    def qty_conf_onchange(self):
        for l in self:
            if l.qty <= l.qty_conf and not l.date_finished:
                l.date_finished = datetime.now()
        

