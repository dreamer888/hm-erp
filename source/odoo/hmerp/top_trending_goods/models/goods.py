from odoo import models, fields, api, _
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT

TOP_TRENDING = [
    ('high_profit_high_amount', '高利润高销售额'),
    ('low_profit_high_amount', '低利润高销售额'),
    ('high_profit_low_amount', '高利润低销售额'),
    ('low_profit_low_amount', '低利润低销售额'),
    ('no_sales', '近期无销量'),
]

class Goods(models.Model):
    _inherit = 'goods'

    def _search_top_trending(self, operator, value):
        '''构造产品分级的搜索表达式

        利润率 = 100 * (产品上的销售价 - 产品上的成本) / 产品上的销售价
        销售额 = 销售订单实际发货量 * 销售订单上产品售价
        '''
        exp = []

        if (operator != '='):
            return exp

        ICP = self.env["ir.config_parameter"].sudo()
        days_range = int(ICP.get_param("top_trending_goods.days_range") or '90') # 销售日期范围（n 天内）
        high_profit = float(ICP.get_param("top_trending_goods.high_profit_ratio") or '0.2') # 高利润的比例
        high_amount = float(ICP.get_param("top_trending_goods.high_amount_ratio") or '0.2') # 高销售额的比例

        # 考察的数据范围是最近90天内已完成的销售订单
        now = datetime.datetime.now()
        start_date = (now - datetime.timedelta(days=days_range)).strftime(DEFAULT_SERVER_DATE_FORMAT)

        # 三个月内有销量的产品
        sql = '''
        SELECT g.id as id,
            g.gpm
        FROM sell_order_line sol
        INNER JOIN sell_order so ON so.id=sol.order_id 
        INNER JOIN goods g ON sol.goods_id=g.id 
        WHERE so.state='done' 
        AND so.date>='%s'
        AND sol.quantity_out>0
        GROUP BY g.id, g.gpm 
        ORDER BY g.gpm desc
        ''' % (start_date, )
        self._cr.execute(sql)

        values = self._cr.fetchall()
        sold_goods_ids = [val[0] for val in values]


        # 1、高利润高销售额产品
        if value == 'high_profit_high_amount':
            # 高利润的产品 IDS
            high = len(sold_goods_ids)*high_profit
            high_profit_goods = [g for i,g in enumerate(sold_goods_ids) if i<high]

            # 按销售额排列的产品IDS
            sql = '''
            SELECT sol.goods_id as id,
                   sum(COALESCE(sol.quantity_out,0)*COALESCE(sol.price_taxed,0)) as amount
            FROM sell_order_line sol
            INNER JOIN sell_order so ON so.id=sol.order_id 
            WHERE so.state='done' 
            AND so.date>='%s'
            AND sol.quantity_out>0
            GROUP BY sol.goods_id 
            ORDER BY amount desc 
            ''' % (start_date, )
            self._cr.execute(sql)

            values = self._cr.fetchall()
            goods_ids = [val[0] for val in values]

            # 高销售额产品 IDS
            high = len(goods_ids)*high_amount
            high_amount_goods = [g for i,g in enumerate(goods_ids) if i<high]
            
            # 高利润高销售额产品 IDS
            res_ids = [x for x in high_profit_goods if x in high_amount_goods]

            return [('id','in',res_ids)]


        # 2、低利润高销售额产品
        if value == 'low_profit_high_amount':
            # 低利润的产品 IDS
            low = len(sold_goods_ids)*high_profit
            low_profit_goods = [g for i,g in enumerate(sold_goods_ids) if i>=low]

            # 按销售额排列的产品IDS
            sql = '''
            SELECT sol.goods_id as id,
                   sum(COALESCE(sol.quantity_out,0)*COALESCE(sol.price_taxed,0)) as amount
            FROM sell_order_line sol
            INNER JOIN sell_order so ON so.id=sol.order_id 
            WHERE so.state='done' 
            AND so.date>='%s'
            AND sol.quantity_out>0
            GROUP BY sol.goods_id 
            ORDER BY amount desc 
            ''' % (start_date, )
            self._cr.execute(sql)

            values = self._cr.fetchall()
            goods_ids = [val[0] for val in values]

            # 高销售额产品 IDS
            high = len(goods_ids)*high_amount
            high_amount_goods = [g for i,g in enumerate(goods_ids) if i<high]
            
            # 低利润高销售额产品 IDS
            res_ids = [x for x in low_profit_goods if x in high_amount_goods]

            return [('id','in',res_ids)]

        # 3、高利润低销售额产品
        if value == 'high_profit_low_amount':
            # 高利润的产品 IDS
            high = len(sold_goods_ids)*high_profit
            high_profit_goods = [g for i,g in enumerate(sold_goods_ids) if i<high]

            # 按销售额排列的产品IDS
            sql = '''
            SELECT sol.goods_id as id,
                   sum(COALESCE(sol.quantity_out,0)*COALESCE(sol.price_taxed,0)) as amount
            FROM sell_order_line sol
            INNER JOIN sell_order so ON so.id=sol.order_id 
            WHERE so.state='done' 
            AND so.date>='%s'
            AND sol.quantity_out>0
            GROUP BY sol.goods_id 
            ORDER BY amount desc 
            ''' % (start_date, )
            self._cr.execute(sql)

            values = self._cr.fetchall()
            goods_ids = [val[0] for val in values]
            
            # 低销售额产品 IDS
            low = len(goods_ids)*high_amount
            low_amount_goods = [g for i,g in enumerate(goods_ids) if i>=low]
            
            # 高利润低销售额产品 IDS
            res_ids = [x for x in high_profit_goods if x in low_amount_goods]

            return [('id','in',res_ids)]

        # 4、低利润低销售额产品
        if value == 'low_profit_low_amount':
            # 低利润的产品 IDS
            low = len(sold_goods_ids)*high_profit
            low_profit_goods = [g for i,g in enumerate(sold_goods_ids) if i>=low]

            # 按销售额排列的产品IDS
            sql = '''
            SELECT sol.goods_id as id,
                   sum(COALESCE(sol.quantity_out,0)*COALESCE(sol.price_taxed,0)) as amount
            FROM sell_order_line sol
            INNER JOIN sell_order so ON so.id=sol.order_id 
            WHERE so.state='done' 
            AND so.date>='%s'
            AND sol.quantity_out>0
            GROUP BY sol.goods_id 
            ORDER BY amount desc 
            ''' % (start_date, )
            self._cr.execute(sql)

            values = self._cr.fetchall()
            goods_ids = [val[0] for val in values]

            # 低销售额产品 IDS
            low = len(goods_ids)*high_amount
            low_amount_goods = [g for i,g in enumerate(goods_ids) if i>=low]
            
            # 低利润低销售额产品 IDS
            res_ids = [x for x in low_profit_goods if x in low_amount_goods]

            return [('id','in',res_ids)]

        # 5、三个月内无销量产品
        if value == 'no_sales':
            return [('id','not in',sold_goods_ids)]

        return exp

    def _get_top_trending_goods(self):
        '''近期销售统计
        近期出货量，是指近期（通常是90天，但可在后台设置）销售订单的实际发货量合计。
        '''
        ICP = self.env["ir.config_parameter"].sudo()
        days_range = int(ICP.get_param("top_trending_goods.days_range") or '90') # 销售日期范围（n 天内）

        # 考察的数据范围是最近90天内已完成的销售订单
        now = datetime.datetime.now()
        start_date = (now - datetime.timedelta(days=days_range)).strftime(DEFAULT_SERVER_DATE_FORMAT)

        sql = '''
        SELECT sol.goods_id as id,
            sum(COALESCE(sol.quantity_out,0)) as out_qty,
            sum(COALESCE(sol.quantity_out,0)*COALESCE(sol.price_taxed,0)) as amount
        FROM sell_order_line sol
        INNER JOIN sell_order so ON so.id=sol.order_id 
        WHERE so.state='done' 
        AND so.date>=%s
        AND sol.quantity_out>0
        AND sol.goods_id in %s
        GROUP BY sol.goods_id 
        ORDER BY out_qty desc 
        '''
        self._cr.execute(sql, [start_date, tuple(self.ids)])

        values = self._cr.fetchall()
        out_qty = {val[0]:val[1] for val in values}
        amount = {val[0]:val[2] for val in values}

        for p in self:
            out = out_qty.get(p.id,0.0)
            amt = amount.get(p.id,0.0)
            p.update({
                'top_trending_out': out,
                'top_trending_amount': amt,
                'top_trending_profit': amt - out*(p.cost or 0.0),
                }) 

    top_trending = fields.Selection(TOP_TRENDING, store=False, search='_search_top_trending', string='产品分级', readonly=True,
                          help='用于显示前端窗口的产品分级筛选条件')

    top_trending_profit = fields.Float('近期利润',
                          compute=_get_top_trending_goods,
                          digits='Amount',
                          help='近期利润 = 销售订单实际发货量 * 销售订单上产品售价 - 销售订单实际发货量 * 产品上的成本价')
    top_trending_amount = fields.Float('近期销售额',
                          compute=_get_top_trending_goods,
                          digits='Amount',
                          help='近期销售额 = 销售订单实际发货量 * 销售订单上产品售价')
    top_trending_out = fields.Float('近期出货量',
                          compute=_get_top_trending_goods,
                          digits='Quantity',
                          help='近期出货量，是指近期（通常是90天，但可在后台设置）销售订单的实际发货量合计。')
