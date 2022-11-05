from odoo import fields, models, api, tools


class MrpInDetialReport(models.Model):
    _name = 'mrp.in.detial.report'
    _description = '生产入库明细'
    _auto = False

    name = fields.Char('单据号码')
    date = fields.Date('单据日期')
    user_id = fields.Many2one('res.users', '经办人')
    order_id = fields.Many2one('sell.order', '销售订单')
    plm_id = fields.Many2one('mrp.plm', '生产加工单')
    plm_qty = fields.Float('加工数量', digits='Quantity')
    warehouse_dest_id = fields.Many2one('warehouse', '仓库')
    goods_id = fields.Many2one('goods', '商品')
    category_id = fields.Many2one('core.category', '商品类别')
    uom = fields.Char('单位', compute='_compute_uom')
    goods_qty = fields.Float('入库数量', digits='Quantity')
    state = fields.Selection([
                ('draft', '草稿'),
                ('done', '已确认'),
                ], string='状态')
    def _compute_uom(self):
        for l in self:
            l.uom = (l.goods_id.uom_id.name if l.goods_id else '')
    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, 'mrp_in_detial_report')
        cr.execute("""
            CREATE or REPLACE VIEW mrp_in_detial_report AS (
                SELECT H.id,H.name,wh.date,wh.user_id,plm.order_id,H.plm_id,
                       wml.goods_id,gd.category_id,plm.qty plm_qty,wh.warehouse_dest_id,wml.goods_qty,wh.state
                FROM wh_move_line AS wml
                LEFT OUTER JOIN goods gd ON gd.id = wml.goods_id
                LEFT OUTER JOIN wh_move AS wh ON wml.move_id = wh.id
                LEFT JOIN mrp_plm_in H ON H.mrp_plm_in_id = wh.id
                LEFT OUTER JOIN mrp_plm AS plm ON H.plm_id = plm.id
                WHERE H.id is not null
            )
            """)
    
    def view_bil_from(self):
        '''查看单据内容'''
        self.ensure_one()        
        result = self.get_data_from_cache()
        if not result or len(result) == 0:
            return {}
        id = result[0].get('id')
        action = {
            'name': '生产入库',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.in',
            'view_id': False,
            'target': 'current',
        }
        view_id = self.env.ref('manufacture.mrp_plm_in_form').id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = id
        return action