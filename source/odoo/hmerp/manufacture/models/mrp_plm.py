from operator import le
from odoo import fields, api, models
from odoo.exceptions import UserError
import datetime


# 生产加工单确认状态可选值
MRP_PLM_STATES = [
    ('draft', '草稿'),
    ('done', '已确认'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class MrpPlm(models.Model):
    _name = "mrp.plm"
    _description = "生产加工单"

    @api.model
    def _default_warehouse(self):
        return self._default_warehouse_impl()

    @api.model
    def _default_warehouse_impl(self):
        if self.env.context.get('warehouse_type'):
            return self.env['warehouse'].get_warehouse_by_type(
                self.env.context.get('warehouse_type'))


    plm_in_count = fields.Integer(compute='_compute_plm_in', store=False, string='生产入库', default=0)
    plm_cons_count = fields.Integer(compute='_compute_plm_cons', store=False, string='生产领料', default=0)
    plm_cons_retu_count = fields.Integer(compute='_compute_plm_cons', store=False, string='生产退料', default=0)
    plm_cons_add_count = fields.Integer(compute='_compute_plm_cons', store=False, string='生产补料', default=0)
    plm_task_count = fields.Integer(compute='_compute_plm_task', store=False, string='生产任务单', default=0)
    plm_ous_count = fields.Integer(compute='_compute_plm_ous', store=False, string='工序委外订单', default=0)
    plm_in_ids = fields.One2many('mrp.plm.in', 'plm_id', string='生产入库', copy=False)
    plm_cons_ids = fields.One2many('mrp.plm.cons', 'plm_id', string='生产领料', copy=False)
    plm_cons_retu_ids = fields.One2many('mrp.plm.cons.retu', 'plm_id', string='生产退料', copy=False)
    plm_cons_add_ids = fields.One2many('mrp.plm.cons.add', 'plm_id', string='生产补料', copy=False)
    plm_task_ids = fields.One2many('mrp.plm.task', 'plm_id', string='生产任务单', copy=False)
    plm_ous_ids = fields.One2many('mrp.plm.ous', 'plm_id', string='委外任务单', copy=False)
    partner_id = fields.Many2one('partner', '客户', ondelete='restrict', states=READONLY_STATES,
                                 help='签约合同的客户')
    dealing_id = fields.Many2one('mrp.plm.task.defectdealing', '生产不良处理单')
    ous_dealing_id = fields.Many2one('mrp.plm.ous.defectdealing', '工序不良处理')
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states=READONLY_STATES,
                              help='单据经办人')

    date = fields.Date('单据日期', required=True, states=READONLY_STATES,
                       default=lambda self: fields.Date.context_today(self),
                       index=True, copy=False, help="默认是订单创建日期")

    delivery_date = fields.Date('要求完工日期', required=True, states=READONLY_STATES,
                                default=lambda self: fields.Date.context_today(self),
                                index=True, copy=False, help="生产加工单的要求完工日期")

    type = fields.Selection([('work', '生产加工'), ('rework', '生产返工')], '类型',
                            default='work', states=READONLY_STATES, help='生产加工单类型，分为生产加工或生产返工')
    ref = fields.Char('客户订单号', states=READONLY_STATES)
    warehouse_id = fields.Many2one('warehouse', '默认入库仓', ondelete='restrict', required=True, readonly=True,
                                   domain="['|',('user_ids','=',False),('user_ids','in',uid)]",
                                   states={'draft': [('readonly', False)]},
                                   default=_default_warehouse,
                                   help='移库单的来源仓库')
    department_id = fields.Many2one('staff.department', '生产部门', index=True,
                                    states=READONLY_STATES, ondelete='cascade')

    uom_id = fields.Many2one('uom', '单位', required=True, states=READONLY_STATES, ondelete='restrict', help='商品计量单位')
    name = fields.Char('单据编号', index=True, states=READONLY_STATES, copy=False, default='/', help="创建时它会自动生成下一个编号")
    goods_id = fields.Many2one('goods', '商品', required=True, ondelete='restrict',
                               states=READONLY_STATES, help='生产加工商品')
    bom_id = fields.Many2one('mrp.bom', 'Bom清单', index=True, states=READONLY_STATES, ondelete='cascade', help='加工商品的清单')

    qty = fields.Float('生产数量', digits='Quantity', states=READONLY_STATES, help='生产加工单生产数量')
    qty_task = fields.Float('计划数量', store=False, readonly=True)
    qty_in = fields.Float('已入库数量', compute='_compute_qty_in', copy=False, readonly=True, digits='Quantity', 
                          help='生产加工单已入库数量')
    qty_cons = fields.Float('已领材料套数', compute='_compute_qty_cons', copy=False, readonly=True, digits='Quantity', help='生产加工单已领材料套数')

    order_id = fields.Many2one('sell.order', '订单号', copy=False, readonly=True,
                               ondelete='cascade', help='mrp生产计划产的来源销售订单ID')
    order_line_id = fields.Many2one('sell.order.line', '销售订单行', copy=False, readonly=True,
                               ondelete='cascade', help='mrp生产计划产的来源销售订单行ID')
    plan_id = fields.Many2one('mrp.plan', 'MRP分析', readonly=True)
    plan_result_id = fields.Many2one('mrp.plan.result.line', 'MRP建议', readonly=True)
    plm_from_id = fields.Many2one('mrp.plm', '来源生产加工单', readonly=True)
    state = fields.Selection(MRP_PLM_STATES, '确认状态', readonly=True,
                             help="生产加工单的确认状态", index=True,
                             copy=False, default='draft')
    is_close = fields.Boolean('生产结案', readonly=True)
    remark = fields.Text('备注', help='单据备注')
    mrp_proc_ids = fields.One2many('mrp.proc', 'id', compute='_compute_mrp_proc_ids', store=False)    
    line_ids = fields.One2many('mrp.plm.line', 'plm_id', '生产加工单行', states=READONLY_STATES, copy=True,
                               help='生产加工单的明细行，不能为空')
    line_proc_ids = fields.One2many('mrp.plm.proc.line', 'plm_id', '工艺线路明细行', copy=True,
                                    states=READONLY_STATES)

    _sql_constraints = [
        ('qty_positive', 'check (qty > 0)', '生产数量必须是正数!'),
    ]

    def _compute_down_proc(self):
        for b in self:
            for p in b.line_proc_ids:
                str = ''
                l = b.line_proc_ids.search([('sequence', '=', p.sequence + 1), ('plm_id', '=', p.plm_id.id)])
                if len(l):
                    p.down_id = l[0].id
                else:
                    p.down_id = False

    @api.depends('line_proc_ids')
    def _compute_mrp_proc_ids(self):
        for b in self:
            if len(b.line_proc_ids) > 0:
                b.mrp_proc_ids = b.line_proc_ids.mapped('mrp_proc_id')
            else:
                b.mrp_proc_ids = False
                
    @api.depends('plm_in_ids')
    def _compute_plm_in(self):
        for plm in self:
            plm.plm_in_count = len([plm_in for plm_in in plm.plm_in_ids])
    @api.depends('plm_cons_ids', 'plm_cons_retu_ids')
    def _compute_plm_cons(self):
        for plm in self:
            plm.plm_cons_count = len([plm_cons for plm_cons in plm.plm_cons_ids])
            plm.plm_cons_retu_count = len([plm_cons for plm_cons in plm.plm_cons_retu_ids])
            plm.plm_cons_add_count = len([plm_cons for plm_cons in plm.plm_cons_add_ids])
    @api.depends('plm_task_ids')
    def _compute_plm_task(self):
        for plm in self:
            plm.plm_task_count = len([plm_task for plm_task in plm.plm_task_ids])
            for l in plm.line_proc_ids.filtered(lambda _l:_l.mrp_proc_id.get_way == 'self'):
                l.qty_task = sum(l1.qty_task for l1 in plm.plm_task_ids.filtered(\
                    lambda l2: not l2.state == 'draft' and l2.plm_proc_line_id.id == l.id))
    @api.depends('plm_ous_ids')
    def _compute_plm_ous(self):
        for plm in self:
            plm.plm_ous_count = len([plm_ous for plm_ous in plm.plm_ous_ids])
            for l in plm.line_proc_ids.filtered(lambda _l:_l.mrp_proc_id.get_way == 'ous'):
                l.qty_task = sum(l1.qty_task for l1 in plm.plm_ous_ids.filtered(\
                    lambda l2: l2.state == 'done' and l2.plm_proc_line_id.id == l.id))

    @api.depends('plm_in_ids')
    def _compute_qty_in(self):
        for l in self:
            l.qty_in = sum(sum(_i.goods_qty for _i in i.line_in_ids) for i in l.plm_in_ids.filtered(lambda line: line.state == 'done'))  

    @api.depends('plm_cons_ids')
    def _compute_qty_cons(self):
        for plm in self:
            plm.qty_cons = 0
            #plm.line_ids._compute_qty_to()
            if plm.line_ids:
                plm.qty_cons = min(l.qty_consed * (l.radix if l.radix > 0 else 1) / (l.qty_bom if l.qty_bom > 0 else 1) for l in plm.line_ids)

    @api.onchange('goods_id')
    def goods_id_onchange(self):
        for l in self:
            if l.goods_id and l.goods_id.uom_id:
                l.uom_id = l.goods_id.uom_id
            if l.goods_id and l.goods_id.out_warehouse_id:
                l.warehouse_id = l.goods_id.out_warehouse_id
            if l.goods_id:
                bom = self.env['mrp.bom'].search([('goods_id', '=', l.goods_id.id)])
                if bom and len(bom) > 0:
                    l.bom_id = bom[0].id

    @api.onchange('qty')
    def onchaing_qty(self):
        for p in self:
            for l in p.line_ids:
                l.qty = p.qty * l.qty_bom
                l.qty_waste = l.qty * l.rate_waste / 100
        self._compute_proc_line_rate_waste()

    @api.onchange('bom_id')
    def onchange_bom_id(self):
        for l in self:
            if l.bom_id and not l.goods_id:
                l.goods_id = l.bom_id.goods_id

            if l.bom_id and len(l.line_ids) == 0:
                if l.bom_id:
                    # 自动展开子件
                    line_ids = []
                    for line in l.bom_id.line_ids:
                        line_ids.append((0, 0, {
                            'goods_id': line.goods_id,
                            'warehouse_id': line.warehouse_id.id,
                            'uom_id': line.goods_id.uom_id.id,
                            'get_way': line.get_way,
                            'qty': line.qty * l.qty,
                            'radix': line.radix,
                            'qty_bom': line.qty,
                            'qty_waste': line.qty * line.rate_waste / 100,
                            'rate_waste': line.rate_waste,
                        }))
                    l.line_ids = line_ids


                    #自动展开工艺明细
                    line_proc_ids = []
                    for line in l.bom_id.line_proc_ids:
                        rate_self = line.rate_self
                        if line.get_way == 'self' and (not rate_self or rate_self <= 0):
                            rate_self = 100
                        if line.get_way == 'ous' and rate_self >= 100:
                            rate_self = 0
                        line_proc_ids.append((0, 0, {
                            'sequence': line.sequence,
                            'mrp_proc_id': line.mrp_proc_id,
                            'qty_proc': line.qty,
                            'qty': line.qty * l.qty,
                            'need_qc': line.need_qc,
                            'workcenter_id': line.workcenter_id,
                            'qc_department_id': line.qc_department_id,
                            'get_way': line.get_way,
                            'rate_self': rate_self,
                            'rate_waste': line.rate_waste,
                            'sub_remark': line.sub_remark,
                            'time_uom': line.time_uom,
                            'pre_time': line.pre_time,
                            'work_time': line.work_time,
                            'price_std': line.price_std,
                            'price': line.price,
                        }))
                    l.line_proc_ids = line_proc_ids

    def _compute_proc_line_rate_waste(self):
        for p in self:
            rate_up = False
            for l in sorted(p.line_proc_ids,key=lambda _l:_l.sequence, reverse = True):
                rate_waste = l.rate_waste
                if rate_up:
                    rate_waste += rate_up
                l.qty = l.qty_proc * p.qty * (100 + rate_waste) / 100
                rate_up = rate_waste

    def button_done(self):
        for line in self:
            if line.state == 'done':
                raise UserError('请不要重复确认！')
            if line.type == 'work' and not line.line_ids:
                raise UserError('请输入商品明细行！')
            line._compute_down_proc()
            self._compute_proc_line_rate_waste()
            """自动产生草稿的生产入库"""
            line._create_plm_in()
            """自动产生草稿的生产领料"""
            line._create_plm_cons()
            price_waring = line._create_plm_tasks()
            line.write({
                'state': 'done',
            })
            if line.dealing_id:
                line.dealing_id._compute_to_info()
            if line.ous_dealing_id:
                line.ous_dealing_id._compute_to_info()
            if (self.dealing_id and self.dealing_id.qty_replan < self.dealing_id.qty_replan_to) or \
               (self.ous_dealing_id and self.ous_dealing_id.qty_replan < self.ous_dealing_id.qty_replan_to):
                raise UserError('%s %s, 不能大于来源单重开数量' % (self._description, self.name))

    def button_draft(self):
        '''撤销确认生产入库'''
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销' % self._description)
        # 查找产生的入库单并删除
        plm_in = self.env['mrp.plm.in'].search(
            [('plm_id', '=', self.id)])
        plm_in.unlink()
        plm_cons = self.env['mrp.plm.cons'].search(
            [('plm_id', '=', self.id)])
        plm_cons.unlink()
        plm_task = self.env['mrp.plm.task'].search(
            [('plm_id', '=', self.id)])
        plm_task.unlink()   
        plm_ous = self.env['mrp.plm.ous'].search(
            [('plm_id', '=', self.id)])
        plm_ous.unlink()  

        self.write({
            'state': 'draft',
        })

    def _create_plm_in(self):
        '''由生产加工单，自动产生生产入库'''
        self.ensure_one()
        if self.qty <= self.qty_in:
            return {}
        plm_in_line = []  # 生产入库单行

        plm_in_line.append(self.get_plm_in_line(self, single=True))
        plm_in_id = self._generate_plm_in(plm_in_line)
        view_id = self.env.ref('manufacture.mrp_plm_in_form').id

        return {
            'name': '生产入库',
            'view_mode': 'form',
            'view_id': False,
            'views': [(view_id, 'form')],
            'res_model': 'mrp.plm.in',
            'res_id':plm_in_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def get_plm_in_line(self, line, single=False):
        '''返回生产入库行'''
        self.ensure_one()
        return {
            'type': 'in',
            'plm_id': line.id,
            'goods_id': line.goods_id.id,
            #'attribute_id': line.attribute_id.id,
            'uos_id': line.goods_id.uos_id.id,
            'goods_qty': line.qty - line.qty_in,
            'uom_id': line.uom_id.id,
            'plan_date':self.delivery_date,
        }

    def _generate_plm_in(self, plm_in_line):
        '''根据明细行生成入库单'''  
        warehouse = self.env.ref("warehouse.warehouse_production")      
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        mrp_plm_id = rec.env['mrp.plm.in'].create({
            'warehouse_id': warehouse.id,
            'warehouse_dest_id': self.warehouse_id.id,
            'date': self.date,
            'plm_id': self.id,
            'user_id':usr.id,
            'department_id':usr.department_id.id,
            'ref':self.ref,
            'origin': 'mrp.plm.in',
        })        
        mrp_plm_id.write({'line_in_ids': [(0, 0, line) for line in plm_in_line]})                
        return mrp_plm_id

    def _create_plm_cons(self):
        '''由生产加工单生成领料单'''
        self.ensure_one()
        gp_lines = {}
        for line in self.line_ids:
            # 如果订单部分入库，则点击此按钮时生成剩余数量的入库单
            to_in = line.qty + line.qty_waste - line.qty_to + line.qty_retu
            if to_in <= 0:
                continue
            l = self.get_plm_cons_line(line, single=False)
            if not line.warehouse_id.id in gp_lines.keys():
                gp_lines.setdefault(line.warehouse_id.id,[])
            gp_lines[line.warehouse_id.id].append(l)

        if not gp_lines:
            return {}
        plm_cons = self._generate_plm_cons(gp_lines)
        view_id = self.env.ref('manufacture.mrp_plm_cons_form').id

        return {
            'name': '领料单',
            'view_mode': 'form',
            'view_id': False,
            'views': [(view_id, 'form')],
            'res_model': 'mrp.plm.cons',
            'res_id': (plm_cons[0] if len(plm_cons) > 0 else 0),
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def _generate_plm_cons(self, gp_lines):
        '''根据明细行生成领料单,并按领料仓分单'''
        warehouse = self.env.ref("warehouse.warehouse_production")
        ids = []
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for line in gp_lines:
            mrp_plm_cons = rec.env['mrp.plm.cons'].create({
                'warehouse_id': line,
                'warehouse_dest_id': warehouse.id,
                'date': self.date,
                'plm_id': self.id,
                'user_id':usr.id,
                'department_id':usr.department_id.id,
                'ref':self.ref,
                'origin': 'mrp.plm.cons',
            })
            mrp_plm_cons.write({'line_out_ids': [(0, 0, l) for l in gp_lines[line]]})
            ids.append(mrp_plm_cons.id)
        return ids

    def get_plm_cons_line(self, line, single=False):
        '''返回领料行'''
        self.ensure_one()
        return {
            'type': 'out',
            'plm_id': line.plm_id.id,
            'plm_line_id': line.id,
            'goods_id': line.goods_id.id,
            #'attribute_id': line.attribute_id.id,
            'uos_id': line.goods_id.uos_id.id,
            'goods_qty': line.qty + line.qty_waste  - line.qty_to + line.qty_retu,
            'uom_id': line.uom_id.id,
            'warehouse_id': line.warehouse_id.id,
            #'cost_unit': line.price,
            #'price': line.price,
            #'price_taxed': line.price_taxed,
            #'discount_rate': line.discount_rate,
            #'discount_amount': discount_amount,
            #'tax_rate': line.tax_rate,
            #'note': line.note or '',
            'plan_date':self.delivery_date,
        }
    
    def action_view_plm_in(self):
        self.ensure_one()
        action = {
            'name': '生产入库',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.in',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_in_ids = [plm_in.id for plm_in in self.plm_in_ids]
        # choose the view_mode accordingly
        if len(plm_in_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_in_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_in_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_in_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_in_ids and plm_in_ids[0] or False
        return action

    def action_view_plm_cons(self):
        self.ensure_one()
        action = {
            'name': '领料单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.cons',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_cons_ids = [plm_cons.id for plm_cons in self.plm_cons_ids]
        # choose the view_mode accordingly
        if len(plm_cons_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_cons_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_cons_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_cons_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_cons_ids and plm_cons_ids[0] or False
        return action

    def button_retu(self):
        id = self._create_plm_cons_retu()
        if not id:
            return {}
        action = {
            'name': '生产退料',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.cons.retu',
            'view_id': False,
            'target': 'current',
        }

        view_id = self.env.ref('manufacture.mrp_plm_cons_retu_form').id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = id
        return action

    def _create_plm_cons_retu(self):
        self.ensure_one()
        warehouse = self.env.ref("warehouse.warehouse_production")
        lines = []
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self.line_ids:
            if l.qty_cons - l.qty_retu > 0:
                lines.append({
                    'type': 'in',
                    'plm_id': self.id,
                    'plm_line_id': l.id,
                    'goods_id': l.goods_id.id,
                    'uos_id': l.goods_id.uos_id.id,
                    'goods_qty': l.qty_cons - l.qty_retu,
                    'uom_id': l.uom_id.id
                })
        if len(lines) == 0:
            return False
        mrp_plm_cons = rec.env['mrp.plm.cons.retu'].create({
            'warehouse_id': warehouse.id,
            'date': self.date,
            'plm_id': self.id,
            'user_id':usr.id,
            'department_id':usr.department_id.id,
            'ref': self.ref,
            'origin': 'mrp.plm.cons.retu',
        })
        
        mrp_plm_cons.write({'line_in_ids': [(0, 0, l) for l in lines]})
        return mrp_plm_cons.id

    def action_view_plm_cons_retu(self):
        self.ensure_one()
        action = {
            'name': '生产退料',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.cons.retu',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_cons_retu_ids = [plm_cons_retu.id for plm_cons_retu in self.plm_cons_retu_ids]
        # choose the view_mode accordingly
        if len(plm_cons_retu_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_cons_retu_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_cons_retu_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_cons_retu_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_cons_retu_ids and plm_cons_retu_ids[0] or False
        return action

    def button_cons_add(self):
        self.ensure_one()
        id = self._create_plm_cons_add()
        if not id:
            return {}
        action = {
            'name': '生产补料',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.cons.add',
            'view_id': False,
            'target': 'current',
        }

        view_id = self.env.ref('manufacture.mrp_plm_cons_add_form').id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = id
        return action

    def _create_plm_cons_add(self):
        self.ensure_one()
        lines = []
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self.line_ids:
            lines.append({
                'plm_id': self.id,
                'plm_line_id': l.id,
                'goods_id': l.goods_id.id,
                'warehouse_id': l.warehouse_id.id,
                'qty': l.qty,
                'uom_id': l.uom_id.id
            })
        if len(lines) == 0:
            return False
        mrp_plm_cons = rec.env['mrp.plm.cons.add'].create({
            'department_id': self.department_id.id,
            'date': self.date,
            'plm_id': self.id,
            'user_id':usr.id,
            'department_id':usr.department_id.id,
        })
        
        mrp_plm_cons.write({'line_ids': [(0, 0, l) for l in lines]})
        return mrp_plm_cons.id

    def action_view_plm_cons_add(self):
        self.ensure_one()
        action = {
            'name': '生产补料',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.cons.add',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_cons_add_ids = [plm_cons_add.id for plm_cons_add in self.plm_cons_add_ids]
        # choose the view_mode accordingly
        if len(plm_cons_add_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_cons_add_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_cons_add_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_cons_add_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_cons_add_ids and plm_cons_add_ids[0] or False
        return action

    def _create_plm_tasks(self):
        """
        产生生产任务单，为排产计划做准备，其中包含的生产日计划明细（手工维护或APS排产产生）
        """
        rec = self.with_context(is_return=True)
        price_waring = ''
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for plm in self:
            up_task = False 
            price_waring_line = ''
            for p in plm.line_proc_ids:
                mrp_plm_task = False
                mrp_plm_task_line = {
                        'date': datetime.datetime.now(),
                        'user_id':usr.id,
                        'department_id':usr.department_id.id,
                        'plm_proc_line_id': p.id,
                        'workcenter_id': p.workcenter_id.id,
                        'goods_id': plm.goods_id.id,
                        'goods_uom_id': plm.uom_id.id,
                        'plm_id': plm.id,
                        'qty_task':plm.qty
                    }
                if p.get_way == 'self':            
                    mrp_plm_task = rec.env['mrp.plm.task'].create(mrp_plm_task_line)
                else:
                    mrp_plm_task = rec.env['mrp.plm.ous'].create(mrp_plm_task_line)
                    """通过价格策略取工序委外默认供应商和单价
                    mrp_plm_task.partner_id = self.env['ous.price.strategy'].get_partner(plm.goods_id,p.mrp_proc_id,mrp_plm_task.date)
                    if mrp_plm_task.partner_id:
                        price_msg, price_id = self.env['ous.price.strategy'].get_price_id(mrp_plm_task.partner_id, plm.goods_id,p.mrp_proc_id,mrp_plm_task.date)
                        if price_msg and price_msg != '':
                            price_waring_line += price_msg
                        if price_id:
                            mrp_plm_task.price = price_id.price
                            mrp_plm_task.price_taxed = price_id.price_taxed
                            mrp_plm_task.discount_rate = price_id.discount_rate
                            mrp_plm_task.tax_rate = plm.goods_id.get_tax_rate(plm.goods_id, mrp_plm_task.partner_id, 'buy')
                            mrp_plm_task.discount_amount = (mrp_plm_task.qty_task * price_id.price * price_id.discount_rate * 0.01)
                            mrp_plm_task.onchange_price()    
                            mrp_plm_task._compute_all_amount()
                    else:
                        price_waring_line += ('商品 %s 工序 %s 没有匹配到默认供应商' % (plm.goods_id.name, p.mrp_proc_id.name))
                    """
                if up_task != False:
                    if p.get_way == 'self':  
                        up_task.next_task_id = mrp_plm_task
                    else:
                        up_task.next_ous_id = mrp_plm_task
                up_task = mrp_plm_task
            if price_waring_line != '':
                if price_waring != '':
                    price_waring += '\n'
                price_waring += ('生产加工单 %s 委外价格策略检测\n   %s' % (plm.name, price_waring_line))
        return price_waring

    def action_view_plm_task(self):
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
        plm_task_ids = [plm_task.id for plm_task in self.plm_task_ids]
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

    def action_view_plm_ous(self):
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
        plm_ous_ids = [plm_ous.id for plm_ous in self.plm_ous_ids]
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

    def _write_cons(self):
        for plm in self:
            qty_cons = (l.qty_cons * (l.radix if l.radix > 0 else 1) / (l.qty_bom if l.qty_bom > 0 else 1) for l in plm.line_ids)
            plm.qty_cons = min(qty_cons)


class MrpPlmLine(models.Model):
    _name = "mrp.plm.line"
    _description = "加工单耗用材料明细"

    plm_id = fields.Many2one('mrp.plm', '加工单号', index=True, default=None, readonly=True, ondelete='cascade',
                             help='关联生产加工单ID')
    goods_id = fields.Many2one('goods', '商品', required=True, ondelete='restrict', help='商品')
    uom_id = fields.Many2one('uom', '单位', required=True, ondelete='restrict',
                             help='商品计量单位')
    warehouse_id = fields.Many2one('warehouse', '默认发料库', required=True, ondelete='restrict',
                                   help='生产领料默认从该仓库调出')
    qty = fields.Float('数量', default=1, required=True, digits='Quantity', help='下单数量')
    radix = fields.Float('基数', default=1, digits='Quantity')
    qty_waste = fields.Float('损耗量', default=1, digits='Quantity', help='下单数量')
    qty_bom = fields.Float('单位用量', default=1, digits='Quantity')
    rate_waste = fields.Float('损耗率(%)', digits='Quantity')
    get_way = fields.Selection([
        ('self', '自制'),
        ('ous', '委外'),
        ('po', '采购'),
    ], default='self', string='获取方式')
    qty_consed = fields.Float('实发数量', compute='_compute_qty_to', copy=False, digits='Quantity', help='生产加工单待耗用材料已领数量')
    qty_cons = fields.Float('已领数量', compute='_compute_qty_to', copy=False, digits='Quantity', help='生产加工单待耗用材料已领数量')
    qty_to = fields.Float('已转领料量', compute='_compute_qty_to', copy=False, store=False, digits='Quantity', 
                          default=0, help='生产加工单待耗用材料已转领数量')
    qty_retu = fields.Float('退料数量', compute='_compute_qty_to', copy=False, digits='Quantity', help='生产加工单待耗用材料退料数量')
    qty_retu_to = fields.Float('已转退料数量', compute='_compute_qty_to', copy=False, store=False, digits='Quantity', 
                          default=0, help='生产加工单待耗用材料已转退料数量')
    mrp_proc_id = fields.Many2one('mrp.proc', '领料工序', ondelete='cascade', help='绑定当前工序线路的工序')
    remark = fields.Char('备注', Default='')

    @api.depends('plm_id')
    def _compute_qty_to(self):
        for l in self:
            l.qty_to = sum(sum(l2.goods_qty for l2 in \
                        l1.line_out_ids.filtered(lambda _l:_l.plm_line_id.id == l.id)) for l1 in \
                        l.plm_id.plm_cons_ids)
            l.qty_cons = sum(sum(l2.goods_qty for l2 in \
                         l1.line_out_ids.filtered(lambda _l:_l.plm_line_id.id == l.id)) for l1 in \
                         l.plm_id.plm_cons_ids.filtered(lambda _l:_l.state == 'done'))
            l.qty_retu_to = sum(sum(l2.goods_qty for l2 in \
                            l1.line_in_ids.filtered(lambda _l:_l.plm_line_id.id == l.id)) for l1 in \
                            l.plm_id.plm_cons_retu_ids)
            l.qty_retu = sum(sum(l2.goods_qty for l2 in \
                            l1.line_in_ids.filtered(lambda _l:_l.plm_line_id.id == l.id)) for l1 in \
                            l.plm_id.plm_cons_retu_ids.filtered(lambda _l:_l.state == 'done'))
            l.qty_consed = l.qty_cons - l.qty_retu

    @api.onchange('qty','radix')
    def onchange_qty_radix(self):        
        for b in self:
            if not b.plm_id or b.plm_id.qty <= 0:
                raise UserError('请先录入大于0的母件数量')
            else:
                if not b.radix or b.radix <= 0:
                    b.radix = 1
                b.qty_bom = b.qty * 100 / b.plm_id.qty / b.radix / 100 if b.plm_id.qty > 0 else 1

    @api.onchange('goods_id')
    def goods_id_onchange(self):
        for l in self:
            if l.goods_id:
                l.get_way = l.goods_id.get_way

class MrpPlmProcLine(models.Model):
    _name = "mrp.plm.proc.line"
    _description = "工艺线路"
    _order = 'sequence, id'
    
    plm_id = fields.Many2one('mrp.plm', '母件Bom编号', index=True, default=None, ondelete='cascade',
                             help='关联生产加工单的编号')
    sequence = fields.Integer('序号', help='此序号决定的工艺线路的顺序，调整后自动挂接承上工序和转下工序')
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', required=True, ondelete='restrict',)
    down = fields.Char('转下工序', compute='_compute_down', readolny=True)
    down_id = fields.Many2one('mrp.plm.proc.line', 'down_id', readonly=True, ondelete='cascade',
                              help='此栏位由工序状态确认后自动回填')
    qty = fields.Float('加工数量', digits='Quantity')
    qty_proc = fields.Float('单位数量', default=1, digits='Quantity', readonly=True)
    #up_proc = fields.Char('承上工序', compute=_compute_up_proc, readonly=True)
    proc_ctl = fields.Boolean('工序控制', default=0, help='勾选后，转下工序的可报工数，为当前工序的有效完工数(有效完工数：无质检时为报工数，否则为质检合格数)')
    need_qc = fields.Boolean('需检验', default=0)
    qc_department_id = fields.Many2one('staff.department', '质检部门', index=True, ondelete='cascade')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心')
    plm_task_ids = fields.One2many('mrp.plm.task', 'plm_proc_line_id', string='计划明细')
    plm_ous_ids = fields.One2many('mrp.plm.ous', 'plm_proc_line_id', string='计划明细')
    plm_task_conf_ids = fields.One2many('mrp.plm.task.conf', 'plm_proc_line_id', string='报工明细')
    plm_task_qc_ids = fields.One2many('mrp.plm.task.qc', 'plm_proc_line_id', string='质检报告明细')
    qty_task = fields.Float('计划数量', compute='_compute_task_ids', digits='Quantity',readonly=True)
    qty_conf = fields.Float('报工数量', compute='_compute_task_conf_ids', digits='Quantity',readonly=True)
    qty_ok = fields.Float('合格数量', compute='_compute_task_qc_ids', digits='Quantity',readonly=True)
    qty_bad = fields.Float('不良数量', compute='_compute_task_qc_ids', digits='Quantity',readonly=True)
    get_way = fields.Selection([('self', '自制'), ('ous', '委外')],
                               '获取方式', required=True, default='self')
    rate_self = fields.Float('自制比率', digits='Quantity')
    sub_remark = fields.Char('作业描述', default='')
    rate_waste = fields.Float('损耗率', digits='Quantity')
    time_uom = fields.Selection([('s', '秒'), ('m', '分钟'), ('h', '小时')],
                                '时间单位', default='s')
    pre_time = fields.Float('准备时间', digits='Quantity')
    work_time = fields.Float('耗用工时', digits='Quantity')
    price_std = fields.Float('标准工价', digits='Quantity')
    price = fields.Float('加工工价', digits='Quantity')
    remark = fields.Char('备注', Default='')

    # 计算工序叠加损耗，除修改行外，其余行界面未修改问题，以下代码暂不启用
    # values=[]
    # for l in sorted(line.plm_id.line_proc_ids,key=lambda _l:_l.sequence, reverse = True):
    #     rate_waste = l.rate_waste
    #     if rate_up:
    #         rate_waste += rate_up
    #     l.qty = l.qty_proc * l.plm_id.qty * (100 + rate_waste) / 100
    #     rate_up = rate_waste

    def change_line_qty(self):
        for line in self.plm_id.line_proc_ids:
            sequence = line.sequence
            proc_ids = line.plm_id.line_proc_ids.filtered(lambda l: l.sequence<=sequence)
            rate_waste = sum(proc_ids.mapped('rate_waste'))
            line.qty = line.qty_proc * line.plm_id.qty * (100 + rate_waste) / 100

    @api.onchange('sequence', 'rate_waste')
    def _onchange_proc_line(self):
        self.change_line_qty()

    @api.depends('plm_task_ids')
    def _compute_task_ids(self):
        for line in self:
            line.qty_task = sum(l.qty_task for l in line.plm_task_ids.filtered(lambda l1: l1.state != 'draft'))
            
    @api.depends('plm_task_conf_ids')
    def _compute_task_conf_ids(self):
        for line in self:
            line.qty_conf = sum(l.qty for l in line.plm_task_conf_ids.filtered(lambda l1: l1.state == 'done'))
            
    @api.depends('plm_task_qc_ids')
    def _compute_task_qc_ids(self):
        for line in self:
            line.qty_ok = sum(l.qty_ok for l in line.plm_task_qc_ids.filtered(lambda l1: l1.state == 'done'))
            line.qty_bad = sum(l.qty_ok for l in line.plm_task_qc_ids.filtered(lambda l1: l1.state == 'done'))

    @api.depends('down_id')
    def _compute_down(self):
        for cur_l in self:
            search_l = self.search([('id', '=', cur_l.down_id.id), ('plm_id', '=', cur_l.plm_id.id)])
            if len(search_l) > 0:
                cur_l.down = search_l[0].mrp_proc_id.name
            else:
                cur_l.down = False

    @api.onchange('get_way')
    def get_way_onchange(self):
        for l in self:
            if l.get_way == 'self' and (not l.rate_self or l.rate_self <= 0):
                l.rate_self = 100
            if l.get_way == 'ous' and l.rate_self >= 100:
                l.rate_self = 0

    @api.onchange('mrp_proc_id')
    def mrp_proc_id_onchange(self):
        for l in self:
            if l.mrp_proc_id:
                l.workcenter_id = l.mrp_proc_id.workcenter_id
                l.proc_ctl = l.mrp_proc_id.proc_ctl
                l.need_qc = l.mrp_proc_id.need_qc
                l.qc_department_id = l.mrp_proc_id.qc_department_id
                l.get_way = l.mrp_proc_id.get_way
                l.rate_self = (0 if l.get_way == 'ous' else 100)
                l.rate_waste = l.mrp_proc_id.rate_waste
                l.sub_remark = l.mrp_proc_id.sub_remark
                l.time_uom = l.mrp_proc_id.time_uom
                l.pre_time = l.mrp_proc_id.pre_time
                l.work_time = l.mrp_proc_id.work_time
                l.price_std = l.mrp_proc_id.price_std
                l.price = l.mrp_proc_id.price
                l.qty = l.plm_id.qty * l.qty_proc

    