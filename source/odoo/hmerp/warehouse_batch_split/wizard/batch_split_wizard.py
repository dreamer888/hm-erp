from odoo import models, fields, api
from odoo.exceptions import UserError


class BatchSplitWizard(models.TransientModel):
    _name = 'batch.split.wizard'
    _description = '批次拆分向导'

    move_line_id = fields.Many2one(
        'wh.move.line',
        string="移库行",
        required=True,
        default=lambda self: self.env.context.get('active_ids')[0])
    goods_id = fields.Many2one(
        'goods',
        string='商品',
        related='move_line_id.goods_id')
    warehouse_id = fields.Many2one(
        'warehouse',
        string='仓库',
        related='move_line_id.warehouse_id')
    goods_qty = fields.Float(
        '计划拆分数量',
        related='move_line_id.goods_qty')
    line_ids = fields.One2many(
        'batch.split.line',
        'wizard_id',
        string='批次行')

    def split_move_line(self):
        self.ensure_one()
        if self.move_line_id.state == 'done':
            raise UserError("不能拆分已完成的单据")
        if not self.move_line_id.goods_id.using_batch:
            raise UserError("商品并不管理批次")
        # 总数量不能大于计划拆分数量
        if sum(l.qty for l in self.line_ids) > self.goods_qty:
            raise UserError("批次总数量不能超出计划拆分数量")
        # 循环批次行
        first = True
        for l in self.line_ids:
            if not l.qty:
                raise UserError("批次数量不能为0")
            if not l.lot and not l.lot_id:
                raise UserError("请输入批次")
            if l.lot_id:
                # 如果不是入库，每行数量不可以大于批次剩余数量
                if l.qty > l.lot_id.qty_remaining:
                    raise UserError("不能超出批次可用数量")
            vals = {
                'lot': l.lot,
                'expiration_date': l.expiration_date,
                'lot_id': l.lot_id.id,
                'goods_qty': l.qty
            }
            res = False
            if first:
                #第一行直接写入move_line
                self.move_line_id.write(vals)
                res = self.move_line_id
                first = False
            else:
                #其他行复制第一行并写入批次和数量
                res = self.move_line_id.copy(vals)
            if l.lot_id:
                res.onchange_lot_id()


class BatchSplitLine(models.TransientModel):
    _name = 'batch.split.line'
    _description = '批次拆分向导行'

    wizard_id = fields.Many2one('batch.split.wizard', string="向导")
    lot = fields.Char('入库批次')
    expiration_date = fields.Date('报废日期')
    lot_id = fields.Many2one('wh.move.line', string="出库批次")
    qty = fields.Float('数量')

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        if self.lot_id:
            self.qty = self.lot_id.qty_remaining
