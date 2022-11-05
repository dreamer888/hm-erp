
from odoo import models, fields


class MrpBomCopyDialogWizard(models.TransientModel):
    _name = 'mrp.bom.copy.dialog.wizard'
    _description = u'BOM复制提示的向导'

    bom_id_from = fields.Many2one('mrp.bom', '来源BOM', readonly=True,
                    default=lambda self: self._get_bom_id())
    goods_id_from = fields.Many2one('goods', '来源成品', readonly=True,
                    default=lambda self: self._get_goods_id())
    bom_ver = fields.Char('版本')
    goods_id = fields.Many2one('goods', '目标成品')
        
    def _get_bom_id(self):
        if 'bom_id' in self.env.context:
            return self.env.context.get('bom_id')
        return False

    def _get_goods_id(self):
        if 'goods_id' in self.env.context:
            return self.env.context.get('goods_id')
        return False

    def do_confirm(self):
        if not self.bom_id_from:
            raise ValueError(u'来源BOM不能为空')
        if not self.goods_id:
            raise ValueError(u'目标成品不能为空')

        if self.bom_id_from and self.goods_id:
            id = 0
            """
            复制BOM操作
            """
            goods = self.goods_id
            bom1 = self.env['mrp.bom'].search([('goods_id', '=', self.goods_id.id)])
            if bom1 and len([l for l in bom1]) > 0:
                raise ValueError(u'目标商品已存在BOM')
            bom = self._copy_bom(self.bom_id_from, self.goods_id, self.bom_ver)
            if bom:
                id = bom.id
            action = {
                'name': '生产加工单',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mrp.bom',
                'view_id': False,
                'target': 'main',
            }
            view_id = self.env.ref('manufacture.mrp_bom_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = id
            return action
        else:
            raise ValueError(u'错误, 向导中找不到源单的定义')

    def _copy_bom(self, bom_id_from, goods_id, bom_ver=''):
        bom = bom_id_from.copy()
        bom.bom_ver = bom_ver
        bom.goods_id = goods_id
        bom.uom_id = goods_id.uom_id
        bom.auto_code(bom)
        for l in bom.line_ids.filtered(lambda _l: _l.goods_id.name.startswith(bom_id_from.goods_id.name)):
            """与母件代号前缀匹配"""
            new_name = goods_id.name + l.goods_id.name.replace(bom_id_from.goods_id.name, '')
            goods = self.env['goods'].search([('name', '=', new_name)])
            if goods and len([l1 for l1 in goods]) > 0:
                """
                按代码规则匹配下层商品，需替换为新商品
                """
                new_goods = goods[0]
                l.goods_id = new_goods
                l.uom_id = new_goods.uom_id
                line_bom = self.env['mrp.bom'].search([('goods_id', '=', new_goods.id)])
                if line_bom and len([l1 for l1 in line_bom]) > 0:
                    l.bom_id = line_bom[0]
                elif l.bom_id:
                    """新商品不存在，将Copy原Bom"""
                    l.bom_id = self._copy_bom(l.bom_id,l.goods_id)
        return bom
