from odoo import fields, api, models
from odoo.exceptions import UserError


class MrpPlmCons(models.Model):
    _name = "mrp.plm.cons"
    _inherits = {'wh.move': 'mrp_plm_cons_id'}
    _description = "生产领料"
    
    mrp_plm_cons_id = fields.Many2one('wh.move', '生产领料', readonly=True, required=True, ondelete='cascade')
    name = fields.Char('单据编号', index=True, states={'done': [('readonly', True)]}, copy=False, default='/', help="创建时它会自动生成下一个编号")
   
    plm_id = fields.Many2one('mrp.plm', '订单号', copy=False, readonly=True, ondelete='cascade', help='')
    plm_cons_add_id = fields.Many2one('mrp.plm.cons.add', '生产补料', readonly=True)
    modifying = fields.Boolean('差错修改中', default=False, copy=False,
                               help='是否处于差错修改中')

    def button_done(self):
        '''审核领料单'''
        self.ensure_one()
        # 报错
        if self.state == 'done':
            raise UserError('请不要重复入库')
        # 库存不足 生成零的
        if self.env.user.company_id.is_enable_negative_stock:
            result_vals = self.env['wh.move'].create_zero_wh_in(
                self, self._name)
            if result_vals:
                return result_vals
        # 调用wh.move中审核方法，更新审核人和审核状态
        self.mrp_plm_cons_id.approve_order()

        # 将入库货数量写入生产加工单
        #self._line_qty_write()
        #self.plm_id._write_cons()
        self.approve_uid = self._uid
        self.write({
            'state': 'done',  # 为保证审批流程顺畅，否则，未审批就可审核
        })
        if self.plm_cons_add_id:
            self.plm_cons_add_id._compute_plm_cons()
            for l in self.line_out_ids:
                if l.plm_cons_add_line_id.qty < l.plm_cons_add_line_id.qty_cons:
                    raise UserError('%s %s,领料大于补料数量' % (self._description, self.name))
        else:
            self.plm_id.line_ids._compute_qty_to()
            for l in self.line_out_ids:
                if l.plm_line_id.qty < l.plm_line_id.qty_cons - l.plm_line_id.qty_retu:
                    raise UserError('%s %s,大于可领料数量' % (self._description, self.name))
        if self.plm_cons_add_id:
            self.plm_cons_add_id._create_plm_cons()
        elif self.plm_id:# and not self.modifying:
            return self.plm_id._create_plm_cons()

    def button_draft(self):
        '''反审核领料单'''
        self.ensure_one()
        self.write({
            'state': 'draft',
        })
        # 调用wh.move中反审核方法，更新审核人和审核状态
        self.mrp_plm_cons_id.cancel_approved_order()

    def unlink(self):
        for plm_in in self:
            plm_in.mrp_plm_cons_id.unlink()

    def _line_qty_write(self):
        self.ensure_one()
        if self.line_out_ids:
            for line in self.line_out_ids:
                line.plm_line_id.qty_cons += line.goods_qty
    
    def goods_inventory(self, vals):
        """
        审核时若仓库中商品不足，则产生补货向导生成其他入库单并审核。
        :param vals: 创建其他入库单需要的字段及取值信息构成的字典
        :return:
        """
        auto_in = self.env['wh.in'].create(vals)
        line_ids = [line.id for line in auto_in.line_in_ids]
        self.with_context({'wh_in_line_ids': line_ids}).button_done()
        return True


class WhMoveLine(models.Model):
    _inherit = 'wh.move.line'
    _description = "生产领料明细"
    plm_id = fields.Many2one('mrp.plm', '生产加工单', readonly=True, ondeelete='cascade', help='对应生产加工单的ID')
    plm_line_id = fields.Many2one('mrp.plm.line', '生产加工物料行', readonly=True, ondelete='cascade', help='对应生产加工物料行ID')
    plm_cons_add_line_id = fields.Many2one('mrp.plm.cons.add.line', '生产补料行', readonly=True, ondelete='cascade', help='对应生产补料行ID')
    qty_retu = fields.Float('退料数量', digits='Quantity', store=False, readonly=True)    
    qty_cons_pending = fields.Float('待领数量', digits='Quantity', compute='_compute_qty_cons_pending', readonly=True, store=False)

    @api.depends('plm_line_id', 'plm_cons_add_line_id')
    def _compute_qty_cons_pending(self):
        for l in self:
            if l.plm_cons_add_line_id:
                l.qty_cons_pending = l.plm_cons_add_line_id.qty - l.plm_cons_add_line_id.qty_cons
            else:
                l.qty_cons_pending = l.plm_line_id.qty + l.plm_line_id.qty_waste - l.plm_line_id.qty_cons + l.plm_line_id.qty_retu

