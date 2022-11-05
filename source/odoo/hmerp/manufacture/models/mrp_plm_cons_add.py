from odoo import fields, api, models
from odoo.exceptions import UserError


# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
}


class MrpPlmConsAdd(models.Model):
    _name = 'mrp.plm.cons.add'
    _description = '生产补料'

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
    plm_id = fields.Many2one('mrp.plm', '订单号', readonly=True, copy=False, ondelete='cascade', help='')
    plm_cons_ids = fields.One2many('mrp.plm.cons', 'plm_cons_add_id', string='生产领料', readonly=True, copy=False)
    plm_cons_count = fields.Integer(compute='_compute_plm_cons', store=False, string='领料单数量', readonly=True, default=0)
    remark = fields.Char('备注', Default='', states=READONLY_STATES)
    state = fields.Selection([
                   ('draft', '草稿'),
                   ('done', '已确认')], string='状态', readonly=True,
                   default='draft')
    line_ids= fields.One2many('mrp.plm.cons.add.line', 'plm_cons_add_id', '补料明细', states=READONLY_STATES)

    @api.depends('plm_cons_ids')
    def _compute_plm_cons(self):
        for plm in self:
            plm.plm_cons_count = len([plm_cons for plm_cons in plm.plm_cons_ids])
            for l in plm.line_ids:
                l.qty_cons = sum(sum(l2.goods_qty for l2 in\
                             l1.line_out_ids.filtered(lambda _l:_l.plm_cons_add_line_id.id == l.id)) for l1 in\
                             plm.plm_cons_ids.filtered(lambda l2: l2.state == 'done'))
                l.qty_cons_to = sum(sum(l2.goods_qty for l2 in \
                                l1.line_out_ids.filtered(lambda _l:_l.plm_cons_add_line_id.id == l.id)) for l1 in plm.plm_cons_ids)

    def button_done(self):
        '''审核领料单'''
        self.ensure_one()
        # 报错
        if self.state == 'done':
            raise UserError('请不要重复入库')
        self.write({
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })
        self._create_plm_cons()

    def button_draft(self):
        self.ensure_one()
        self.write({
            'state': 'draft',
        })
        plm_cons = self.env['mrp.plm.cons'].search(
            [('plm_cons_add_id', '=', self.id)])
        plm_cons.unlink()

    def _create_plm_cons(self):
        '''由生产加工单生成领料单'''
        self.ensure_one()
        gp_lines = {}
        for line in self.line_ids:
            # 如果订单部分入库，则点击此按钮时生成剩余数量的入库单
            to_in = line.qty - line.qty_to
            if to_in <= 0:
                continue
            l = self.get_plm_cons_line(line, single=False);
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
                'user_id':usr.id,
                'department_id':usr.department_id.id,
                'plm_id': self.plm_id.id,
                'plm_cons_add_id': self.id,
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
            'plm_line_id': line.plm_line_id.id,
            'plm_cons_add_line_id': line.id,
            'goods_id': line.goods_id.id,
            #'attribute_id': line.attribute_id.id,
            'uos_id': line.goods_id.uos_id.id,
            'goods_qty': line.qty - line.qty_to,
            'uom_id': line.uom_id.id
        }
    
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

class MrpPlmConsAddLine(models.Model):
    _name = 'mrp.plm.cons.add.line'
    _description = '补料明细'
    plm_cons_add_id = fields.Many2one('mrp.plm.cons.add', '生产补料', readonly=True)
    plm_id = fields.Many2one('mrp.plm', '加工单号', index=True, default=None, readonly=True, ondelete='cascade',
                             help='关联生产加工单ID')
    plm_line_id = fields.Many2one('mrp.plm.line', '生产加工物料行', ondelete='cascade', help='对应生产加工物料行ID')
    goods_id = fields.Many2one('goods', '商品', required=True, ondelete='restrict', help='商品')
    uom_id = fields.Many2one('uom', '单位', required=True, ondelete='restrict',
                             help='商品计量单位')
    warehouse_id = fields.Many2one('warehouse', '默认发料库', required=True, ondelete='restrict',
                                   help='生产领料默认从该仓库调出')
    qty = fields.Float('数量', default=1, required=True, digits='Quantity', help='下单数量')
    qty_cons = fields.Float('已领数量', store=False, readonly=True, copy=False, digits='Quantity', help='生产加工单待耗用材料已领数量')
    qty_to = fields.Float('已转领料量', store=False, readonly=True, copy=False, digits='Quantity', 
                          default=0, help='生产加工单待耗用材料已转领数量')
    remark = fields.Char('备注', Default='')
