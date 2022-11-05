from odoo import _, api, fields, models
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class WarehouseProduceWizard(models.TransientModel):
    _name = 'wh.produce.wizard'
    _description = '报工向导'

    @api.model
    def _get_note(self):
        _logger.info('获取界面提示文本')
        model = self.env.context.get('active_model')
        id = self.env.context.get('active_ids')[0]
        ass = self.env[model].browse(id)
        return '正在对 %s 报工，点击确认按钮拆分' % ass.name

    note = fields.Text(string='描述', default=_get_note)
    date = fields.Date(
        '完工日期',
        required=True,
        default=fields.Date.context_today)
    qty = fields.Float('完工数量', default=1)
    line_in_ids = fields.One2many(
        'wizard.produce.move.line.in',
        'wizard_id',
        string='产出成品行')
    line_out_ids = fields.One2many(
        'wizard.produce.move.line.out',
        'wizard_id',
        string='消耗材料行')

    @api.onchange('qty')
    def onchange_goods_qty(self):
        _logger.info('根据数量和BOM填充报工成品和材料行')
        model = self.env.context.get('active_model')
        id = self.env.context.get('active_ids')[0]
        ass = self.env[model].browse(id)
        line_out_ids, line_in_ids = [], []
        warehouse_id = ass.warehouse_id
        if ass.bom_id and self.qty > 0:
            line_in_ids = [(0, 0, {
                            'goods_id': line.goods_id.id,
                            'attribute_id': line.attribute_id.id,
                            'warehouse_id': self.env['warehouse'].get_warehouse_by_type('production').id,
                            'warehouse_dest_id': warehouse_id.id,
                            'uom_id': line.goods_id.uom_id.id,
                            'goods_qty': self.qty,
                            'type': 'in',
                            }) for line in ass.bom_id.line_parent_ids]
            parent_line_goods_qty = ass.bom_id.line_parent_ids[0].goods_qty
            for line in ass.bom_id.line_child_ids:
                local_goods_qty = line.goods_qty / parent_line_goods_qty * self.qty
                line_out_ids.append((0, 0, {
                    'goods_id': line.goods_id.id,
                    'attribute_id': line.attribute_id.id,
                    'designator': line.designator,
                    'warehouse_id': warehouse_id.id,
                    'warehouse_dest_id': self.env[
                        'warehouse'].get_warehouse_by_type('production'),
                    'uom_id': line.goods_id.uom_id.id,
                    'goods_qty':  local_goods_qty,
                    'type': 'out',
                }))
            self.line_in_ids = False
            self.line_out_ids = False
            if line_in_ids:
                self.line_in_ids = line_in_ids
            if line_out_ids:
                self.line_out_ids = line_out_ids

    def _get_new_ass_head(self, ass):
        model = self.env.context.get('active_model')
        new_name = ''
        exist_splits = self.env[model].search(
            [('name', 'ilike', ass.name)], order="id desc")
        new_name = ass.name + '-' + str(len(exist_splits)).zfill(3)
        return {
            'name': new_name,
            'warehouse_id': ass.warehouse_id.id,
            'warehouse_dest_id': ass.warehouse_dest_id.id,
            'goods_id': ass.goods_id.id,
            'date': self.date,
            'bom_id': ass.bom_id.id,
            'is_many_to_many_combinations': True,
        }

    def button_ok(self):
        # 保存前调用了onchange导致结果不对
        if self.qty <= 0:
            raise UserError('完工数量不能小于0')
        _logger.info('生成新组装单并确认')
        model = self.env.context.get('active_model')
        id = self.env.context.get('active_ids')[0]
        ass = self.env[model].browse(id)
        production_wh = self.env[
                        'warehouse'].get_warehouse_by_type('production')
        # 新组装单从原组装单逐行创建出来
        new_ass = self.env[model].create(self._get_new_ass_head(ass))
        new_ass.goods_qty = self.qty
        new_ass.line_in_ids = [(0, 0, {
            'goods_id': d.goods_id.id,
            'attribute_id': d.attribute_id.id,
            'lot': d.lot,
            'goods_qty': d.goods_qty,
            'uom_id': d.uom_id.id,
            'type': d.type,
            'location_id': d.location_id.id,
            'warehouse_id': production_wh.id,
            'warehouse_dest_id': ass.warehouse_dest_id.id,
            }) for d in self.line_in_ids]
        new_ass.line_out_ids = [(0, 0, {
            'goods_id': d.goods_id.id,
            'attribute_id': d.attribute_id.id,
            'designator': d.designator,
            'lot_id': d.lot_id.id,
            'goods_qty': d.goods_qty,
            'uom_id': d.uom_id.id,
            'type': d.type,
            'location_id': d.location_id.id,
            'warehouse_id': ass.warehouse_id.id,
            'warehouse_dest_id': production_wh.id,
            }) for d in self.line_out_ids]
        new_ass.approve_feeding()
        new_ass.approve_order()

        # 原组装单行数量扣减
        if ass.goods_qty <= self.qty:
            ass.unlink()
        else:
            ass.goods_qty -= self.qty
            ass.onchange_goods_qty()
        return self.env.ref('warehouse.wh_assembly_action').read()[0]


class WizardProduceMoveLineIn(models.TransientModel):
    _name = 'wizard.produce.move.line.in'
    _inherit = 'wh.move.line'
    _description = '移库行'

    wizard_id = fields.Many2one('wh.produce.wizard', '向导')


class WizardProduceMoveLineOut(models.TransientModel):
    _name = 'wizard.produce.move.line.out'
    _inherit = 'wh.move.line'
    _description = '移库行'

    wizard_id = fields.Many2one('wh.produce.wizard', '向导')
