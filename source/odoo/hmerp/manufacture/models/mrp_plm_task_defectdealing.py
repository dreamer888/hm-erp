from odoo import fields, api, models
from odoo.exceptions import UserError
import datetime


class MrpPlmTaskDefectdealing(models.Model):
    _name = "mrp.plm.task.defectdealing"
    _description = "不良处理单"

    
    name = fields.Char('工序质检报告', required=True)
    company_id = fields.Many2one('res.company', '公司', default=lambda self: self.env.company, required=True, index=True, readonly=True)
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states={'done': [('readonly', True)]}, ondelete='cascade')
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states={'done': [('readonly', True)]},
                              help='单据经办人')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心', states={'done': [('readonly', True)]})
    goods_id = fields.Many2one('goods', '加工商品', readonly=True)
    goods_uom_id = fields.Many2one('uom', '单位', index=True, readonly=True, required=True, ondelete='cascade')
    plm_task_id = fields.Many2one('mrp.plm.task', '生产任务单', readonly=True, help='关联生产任务ID')
    plm_ous_id = fields.Many2one('mrp.plm.ous', '工序委外订单', readonly=True, help='关联生产任务ID')
    plm_task_qc_id = fields.Many2one('mrp.plm.task.qc', '工序不良处理单', readonly=True, help='关联生产报工ID')    
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, help='关联生产加工单ID')
    plm_proc_line_id = fields.Many2one('mrp.plm.proc.line', '工序来源行', readonly=True, help='关联生产加工单工艺明细行ID')
    next_task_id = fields.Many2one('mrp.plm.task', '转下工序任务', readonly=True)
    next_ous_id = fields.Many2one('mrp.plm.ous', '转下工序委外任务', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '质检工序', compute='_compute_mrp_proc_id', readonly=True)
    next_mrp_proc_id = fields.Many2one('mrp.proc', '转下工序', readonly=True, compute='_compute_next_proc_id')
    next_mrp_proc_get_way = fields.Char('转下工序获取方式', compute='_compute_next_proc_id', readonly=True)
    qty = fields.Float('不良处理数量', digits='Quantity', readonly=True)
    qty_pending = fields.Float('待处理数量', digits='Quantity', compute='_compute_qty_pending', readonly=True)
    qty_rework = fields.Float('返工数量', compute='_compute_rework', digits='Quantity', help='返工数量')
    qty_scrap = fields.Float('报废数量', states={'done': [('readonly', True)]}, digits='Quantity', help='报废数量')
    qty_replan = fields.Float('重工数量', states={'done': [('readonly', True)]}, digits='Quantity', help='重开生产加工单数量')
    qty_retu = fields.Float('退回数量', digits='Quantity', states={'done': [('readonly', True)]}, help='重开生产加工单数量')
    qty_scrap_to = fields.Float(compute='_compute_to_info', digits='Quantity')
    qty_replan_to = fields.Float(compute='_compute_to_info', digits='Quantity')
    qty_retu_to = fields.Float('已转退回数量', compute='_compute_to_info', digits='Quantity', help='重开生产加工单数量')
    state = fields.Selection([
                   ('draft', '草稿'),
                   ('done', '已确认')], string='状态',
                   default='draft', readonly=True)
    rework_line_ids = fields.One2many('mrp.plm.task.defectdealing.line', 'dealing_id', states={'done': [('readonly', True)]}, string='返工任务明细')
    dealing_ids = fields.One2many(string='生产质检不良明细', related='plm_task_qc_id.line_ids', readonly=True)
    mrp_plm_task_ids = fields.One2many('mrp.plm.task', 'dealing_id', readonly=True)
    mrp_plm_ous_ids = fields.One2many('mrp.plm.ous', 'dealing_id', readonly=True)
    mrp_plm_ids = fields.One2many('mrp.plm', 'dealing_id', readonly=True)
    mrp_plm_scrap_ids = fields.One2many('mrp.plm.scrap', 'dealing_id', readonly=True)
    dealing_line_id = fields.Many2one('mrp.plm.task.defectdealing.line', '生产不良返工明细', readonly=True, help='关联生产不良处返工明细行id')
    ous_dealing_line_id = fields.Many2one('mrp.plm.ous.defectdealing.line', '委外不良返工明细', readonly=True, help='关联委外不良处返工明细行id')

    mrp_plm_task_count = fields.Integer(compute='_compute_to_info', readonly=True)
    mrp_plm_ous_count = fields.Integer(compute='_compute_to_info', readonly=True)
    mrp_plm_count = fields.Integer(compute='_compute_to_info', readonly=True)
    mrp_plm_scrap_count = fields.Integer(compute='_compute_to_info', readonly=True)
    
    @api.depends('mrp_plm_task_ids', 'mrp_plm_ous_ids', 'mrp_plm_ids', 'mrp_plm_scrap_ids')
    def _compute_to_info(self):
        for l in self:
            l.mrp_plm_task_count = len([l1 for l1 in l.mrp_plm_task_ids])
            l.mrp_plm_ous_count = len([l1 for l1 in l.mrp_plm_ous_ids])
            l.mrp_plm_count = len([l1 for l1 in l.mrp_plm_ids])
            l.mrp_plm_scrap_count = len([l1 for l1 in l.mrp_plm_scrap_ids])
            l.qty_scrap_to = sum(l1.qty for l1 in l.mrp_plm_scrap_ids.filtered(lambda l2:l2.state == 'done'))
            l.qty_replan_to = sum(l1.qty for l1 in l.mrp_plm_ids.filtered(lambda l2:l2.state == 'done'))
            for l1 in l.rework_line_ids.filtered(lambda _l:_l.mrp_proc_id.get_way == 'self'):
                l1.qty_task = sum(l2.qty_task for l2 in l.mrp_plm_task_ids.filtered(\
                    lambda l3: not l3.state == 'draft' and l3.plm_proc_line_id.id == l1.id))

    @api.depends('mrp_plm_ous_ids')
    def _compute_plm_ous(self):
        for l in self:
            l.mrp_plm_ous_count = len([plm_ous for plm_ous in l.mrp_plm_ous_ids])
            for l in l.rework_line_ids.filtered(lambda _l:_l.mrp_proc_id.get_way == 'ous'):
                l.qty_task = sum(l1.qty_task for l1 in l.mrp_plm_ous_ids.filtered(\
                    lambda l2: l2.state == 'done' and l2.plm_proc_line_id.id == l.id))

    @api.depends('plm_task_qc_id')
    def _compute_qty_pending(self):
        for line in self:
            line.qty_pending = line.plm_task_qc_id.qty_bad - line.plm_task_qc_id.qty_dealing

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

    @api.depends('qty', 'qty_replan', 'qty_scrap', 'qty_retu')
    def _compute_rework(self):
        for l in self:
            l.qty_rework = l.qty - l.qty_scrap - l.qty_replan - l.qty_retu
            if l.rework_line_ids:
                for l1 in l.rework_line_ids:
                    l1.qty = l.qty_rework
    
    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('%s %s,请不要重复确认！' % (l._description, l.name))
            if l.qty <= 0:
                raise UserError('%s %s, 不良处理数量必需大于0！' % (l._description, l.name))
            if l.qty_rework < 0:
                raise UserError('%s %s, 返工数量不许小于0！' % (l._description, l.name))
            if l.qty_rework > 0 and len([l1 for l1 in l.rework_line_ids]) == 0:
                raise UserError('%s %s, 返工数量大于0时，返工明细不能为空！' % (l._description, l.name))
            l.write({
                'state': 'done',
            })
            if l.plm_task_qc_id:
                l.plm_task_qc_id._compute_plm_task_defectdealing()
                l._compute_qty_pending()
                if l.qty_pending < 0:
                    raise UserError('%s %s,不良处理数量大于不良数量！' % (l._description, l.name))
                l.plm_task_qc_id._create_plm_task_defectdealing()

        self._create_mrp_plm_task()
        self._create_mrp_plm_scrap()
        self._create_mrp_plm()

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })
            plm = self.env['mrp.plm'].search(
                [('dealing_id', '=', l.id)])
            plm.unlink()
            plm_ous = self.env['mrp.plm.ous'].search(
                [('dealing_id', '=', l.id)])
            plm_ous.unlink()
            plm_task = self.env['mrp.plm.task'].search(
                [('dealing_id', '=', l.id)])
            plm_task.unlink()  
            plm_scrap = self.env['mrp.plm.scrap'].search(
                [('dealing_id', '=', l.id)])
            plm_scrap.unlink()   

    def _create_mrp_plm_task(self):
        """
        产生返工任务单
        """
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            if l.qty_rework > 0:
                up_task = False 
                for p in l.rework_line_ids:
                    mrp_plm_task = False
                    mrp_plm_task_line = {
                            'user_id':usr.id,
                            'department_id':usr.department_id.id,
                            'plm_proc_line_id': l.plm_proc_line_id.id,
                            'rework_task_id': l.plm_task_id.id,
                            'rework_ous_id': l.plm_ous_id.id,
                            'workcenter_id': p.workcenter_id.id,
                            'dealing_id': l.id,
                            'goods_id': l.goods_id.id,
                            'goods_uom_id': l.goods_uom_id.id,
                            'plm_id': l.plm_id.id,
                            'qty_task':l.qty
                        }
                    if p.get_way == 'self':            
                        mrp_plm_task = rec.env['mrp.plm.task'].create(mrp_plm_task_line)
                        mrp_plm_task.dealing_line_id = p.id
                    else:
                        mrp_plm_task = rec.env['mrp.plm.ous'].create(mrp_plm_task_line)
                        mrp_plm_task.ous_dealing_line_id = p.id
                    
                    if up_task != False:
                        if p.get_way == 'self':  
                            up_task.next_task_id = mrp_plm_task
                        else:
                            up_task.next_ous_id = mrp_plm_task
                    up_task = mrp_plm_task
        
    def _create_mrp_plm(self):
        """
        产生重开生产加工单
        """
        rec = self.with_context(is_return=True)
        for l in self:
            if l.qty_replan - l.qty_replan_to > 0:
                mrp_plm_id = rec.env['mrp.plm'].create({
                    'partner_id': l.plm_id.partner_id.id,
                    'user_id': l.plm_id.user_id.id,
                    'date': datetime.datetime.now(),
                    'type': 'work',
                    'ref': l.plm_id.ref,
                    'warehouse_id': l.plm_id.warehouse_id.id,
                    'department_id': l.plm_id.department_id.id,
                    'uom_id': l.plm_id.uom_id.id,
                    'goods_id': l.plm_id.goods_id.id,
                    'bom_id': l.plm_id.bom_id.id,
                    'order_id': l.plm_id.order_id.id,
                    'dealing_id': l.id,
                    'plm_from_id': l.plm_id.id,
                    'remark': l.plm_id.remark
                })
                for l1 in l.plm_id.line_ids:
                    mrp_plm_line_id = rec.env['mrp.plm.line'].create({
                        'plm_id': mrp_plm_id.id,
                        'goods_id': l1.goods_id.id,
                        'uom_id': l1.uom_id.id,
                        'warehouse_id': l1.warehouse_id.id,
                        'qty_bom': l1.qty_bom,
                        'radix': l1.radix,
                        'rate_waste': l1.rate_waste,
                        'mrp_proc_id': l1.mrp_proc_id.id,
                        'remark': l1.remark
                    })
                for l2 in l.plm_id.line_proc_ids:
                    mrp_plm_line_proc_id = rec.env['mrp.plm.proc.line'].create({
                        'plm_id': mrp_plm_id.id,
                        'sequence': l2.sequence,
                        'mrp_proc_id': l2.mrp_proc_id.id,
                        'qty_proc': l2.qty_proc,
                        'proc_ctl': l2.proc_ctl,
                        'need_qc': l2.need_qc,
                        'qc_department_id': l2.qc_department_id.id,
                        'workcenter_id': l2.workcenter_id.id,
                        'get_way': l2.get_way,
                        'rate_self': l2.rate_self,
                        'sub_remark': l2.sub_remark,
                        'rate_waste': l2.rate_waste,
                        'time_uom': l2.time_uom,
                        'pre_time': l2.pre_time,
                        'work_time': l2.work_time,
                        'price_std': l2.price_std,
                        'price': l2.price,
                        'remark': l2.remark
                    })
                mrp_plm_id.qty = l.qty_replan - l.qty_replan_to

    def unlink(self):
        for l in self:
            if not l.state == 'draft':
                raise UserError('%s %s, 不为草稿状态，不许删除' % (self._description , l.name))
        super().unlink()
    
    def action_view_mrp_plm(self):
        self.ensure_one()
        action = {
            'name': '生产加工单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ids = [plm.id for plm in self.mrp_plm_ids]
        # choose the view_mode accordingly
        if len(plm_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ids and plm_ids[0] or False
        return action

    def action_view_mrp_plm_task(self):
        self.ensure_one()
        action = {
            'name': '生产任务单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.task',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_task_ids = [plm.id for plm in self.mrp_plm_task_ids]
        # choose the view_mode accordingly
        if len(plm_task_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_task_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_task_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_task_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_task_ids and plm_task_ids[0] or False
        return action
    def action_view_mrp_plm_ous(self):
        self.ensure_one()
        action = {
            'name': '工序委外订单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_ids = [plm.id for plm in self.mrp_plm_ous_ids]
        # choose the view_mode accordingly
        if len(plm_ous_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ous_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ous_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_ous_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ous_ids and plm_ous_ids[0] or False
        return action

    def action_view_mrp_plm_scrap(self):
        self.ensure_one()
        action = {
            'name': '生产报废报告',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.scrap',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_scrap_ids = [plm_scrap.id for plm_scrap in self.mrp_plm_scrap_ids]
        # choose the view_mode accordingly
        if len(plm_scrap_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_scrap_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_scrap_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_scrap_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_scrap_ids and plm_scrap_ids[0] or False
        return action

    def _create_mrp_plm_scrap(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_scrap = l.qty_scrap - l.qty_scrap_to
            if qty_scrap > 0:          
                mrp_plm_id = rec.env['mrp.plm.scrap'].create({
                    'dealing_id': l.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'company_id': l.company_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': qty_scrap
                })


class MrpPlmTaskDefectdealingLine(models.Model):
    _name = 'mrp.plm.task.defectdealing.line'
    _description = '生产不良返工明细'    
    _inherit = 'mrp.plm.proc.line'

    dealing_id = fields.Many2one('mrp.plm.task.defectdealing', '不良处理', readonly=True)
    qty = fields.Float('加工数量', compute='_compute_qty',  digits='Quantity')

    @api.depends('dealing_id')
    def _compute_qty(self):
        for l in self:
            if l.dealing_id:
                l.qty = l.dealing_id.qty_rework

    @api.onchange('mrp_proc_id')
    def mrp_proc_id_onchange(self):
        super().mrp_proc_id_onchange()
        for l in self:
            if l.dealing_id and l.qty == 0:
                l.qty = l.dealing_id.qty_rework