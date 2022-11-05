from odoo import fields, api, models
from odoo.exceptions import UserError


class MrpPlmConsRetu(models.Model):
    _name = 'mrp.plm.cons.retu'
    _description = '生产退料'    
    _inherits = {'wh.move': 'mrp_plm_cons_retu_id'}

    mrp_plm_cons_retu_id = fields.Many2one('wh.move', '生产退料', readonly=True, required=True, ondelete='cascade')
    name = fields.Char('单据编号', index=True, states={'done': [('readonly', True)]}, copy=False, default='/', help="创建时它会自动生成下一个编号")
   
    plm_id = fields.Many2one('mrp.plm', '订单号', readonly=True, ondelete='cascade', help='')
    def button_done(self):
        '''审核领料单'''
        self.ensure_one()
        # 报错
        if self.state == 'done':
            raise UserError('请不要重复入库')
        # 调用wh.move中审核方法，更新审核人和审核状态
        self.mrp_plm_cons_retu_id.approve_order()

        self.approve_uid = self._uid
        self.write({
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })

        # 生成分拆单 FIXME:无法跳转到新生成的分单
        if self.plm_id:# and not self.modifying:
            self.plm_id._create_plm_cons()

    def button_draft(self):
        '''反审核领料单'''
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销 %s' % self._description)
        # 如果存在分单，则将差错修改中置为 True，再次审核时不生成分单
        self.write({
            'state': 'draft',
        })
        self.plm_id.line_ids._compute_qty_to()
        for l in self.line_in_ids:
            if l.plm_line_id.qty < l.plm_line_id.qty_cons - l.plm_line_id.qty_retu:
                raise UserError('%s %s,撤回导致生产超领' % (self._description, self.name))
        # 调用wh.move中反审核方法，更新审核人和审核状态
        self.mrp_plm_cons_retu_id.cancel_approved_order()
    
    def unlink(self):
        for l in self:
            l.mrp_plm_cons_retu_id.unlink()
    


class WhMoveLine(models.Model):
    _inherit = 'wh.move.line'
    _description = "生产退料明细"

    qty_retu_pending = fields.Float('待退料数量', digits='Quantity', compute='_compute_qty_retu_pending', readonly=True, store=False)

    @api.depends('plm_line_id')
    def _compute_qty_retu_pending(self):
        for l in self:
            l.qty_retu_pending = l.plm_line_id.qty_cons - l.plm_line_id.qty_retu