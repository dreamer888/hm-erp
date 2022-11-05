from odoo import fields, api, models
from datetime import datetime


class MrpMatDetialReport(models.Model):
    _name = 'mrp.mat.detial.report'
    _inherit = 'report.base'
    _description = '生产材料领用明细'

    id = fields.Integer('单据ID')
    name = fields.Char('单据号码')
    type = fields.Char('类型')
    date = fields.Date('单据日期')
    user_name = fields.Many2one('res.users', '经办人')
    order_name = fields.Char('销售订单')
    plm_name = fields.Char('生产加工单')
    plm_goods_name = fields.Char('加工商品')
    plm_qty = fields.Float('加工数量', digits='Quantity')
    warehouse_name = fields.Char('仓库')
    goods_name = fields.Char('商品')
    qty = fields.Float('应发量', digits='Quantity')
    uom = fields.Char('单位')
    goods_qty = fields.Float('数量', digits='Quantity')
    state = fields.Selection([
                ('draft', '草稿'),
                ('done', '已确认'),
                ], string='状态')


    def select_sql(self,sql_type='out'):
        return '''
        select own.id,own.type,own.name,own.date,own.user_id AS user_name,ob.name AS order_name,plm.name AS plm_name,
        pgd.name || pgd.name AS plm_goods_name,plm.qty plm_qty,w.name AS warehouse_name,gd.name || gd.name AS goods_name,plm_line.qty,uom.name AS uom,
        case when own.type = '退料' then -wml.goods_qty else wml.goods_qty end goods_qty,own.state
        '''

    def from_sql(self,sql_type='out'):
        return '''
        FROM wh_move_line AS wml
        LEFT JOIN goods gd ON wml.goods_id = gd.id
        LEFT JOIN uom ON uom.id = gd.uom_id
        LEFT JOIN core_category AS categ ON gd.category_id = categ.id
        LEFT JOIN mrp_plm AS plm ON wml.plm_id = plm.id
        LEFT JOIN mrp_plm_line AS plm_line ON wml.plm_line_id = plm_line.id
        LEFT JOIN goods pgd ON plm.goods_id = pgd.id
        LEFT JOIN(
            select cons.id,cons.name,wh.date,wh.state,wh.id AS move_id,wh.user_id,wh.warehouse_dest_id AS warehouse_id,
                    case when cons.plm_cons_add_id is not null then '补料' else '领料' end AS type 
            FROM mrp_plm_cons AS cons,wh_move AS wh where wh.id = cons.mrp_plm_cons_id
            union all
            select retu.id,retu.name,wh.date,wh.state,wh.id AS move_id,wh.user_id,wh.warehouse_dest_id AS warehouse_id,'退料'
            FROM mrp_plm_cons_retu AS retu,wh_move AS wh where wh.id = retu.mrp_plm_cons_retu_id
        )own ON own.move_id = wml.move_id  
        LEFT JOIN warehouse w ON w.id = own.warehouse_id
        LEFT JOIN sell_order ob ON ob.id = plm.order_id       
        '''
    
    def where_sql(self,sql_type='out'):
        extra = ''
        if self.env.context.get('name'):
            extra += "AND own.name like '%{name}%'".format(**{'name': self.env.context.get('name')})
        if self.env.context.get('goods_id'):
            extra += 'AND wml.goods_id = {goods_id}'
        if self.env.context.get('warehouse_id'):
            extra += 'AND own.warehouse_id = {warehouse_id}'
        if self.env.context.get('goods_categ_id'):
            extra += 'AND categ.id = {goods_categ_id}'
        if self.env.context.get('state_type') and self.env.context.get('state_type') != 'all':
            extra += ("AND own.state = '%s'" % self.env.context.get('state_type'))

        return '''
        WHERE own.id IS NOT NULL
          AND wml.date >= '{date_start}'
          AND wml.date <= '{date_end}'
          %s
        ''' % extra

    def get_context(self, sql_type='out', context=None):
        n_context = {}
        n_context['date_start'] = self.env.context.get('date_start')
        n_context['date_end'] = self.env.context.get('date_end')
        if self.env.context.get('goods_id'):
            n_context['goods_id'] = context.get('goods_id') and self.env.context.get('goods_id')[0] or ''
        if self.env.context.get('warehouse_id'):
            n_context['warehouse_id'] = context.get('warehouse_id') and self.env.context.get('warehouse_id')[0] or ''
        if self.env.context.get('goods_categ_id'):
            n_context['goods_categ_id'] =context.get('goods_categ_id') and  self.env.context.get('goods_categ_id')[0] or ''

        return n_context

    def collect_data_by_sql(self, sql_type='out'):
        collection = self.execute_sql(sql_type='out')
        return collection
        
    def view_bil_from(self):
        '''查看单据内容'''
        self.ensure_one()        
        result = self.get_data_from_cache()
        if not result or len(result) == 0:
            return {}
        id = result[0].get('id')
        type = result[0].get('type')
        name = ''
        view_name = ''
        model_id = ''

        if type == '退料':
            name = '生产退料'
            view_name = 'manufacture.mrp_plm_cons_retu_form'
            model_id = 'mrp.plm.cons.retu'
        else:
            name = '生产领料'
            view_name = 'manufacture.mrp_plm_cons_form'
            model_id = 'mrp.plm.cons'
        action = {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': model_id,
            'view_id': False,
            'target': 'current',
        }
        view_id = self.env.ref(view_name).id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = id
        return action

