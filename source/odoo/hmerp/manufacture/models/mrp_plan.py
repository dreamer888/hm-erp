from odoo import fields, api, models
from odoo.exceptions import UserError
import datetime


# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
}


class MrpPlanConfig(models.Model):
    _name = 'mrp.plan.config'
    _description = '分析参数'
    #取值参数
    none_stock = fields.Boolean('不考虑可用库存')
    none_stock_somat = fields.Boolean('订单商品不考虑库存')
    nage_stock_append =fields.Boolean('负可用库存追加净需求', default=True)
    mix_batch_plan = fields.Boolean('考虑最少批量(采购/委外/生产)')
    batch_plan = fields.Boolean('考虑批量(采购/委外/生产)')   
    propose = fields.Selection([
        ('net', '净需求'),
        ('gross', '毛需求'),
    ], default='net', string='建议量取值')
    holidy_type = fields.Selection([
        ('single', '单休'),
        ('double', '双休'),
        ('calendar', '行事日历'),
        ('none', '无休假'),
    ], default='single', string='假日类型')
    holidy_plan = fields.Selection([
        ('backward', '预交日期倒推'),
        ('forward', '当前日期顺推'),
    ], default='backward', string='日期推算')
    partner_from = fields.Selection([
        ('default', '默认供应商'),
        ('price_plan', '定价策略'),
        ('min_plan', '最低定价策略'),
        ('now_order', '最新订价'),
        ('now_input', '最新进价'),
    ], default='default', string='厂商取值来源')

    #合并设置
    merge_cycle = fields.Integer('合并周期(天)')
    merge_dep = fields.Boolean('按部门')
    merge_partner = fields.Boolean('按客户')
    merge_order = fields.Boolean('按订单')

    #其他设置
    auto_close = fields.Boolean('订单库存足够自动结案')
    allow_modify = fields.Boolean('允许更改下层商品')
    line_ids = fields.One2many('mrp.plan.config.line', 'config_id', help='库存参数')


class MrpPlanConfigLine(models.Model):
    _name = 'mrp.plan.config.line'
    _description = '分析库存参数'    

    config_id = fields.Many2one('mrp.plan.config', '分析参数', readonly=True, help='关联分析参数主表ID')
    param_name = fields.Selection([
        ('qty_stock', '+库存量'),
        ('qty_po', '+采购在途'),
        ('qty_mo', '+生产在制'),
        ('qty_ous', '+委外在途'),
        ('qty_so', '-销售订单量'),
        ('qty_plancons', '-计划领用量'),
        ('qty_consadd', '-补料申请量'),
        ('qty_uncons', '-生产未领量'),
        ('qty_plan', '+计划量'),
        ('qty_qc', '+在检量'),
    ], string='可用库存')
    close_date = fields.Date('截止日期')
    stock_range = fields.Selection([
        ('all', '所有仓库'),
        ('plan', '分析仓库'),
        ('custom', '指定仓库'),
    ], default='all', string='仓库范围')
    stocks = fields.Many2many(comodel_name='warehouse', string='指定仓库')
    remark = fields.Char('备注')


class MrpPlan(models.Model):
    _name = 'mrp.plan'
    _description = 'MRP分析'

    @api.model
    def _default_warehouse(self):
        return self._default_warehouse_impl()

    @api.model
    def _default_warehouse_impl(self):
        if self.env.context.get('warehouse_type'):
            return self.env['warehouse'].get_warehouse_by_type(
                self.env.context.get('warehouse_type'))

    name = fields.Char('单据编号', index=True, states=READONLY_STATES, copy=False, default='/', help="创建时它会自动生成下一个编号")   
    date = fields.Date('单据日期', required=True, states=READONLY_STATES,
                       default=lambda self: fields.Date.context_today(self),
                       index=True, copy=False, help="默认是订单创建日期")
    user_id = fields.Many2one('staff', '经办人', ondelete='restrict', store=True, states=READONLY_STATES,
                              help='单据经办人')
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states=READONLY_STATES, ondelete='cascade')
    order_id = fields.Many2one('sell.order', '销售订单', readonly=True)  
    remark = fields.Text('备注')
    state = fields.Selection([
                   ('draft', '草稿'),
                   ('done', '已确认')], string='状态', readonly=True,
                   default='draft')
    line_ids = fields.One2many('mrp.plan.line', 'plan_id', string='MRP需求')
    line_result_ids = fields.One2many('mrp.plan.result.line', 'plan_id', string='MRP分析')
    mrp_plm_ids = fields.One2many('mrp.plm', 'plan_id', '生产加工单')
    buy_ids = fields.One2many('buy.order', 'plan_id', '采购订单')
    line_result_count = fields.Integer('建议明细行数', compute='_compute_line_result_count')
    mrp_plm_count = fields.Integer(compute='_compute_plm_buy', readonly=True)
    buy_count = fields.Integer(compute='_compute_plm_buy', readonly=True)

    @api.depends('mrp_plm_ids', 'buy_ids')
    def _compute_plm_buy(self):
        for l in self:
            l.mrp_plm_count = len([l1 for l1 in l.mrp_plm_ids])
            l.buy_count = len([l1 for l1 in l.buy_ids])

    @api.depends('line_result_ids')
    def _compute_line_result_count(self):
        for l in self:
            l.line_result_count = 0
            if l.line_result_ids:
                l.line_result_count = len([l1 for l1 in l.line_result_ids])

    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('请不要重复确认！')
            if not self.line_ids:
                raise UserError('请输入商品明细行！')
            for l1 in l.line_result_ids.filtered(lambda _l: _l.get_way == 'po' and not _l.warehouse_id):
                raise UserError('%s %s, 商品%s 没有指定仓库，无法产生采购订单' % (self.name, self._description, l1.goods_id.name))
            l.write({
                'state': 'done',
            })
            l._create_mrp_plm()
            price_waring = l._create_buy_order()
            if price_waring:
                vals = {
                    'model_name': self._name
                }
                return self.env[self._name].with_context(
                    {'active_model':self._name}
                    ).open_dialog('done_call_back', {
                    'message': price_waring,
                    'args': [vals],
                })
    
    def done_call_back(self,vals):
        return True

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })
            plm = self.env['mrp.plm'].search(
                [('plan_id', '=', l.id)])
            plm.unlink()
            buy = self.env['buy.order'].search(
                [('plan_id', '=', l.id)])
            buy.unlink()

    def button_plan(self):
        for l in self.line_ids.filtered(lambda _l: _l.layer == 0):            
            self.compute_mrp_stock(False, l)
    def compute_mrp_stock(self, parent, line):
        self.compute_plan(parent, line)
        if line.down_ids and len([l1 for l1 in line.down_ids]) > 0:
            for l in line.down_ids:
                self.compute_mrp_stock(line, l)
    def compute_plan(self,parent ,line):
        if line.layer == 0:
            line.qty_gross = line.qty_order
        else:
            line.qty_gross = parent.qty_confirm * line.qty_bom / line.radix * (100 + line.rate_waste) / 100
        line.qty_proposal = line.qty_net = line.qty_gross
        line.qty_confirm = line.qty_proposal + line.qty_set
    def button_clear(self):
        self.line_result_ids.unlink()
    def button_proposal(self):
        for l in self:
            lines = []
            for l1 in l.line_ids.filtered(lambda _l: _l.qty_confirm > 0):
                lines.append({
                    'plan_id': l.id,
                    'plan_line_id': l1.id,
                    'order_id': l1.order_id.id,
                    'order_line_id': l1.order_line_id.id,
                    'cust_so': l1.cust_so,
                    'order_partner_id': l1.partner_id.id,
                    'order_goods_id': l1.order_goods_id.id,
                    'qty_order': l1.qty_order,
                    'order_need_date': l1.order_need_date,
                    'goods_id': l1.goods_id.id,
                    'bom_id': l1.bom_id.id,
                    'warehouse_id': l1.warehouse_id.id,
                    'qty': l1.qty_confirm,
                    'need_date': l1.need_date,
                    'proposal_date': l1.proposal_date,
                    'get_way': l1.get_way,
                    'department_id': l1.department_id.id,
                })
            result_ids = l.write({'line_result_ids': [(0,0, l) for l in lines]})
    def _create_mrp_plm(self):
        user = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            for l1 in l.line_result_ids.filtered(lambda _l:_l.get_way == 'self'):
                mrp_plm_id = self.env['mrp.plm'].create({
                    'partner_id': l1.order_partner_id.id,
                    'user_id': user.id,
                    'date': datetime.datetime.now(),
                    'type': 'work',
                    'warehouse_id': l1.warehouse_id.id,
                    'department_id': l1.department_id.id,
                    'goods_id': l1.goods_id.id,
                    'uom_id': l1.goods_id.uom_id.id,
                    'bom_id': l1.bom_id.id,
                    'order_id': l1.order_id.id,
                    'order_line_id': l1.order_line_id.id,
                    'plan_id': l.id,
                    'plan_result_id': l1.id
                })
                line_ids = []
                if l1.plan_line_id.down_ids:
                    for l2 in sorted(l1.plan_line_id.down_ids, key=lambda _l: _l.bom_sequence, reverse = True):
                        line_ids.append({
                            'plm_id': mrp_plm_id.id,
                            'goods_id': l2.goods_id.id,
                            'uom_id': l2.goods_id.uom_id.id,
                            'warehouse_id': l2.warehouse_id.id,
                            'radix': l2.radix,
                            'rate_waste': l2.rate_waste,
                            'qty_bom': l2.qty_bom,
                            'mrp_proc_id': l2.mrp_proc_id.id,
                        })
                    mrp_plm_id.write({'line_ids':[(0, 0, line) for line in line_ids]})
                line_proc_ids = []
                if l1.plan_line_id.bom_id.line_proc_ids:
                    for l2 in sorted(l1.plan_line_id.bom_id.line_proc_ids, key=lambda _l: _l.sequence, reverse = True):
                        rate_self = l2.rate_self
                        if l2.get_way == 'self' and (not rate_self or rate_self <= 0):
                            rate_self = 100
                        if l2.get_way == 'ous' and rate_self >= 100:
                            rate_self = 0
                        line_proc_ids.append({
                            'sequence': l2.sequence,
                            'plm_id': mrp_plm_id.id,
                            'mrp_proc_id': l2.mrp_proc_id.id,
                            'qty_proc': l2.qty,
                            'need_qc': l2.need_qc,
                            'workcenter_id': l2.workcenter_id.id,
                            'qc_department_id': l2.qc_department_id.id,
                            'get_way': l2.get_way,
                            'rate_self': rate_self,
                            'rate_waste': l2.rate_waste,
                            'sub_remark': l2.sub_remark,
                            'time_uom': l2.time_uom,
                            'pre_time': l2.pre_time,
                            'work_time': l2.work_time,
                            'price_std': l2.price_std,
                            'price': l2.price,
                        })
                    mrp_plm_id.write({'line_proc_ids':[(0, 0, line) for line in line_proc_ids]})
                mrp_plm_id.qty = l1.qty
                mrp_plm_id.onchaing_qty()
                
    def _create_buy_order(self):
        for l in self:
            buy_line_ids = l.line_result_ids.filtered(lambda _l:_l.get_way == 'po')
            date = datetime.datetime.now().date()
            price_waring = ''
            if buy_line_ids and len([_l for _l in buy_line_ids]) > 0:
                pw_line_ids = {}#按供应商+仓库分单
                for line in buy_line_ids:
                    pid = False
                    wid = False
                    partner_id = line.buy_partner_id
                    if partner_id:
                        pid = partner_id.id
                    if line.warehouse_id:
                        wid = line.warehouse_id.id

                    price = line.goods_id.cost
                    for _l in line.goods_id.vendor_ids:
                        if _l.date and _l.date > date:
                            continue
                        if _l.vendor_id == partner_id \
                                and line.qty >= _l.min_qty:
                            price = _l.price
                            break
                    tax_rate = line.goods_id.get_tax_rate(line.goods_id, partner_id, 'buy')
                    price_taxed = 0
                    discount_rate = 0
                    discount_amount = 0
                                       
                    buy_line = {
                        'goods_id': line.goods_id.id,
                        'uom_id': line.goods_id.uom_id.id,
                        'quantity': line.qty,
                        'price': price,
                        'tax_rate': tax_rate,
                        'price_taxed': price_taxed,
                        'discount_rate': discount_rate,
                        'discount_amount': discount_amount,
                        'plan_result_id': line.id,
                    }
                    key = (pid, wid)
                    if not key in pw_line_ids.keys():
                        pw_line_ids.setdefault(key,[])
                    pw_line_ids[key].append(buy_line)
                for key1 in pw_line_ids:
                    buy_id = self.env['buy.order'].create({
                        'partner_id': key1[0] if key1[0] > 0 else False,
                        'date': date,
                        'type': 'buy',
                        'warehouse_dest_id': key1[1] if key1[1] > 0 else False,
                        'plan_id': l.id
                    })
                    for l2 in pw_line_ids[key1]:
                        l2.setdefault('order_id', buy_id.id)
                    buy_id.write({'line_ids': [(0, 0, _l) for _l in pw_line_ids[key1]]})
                    buy_id.line_ids._compute_all_amount()
                    buy_id._compute_qty()
                    buy_id._compute_amount()
            if price_waring != '':
                return ('MRP分析%s %s' % (price_waring, l.name))
        return False
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
    def action_view_buy_order_task(self):
        self.ensure_one()
        action = {
            'name': '采购订单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'buy.order',
            'view_id': False,
            'target': 'current',
        }

        buy_ids = [buy.id for buy in self.buy_ids]
        # choose the view_mode accordingly
        if len(buy_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, buy_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(buy_ids) == 1:
            view_id = self.env.ref('buy.buy_order_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = buy_ids and buy_ids[0] or False
        return action

class MrpPlanLine(models.Model):
    _name = 'mrp.plan.line'
    _description = '需求明细'
    _order = 'plan_id, layer_code'

    plan_id = fields.Many2one('mrp.plan', '生产分析', readonly=True)
    mrp_begin = fields.Boolean('MRP分析开始行', readonly=True)
    layer = fields.Integer('阶层', readonly=True)
    layer_code = fields.Char('阶码', readonly=True)
    up_id = fields.Many2one('mrp.plan.line', 'up_id', readonly=True)
    down_ids = fields.One2many('mrp.plan.line', 'up_id', '转下明细', readonly=True)
    order_id = fields.Many2one('sell.order', '销售订单', readonly=True)
    order_line_id = fields.Many2one('sell.order.line', '销售订单行', readonly=True)
    cust_so = fields.Char('客户订单', readonly=True)
    partner_id = fields.Many2one('partner', '客户', ondelete='restrict', readonly=True, help='客户')
    order_goods_id = fields.Many2one('goods', '订单商品', ondelete='restrict', readonly=True, help='商品')
    qty_order = fields.Float('订货数量', readonly=True)
    order_need_date = fields.Date('订单交期', readonly=True)
    parent_goods_id = fields.Many2one('goods', '成品', ondelete='restrict', readonly=True, help='商品')
    parent_bom_id = fields.Many2one('mrp.bom', '成品BOM', readonly=True)
    department_id = fields.Many2one('staff.department', '生产部门', index=True, ondelete='cascade')
    
    goods_id = fields.Many2one('goods', '子件商品', required=True, readonly=True, ondelete='restrict', help='商品')
    bom_id = fields.Many2one('mrp.bom', '子件BOM', readonly=True)
    bom_line_id = fields.Many2one('mrp.bom.line', 'BOM子件ID', readonly=True)
    warehouse_id = fields.Many2one('warehouse', '默认仓库', ondelete='restrict')
    radix = fields.Float('基数', default=1, digits='Quantity', readonly=True)
    rate_waste = fields.Float('损耗率(%)', digits='Quantity', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '领料工序', readonly=True)
    get_way = fields.Selection([
        ('self', '自制'),
        ('ous', '委外'),
        ('po', '采购'),
    ], default='self', string='获取方式')
    qty_bom = fields.Float('单位用量', default=1, digits='Quantity', readonly=True)
    bom_sequence = fields.Integer('BOM子件顺序号', readonly=True)

    qty_canuse = fields.Float('可用库存', digits='Quantity', readonly=True)
    qty_use = fields.Float('库存占用', digits='Quantity', readonly=True)
    qty_net = fields.Float('净需求', digits='Quantity', readonly=True)
    qty_gross = fields.Float('毛需求', digits='Quantity', readonly=True)
    qty_proposal = fields.Float('建议量', digits='Quantity', readonly=True)
    qty_set = fields.Float('调整量', digits='Quantity')
    qty_confirm = fields.Float('确认量', digits='Quantity')
    qty_plan_to = fields.Float('已建议量', digits='Quantity', readonly=True)
    qty_bom = fields.Float('生产用量', digits='Quantity', readonly=True)
    look_plan = fields.Boolean('锁定建议', digits='Quantity')
    need_date = fields.Date('需求日期', digits='Quantity', readonly=True)
    proposal_date = fields.Date('建议日期', digits='Quantity')
    
    qty_stock = fields.Float('库存量', digits='Quantity', readonly=True)
    qty_plan = fields.Float('计划量', digits='Quantity', readonly=True)
    qty_po = fields.Float('采购在途', digits='Quantity', readonly=True)
    qty_ous = fields.Float('委外在途', digits='Quantity', readonly=True)
    qty_mo = fields.Float('生产在制', digits='Quantity', readonly=True)
    qty_so = fields.Float('销售订单量', digits='Quantity', readonly=True)
    qty_uncons = fields.Float('生产未领量', digits='Quantity', readonly=True)
    qty_plancons = fields.Float('计划领用量', digits='Quantity', readonly=True)
    qty_consadd = fields.Float('补料申请量', digits='Quantity', readonly=True)
    qty_qc = fields.Float('在检量', digits='Quantity', readonly=True)

    @api.onchange('qty_set')
    def qty_set_onchainge(self):
        for l in self:
            l.qty_confirm = l.qty_set + l.qty_net
    @api.onchange('qty_confirm')
    def qty_confirm_onchainge(self):
        for l in self:
            l.qty_set = l.qty_confirm - l.qty_net

class MrpPlanResultLine(models.Model):
    _name = 'mrp.plan.result.line'
    _description = 'MRP建议明细'
    
    plan_id = fields.Many2one('mrp.plan', '生产分析', readonly=True)
    plan_line_id = fields.Many2one('mrp.plan.line', 'MRP需求明细id', readonly=True)
    order_id = fields.Many2one('sell.order', '销售订单', readonly=True)
    order_line_id = fields.Many2one('sell.order.line', '销售订单行', readonly=True)
    cust_so = fields.Char('客户订单', readonly=True)
    order_partner_id = fields.Many2one('partner', '客户', ondelete='restrict', readonly=True, help='客户')
    order_goods_id = fields.Many2one('goods', '订单商品', readonly=True, ondelete='restrict', help='商品')
    qty_order = fields.Float('订货数量', readonly=True)
    order_need_date = fields.Date('订单交期', readonly=True)
    
    goods_id = fields.Many2one('goods', '子件商品', required=True, ondelete='restrict', readonly=True, help='商品')
    bom_id = fields.Many2one('mrp.bom', '子件BOM', readonly=True)
    warehouse_id = fields.Many2one('warehouse', '默认仓库', ondelete='restrict')
    qty = fields.Float('建议量')
    need_date = fields.Date('需求日期', readonly=True)
    proposal_date = fields.Date('建议日期')
    get_way = fields.Selection([
        ('self', '自制'),
        ('po', '采购'),
        ('ous', '委外'),
    ], default='self', string='转单类型')

    department_id = fields.Many2one('staff.department', '生产部门', index=True, ondelete='cascade')
    buy_partner_id = fields.Many2one('partner', '供应商', ondelete='restrict', help='供应商')
    price = fields.Float('单价')
    amount = fields.Float('金额')


class MrpSellOrderExtened(models.Model):
    _inherit = 'sell.order'

    mrp_plan_ids = fields.One2many('mrp.plan', 'order_id', 'MRP分析', readonly=True)
    mrp_plan_count = fields.Integer('MRP分析单数', compute='_compute_mrp_plan')

    def _compute_mrp_plan(self):
        for l in self:
            l.mrp_plan_count = len([l1 for l1 in l.mrp_plan_ids])

    def sell_order_done(self):
        super().sell_order_done()
        """
        产生MRP分析
        """
        user = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            mrp_id = self.env['mrp.plan'].create({
                'user_id': user.id,
                'order_id': l.id,
                'date': datetime.datetime.now()
            })
            self._expand_mrp_plan_line(l, mrp_id)
    
    def _expand_mrp_plan_line(self,order_id, mrp_id):
        lines = []
        for l in order_id.line_ids.filtered(lambda _l: _l.bom_id):
            lines.append({
                'mrp_begin': True,
                'layer': 0,
                'layer_code': str(order_id.id).zfill(5),
                'plan_id': mrp_id.id,
                'order_id': order_id.id,
                'order_line_id': l.id,
                'partner_id': order_id.partner_id.id,
                'order_goods_id': l.goods_id.id,
                'qty_order': l.quantity,
                'order_need_date': order_id.delivery_date,
                'parent_goods_id': l.goods_id.id,
                'parent_bom_id': l.bom_id.id,
                'department_id': l.bom_id.department_id.id,
                'goods_id': l.goods_id.id,
                'bom_id': l.bom_id.id,
                'get_way': 'self',
                'warehouse_id': l.bom_id.warehouse_id.id,
                'radix': 1,
                'qty_bom': 1,
            })
            
        mrp_id.write({'line_ids': [(0,0, l) for l in lines]})
        lines = mrp_id.line_ids.filtered(lambda _l: _l.layer == 0)
        self._expand_mrp_plan_down_line(order_id, lines,mrp_id, 0)        
    
    def _expand_mrp_plan_down_line(self,order_id , parents, mrp_id, layer):
        lines = []
        layer += 1
        for l in parents:
            for l1 in sorted(l.bom_id.line_ids,key=lambda _l:_l.sequence, reverse = True):
                lines.append({
                    'mrp_begin': False,
                    'up_id': l.id,
                    'layer': layer,
                    'layer_code': (l.layer_code + '.' + str(l1.id).zfill(5)),
                    'bom_line_id': l1.id,
                    'bom_sequence': l1.sequence,
                    'plan_id': mrp_id.id,
                    'order_id': order_id.id,
                    'order_line_id': l.order_line_id.id,
                    'partner_id': order_id.partner_id.id,
                    'order_goods_id': l.order_goods_id.id,
                    'qty_order': l.qty_order,
                    'order_need_date': l.order_need_date,
                    'parent_goods_id': l.goods_id.id,
                    'parent_bom_id': l.bom_id.id,
                    'department_id': l.bom_id.department_id.id,
                    'goods_id': l1.goods_id.id,
                    'bom_id': l1.bom_id.id,
                    'get_way': l1.goods_id.get_way,
                    'warehouse_id': l1.warehouse_id.id,
                    'mrp_proc_id': l.mrp_proc_id.id,
                    'radix': l1.radix,
                    'qty_bom': l1.qty,
                    'rate_waste': l.rate_waste,
                })
        
        mrp_id.write({'line_ids': [(0,0, l) for l in lines]})
        lines = mrp_id.line_ids.filtered(lambda _l: _l.layer == layer and _l.bom_id)
        if len([l1 for l1 in lines]) > 0:
            self._expand_mrp_plan_down_line(order_id,lines, mrp_id, layer)

    def sell_order_draft(self):
        super().sell_order_draft()
        mrp_ids = self.env['mrp.plan'].search(
            [('order_id', '=', self.id)])
        mrp_ids.unlink()

    def action_view_mrp_plan(self):
        self.ensure_one()
        action = {
            'name': 'MRP分析',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plan',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        mrp_ids = [mrp.id for mrp in self.mrp_plan_ids]
        # choose the view_mode accordingly
        if len(mrp_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, mrp_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(mrp_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plan_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = mrp_ids and mrp_ids[0] or False
        return action

class MrpSellOrderLineExtened(models.Model):
    _inherit = 'sell.order.line'

    goods_id = fields.Many2one('goods',
                               '商品',
                               required=True,
                               ondelete='restrict',
                               help='商品')
    bom_id = fields.Many2one('mrp.bom', 'BOM', ondelete='restrict', help='BOM')

    @api.onchange('goods_id', 'bom_id')
    def goods_id_bom_id_onchange(self):
        for l in self:
            if l.goods_id and not l.bom_id:
                bom = self.env['mrp.bom'].search([('goods_id', '=', l.goods_id.id)])
                if bom and len(bom) > 0:
                    l.bom_id = bom[0].id
            elif not l.goods_id and l.bom_id:
                l.goods_id = l.bom_id.goods_id
                l.onchange_goods_id()


class BuyOrderExtened(models.Model):
    _inherit = 'buy.order'
    plan_id = fields.Many2one('mrp.plan', 'MRP分析', readonly=True)

class BuyOrderLineExtened(models.Model):
    _inherit = 'buy.order.line'
    plan_result_id = fields.Many2one('mrp.plan.result.line', 'MRP建议', readonly=True)