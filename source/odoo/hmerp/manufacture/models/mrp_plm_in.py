from odoo import fields, api, models
from odoo.exceptions import UserError


# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}
class WhMoveExtened(models.Model):
    _inherit = 'wh.move'
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states={'done': [('readonly', True)]}, ondelete='cascade')

class MrpPlmIn(models.Model):
    _name = "mrp.plm.in"
    _inherits = {'wh.move': 'mrp_plm_in_id'}
    _description = "生产完工入库"

    mrp_plm_in_id = fields.Many2one('wh.move', '入库单', required=True, readonly=True, ondelete='cascade', help='入库单号')
    name = fields.Char('单据编号', index=True, states=READONLY_STATES, copy=False, default='/', help="创建时它会自动生成下一个编号")
   
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, copy=False, ondelete='cascade', help='')
    modifying = fields.Boolean('差错修改中', default=False, copy=False,
                               help='是否处于差错修改中')
    def button_done(self):
        '''审核生产入库单'''
        self.ensure_one()
        # 报错
        if self.state == 'done':
            raise UserError('请不要重复入库 %s %s' % (self._description, self.name))
        # 调用wh.move中审核方法，更新审核人和审核状态
        self.mrp_plm_in_id.approve_order()

        # 将入库货数量写入生产加工单
        #self._line_qty_write()
        self.approve_uid = self._uid
        self.write({
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })
        for l in self.line_in_ids:
            if l.plm_id:
                l.plm_id._compute_plm_in()
                if l.plm_id.qty - l.plm_id.qty_in < 0:  
                    raise UserError('%s %s,入库数量大于生产数量' % (self._description, self.name))
        # 生成分拆单 FIXME:无法跳转到新生成的分单
        self.plm_id._create_plm_in()

    def button_draft(self):
        '''反审核生产入库单'''
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销 %s %s' % (self._description, self.name))
        # 如果存在分单，则将差错修改中置为 True，再次审核时不生成分单
        self.write({
            'modifying': False,
            'state': 'draft',
        })
        # 调用wh.move中反审核方法，更新审核人和审核状态
        self.mrp_plm_in_id.cancel_approved_order()
    
    def unlink(self):
        for plm_in in self:
            plm_in.mrp_plm_in_id.unlink()

    def _line_qty_write(self):
        self.ensure_one()
        if self.plm_id:
            for line in self.line_in_ids:
                line.plm_id.qty_in += line.goods_qty
        return
        
        
class WhMoveLine(models.Model):
    _inherit = 'wh.move.line'
    _description = "生产入库明细"
    plm_id = fields.Many2one('mrp.plm', '生产加工单', ondelete='cascade', help='对应的生产加工的制成品')
    qty_in_pending = fields.Float('待入库数量', digits='Quantity', compute='_compute_qty_in_pending', readonly=True, store=False)

    @api.depends('plm_id')
    def _compute_qty_in_pending(self):
        for l in self:
            l.qty_in_pending = l.plm_id.qty - l.plm_id.qty_in
    