

from odoo import fields, models, api
import datetime


class SellSummaryPartner(models.Model):
    _name = 'sell.summary.partner'
    _inherit = 'report.base'
    _description = '销售汇总表（按客户）'

    id_lists = fields.Text('移动明细行id列表')
    c_category = fields.Char('客户类别')
    partner = fields.Char('客户')
    goods_code = fields.Char('商品编码')
    goods = fields.Char('商品名称')
    attribute = fields.Char('属性')
    warehouse = fields.Char('仓库')
    qty_uos = fields.Float('辅助数量', digits='Quantity')
    uos = fields.Char('辅助单位')
    qty = fields.Float('基本数量', digits='Quantity')
    uom = fields.Char('基本单位')
    price = fields.Float('单价', digits='Price')
    amount = fields.Float('销售收入', digits='Amount')
    tax_amount = fields.Float('税额', digits='Amount')
    subtotal = fields.Float('价税合计', digits='Amount')
    margin = fields.Float('毛利', digits='Amount')

    def select_sql(self, sql_type='out'):
        return '''
        SELECT MIN(wml.id) as id,
               array_agg(wml.id) AS id_lists,
               c_categ.name AS c_category,
               partner.name AS partner,
               goods.code AS goods_code,
               goods.name AS goods,
               attr.name AS attribute,
               wh.name AS warehouse,
               SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_uos_qty
                    ELSE - wml.goods_uos_qty END) AS qty_uos,
                uos.name AS uos,
                SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_qty
                    ELSE - wml.goods_qty END) AS qty,
                uom.name AS uom,
                (CASE WHEN SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_qty
                    ELSE - wml.goods_qty END) = 0 THEN 0
                ELSE
                    SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.amount
                        ELSE - wml.amount END)
                        / SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_qty
                        ELSE - wml.goods_qty END)
                END) AS price,
                SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.amount
                    ELSE - wml.amount END) AS amount,
                SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.tax_amount
                    ELSE - wml.tax_amount END) AS tax_amount,
                SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.subtotal
                    ELSE - wml.subtotal END) AS subtotal,
                (SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.amount
                    ELSE - wml.amount END) - SUM(CASE WHEN wm.origin = 'sell.delivery.sell' THEN wml.goods_qty
                    ELSE - wml.goods_qty END) * wml.cost_unit) AS margin
        '''

    def from_sql(self, sql_type='out'):
        return '''
        FROM wh_move_line AS wml
            LEFT JOIN wh_move wm ON wml.move_id = wm.id
            LEFT JOIN partner ON wm.partner_id = partner.id
            LEFT JOIN core_category AS c_categ
                 ON partner.c_category_id = c_categ.id
            LEFT JOIN goods ON wml.goods_id = goods.id
            LEFT JOIN attribute AS attr ON wml.attribute_id = attr.id
            LEFT JOIN warehouse AS wh ON wml.warehouse_id = wh.id
                 OR wml.warehouse_dest_id = wh.id
            LEFT JOIN uom AS uos ON goods.uos_id = uos.id
            LEFT JOIN uom ON goods.uom_id = uom.id
        '''

    def where_sql(self, sql_type='out'):
        extra = ''
        if self.env.context.get('partner_id'):
            extra += 'AND partner.id = {partner_id}'
        if self.env.context.get('goods_id'):
            extra += 'AND goods.id = {goods_id}'
        if self.env.context.get('c_category_id'):
            extra += 'AND c_categ.id = {c_category_id}'
        if self.env.context.get('warehouse_id'):
            extra += 'AND wh.id = {warehouse_id}'

        return '''
        WHERE wml.state = 'done'
          AND wml.date >= '{date_start}'
          AND wml.date <= '{date_end}'
          AND wm.origin like 'sell.delivery%%'
          AND wh.type = 'stock'
          %s
        ''' % extra

    def group_sql(self, sql_type='out'):
        return '''
        GROUP BY c_category,partner,goods_code,goods,attribute,warehouse,uos,uom,wml.cost_unit
        '''

    def order_sql(self, sql_type='out'):
        return '''
        ORDER BY c_category,partner,goods_code,attribute,warehouse
        '''

    def get_context(self, sql_type='out', context=None):
        return {
            'date_start': context.get('date_start') or '',
            'date_end': context.get('date_end'),
            'partner_id': context.get('partner_id') and
            context.get('partner_id')[0] or '',
            'goods_id': context.get('goods_id') and
            context.get('goods_id')[0] or '',
            'c_category_id': context.get('c_category_id') and
            context.get('c_category_id')[0] or '',
            'warehouse_id': context.get('warehouse_id') and
            context.get('warehouse_id')[0] or '',
        }

    def _compute_order(self, result, order):
        order = order or 'partner ASC'
        return super(SellSummaryPartner, self)._compute_order(result, order)

    def collect_data_by_sql(self, sql_type='out'):
        collection = self.execute_sql(sql_type='out')

        return collection

    def view_detail(self):
        '''销售汇总表（按客户）查看明细按钮'''
        self.ensure_one()
        line_ids = []
        res = []
        move_lines = []
        result = self.get_data_from_cache()
        for line in result:
            if line.get('id') == self.id:
                line_ids = line.get('id_lists')
                move_lines = self.env['wh.move.line'].search(
                    [('id', 'in', line_ids)])

        for move_line in move_lines:
            details = self.env['sell.order.detail'].search(
                [('order_name', '=', move_line.move_id.name),
                 ('goods_id', '=', move_line.goods_id.id)])
            for detail in details:
                res.append(detail.id)

        return {
            'name': '销售明细表',
            'view_mode': 'tree',
            'view_id': False,
            'res_model': 'sell.order.detail',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', res)],
        }
