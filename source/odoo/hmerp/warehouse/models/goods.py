
from .utils import safe_division
from odoo.exceptions import UserError
from odoo import models, fields, api
from odoo.tools import float_compare


class Goods(models.Model):
    _inherit = 'goods'

    net_weight = fields.Float('净重', digits='Weight')
    current_qty = fields.Float('当前数量', compute='compute_stock_qty', digits='Quantity')
    max_stock_qty = fields.Float('库存上限', digits='Quantity')
    min_stock_qty = fields.Float('库存下限', digits='Quantity')
    moq = fields.Float('最小订单量', digits='Quantity')
    sell_lead_time = fields.Char('销售备货周期')
    excess = fields.Boolean('允许订单超发')
    bom_count = fields.Integer('Bom个数', compute="_compute_count")
    bom_ids = fields.Many2many('wh.bom', string='Bom', compute="_compute_count")
    move_line_count = fields.Integer('调拨次数', compute="_compute_count")
    
    incoming_ids = fields.One2many(
        string='即将入库',
        comodel_name='wh.move.line',
        inverse_name='goods_id',
        domain=[('type','=','in'),('state','=','draft')],
        readonly=True,
    )

    outgoing_ids = fields.One2many(
        string='即将出库',
        comodel_name='wh.move.line',
        inverse_name='goods_id',
        domain=[('type','=','out'),('state','=','draft')],
        readonly=True,
    )

    available_qty = fields.Float('可用数量', compute='compute_stock_qty', digits='Quantity')
    

    # 使用SQL来取得指定商品情况下的库存数量
    def get_stock_qty(self):
        for Goods in self:
            self.env.cr.execute('''
                SELECT sum(line.qty_remaining) as qty,
                       wh.name as warehouse
                FROM wh_move_line line
                LEFT JOIN warehouse wh ON line.warehouse_dest_id = wh.id
                WHERE line.qty_remaining != 0
                  AND wh.type = 'stock'
                  AND line.state = 'done'
                  AND line.goods_id = %s
                GROUP BY wh.name
            ''' % (Goods.id,))
            return self.env.cr.dictfetchall()

    def compute_stock_qty(self):
        for g in self:
            g.current_qty = sum(line.get('qty') for line in g.get_stock_qty())
            g.available_qty = g.current_qty                    \
                + sum(l.goods_qty for l in g.incoming_ids)     \
                - sum(l.goods_qty for l in g.outgoing_ids)

    def _get_cost(self, warehouse=None, ignore=None):
        # 如果没有历史的剩余数量，计算最后一条move的成本
        # 存在一种情况，计算一条line的成本的时候，先done掉该line，之后在通过该函数
        # 查询成本，此时百分百搜到当前的line，所以添加ignore参数来忽略掉指定的line
        self.ensure_one()
        if warehouse:
            domain = [
                ('state', '=', 'done'),
                ('goods_id', '=', self.id),
                ('warehouse_dest_id', '=', warehouse.id)
            ]

            if ignore:
                if isinstance(ignore, int):
                    ignore = [ignore]

                domain.append(('id', 'not in', ignore))

            move = self.env['wh.move.line'].search(
                domain, limit=1, order='cost_time desc, id desc')
            if move:
                return move.cost_unit

        return self.cost

    def get_suggested_cost_by_warehouse(
            self, warehouse, qty, lot_id=None, attribute=None, ignore_move=None):
        # 存在一种情况，计算一条line的成本的时候，先done掉该line，之后在通过该函数
        # 查询成本，此时百分百搜到当前的line，所以添加ignore参数来忽略掉指定的line
        if lot_id:
            records, cost = self.get_matching_records_by_lot(
                lot_id, qty, suggested=True)
        else:
            records, cost = self.get_matching_records(
                warehouse, qty, attribute=attribute, ignore_stock=True, ignore=ignore_move)

        matching_qty = sum(record.get('qty') for record in records)
        if matching_qty:
            cost_unit = safe_division(cost, matching_qty)
            if matching_qty >= qty:
                return cost, cost_unit
        else:
            cost_unit = self._get_cost(warehouse, ignore=ignore_move)
        return cost_unit * qty, cost_unit

    def is_using_matching(self):
        """
        是否需要获取匹配记录
        :return:
        """
        if self.no_stock:
            return False
        return True

    def is_using_batch(self):
        """
        是否使用批号管理
        :return:
        """
        self.ensure_one()
        return self.using_batch

    def get_matching_records_by_lot(self, lot_id, qty, uos_qty=0, suggested=False):
        """
        按批号来获取匹配记录
        :param lot_id: 明细中输入的批号
        :param qty: 明细中输入的数量
        :param uos_qty: 明细中输入的辅助数量
        :param suggested:
        :return: 匹配记录和成本
        """
        self.ensure_one()
        if not lot_id:
            raise UserError(u'批号没有被指定，无法获得成本')

        if not suggested and lot_id.state != 'done':
            raise UserError(u'批号%s还没有实际入库，请先确认该入库' % lot_id.move_id.name)

        decimal_quantity = self.env.ref('core.decimal_quantity')
        if float_compare(qty, lot_id.qty_remaining,  decimal_quantity.digits) > 0 and not self.env.context.get('wh_in_line_ids'):
            raise UserError(u'商品%s %s 批次 %s 的库存数量 %s 不够本次出库 %s' % (
                self.code and '[%s]' % self.code or ''  ,self.name, lot_id.lot, lot_id.qty_remaining,qty))

        return [{'line_in_id': lot_id.id, 'qty': qty, 'uos_qty': uos_qty,
                 'expiration_date': lot_id.expiration_date}], \
            lot_id.get_real_cost_unit() * qty

    def get_matching_records(self, warehouse, qty, uos_qty=0, attribute=None,
                             ignore_stock=False, ignore=None, move_line=False):
        """
        获取匹配记录，不考虑批号
        :param ignore_stock: 当参数指定为True的时候，此时忽略库存警告
        :param ignore: 一个move_line列表，指定查询成本的时候跳过这些move
        :return: 匹配记录和成本
        """
        matching_records = []
        for Goods in self:
            domain = [
                ('qty_remaining', '>', 0),
                ('state', '=', 'done'),
                ('warehouse_dest_id', '=', warehouse.id),
                ('goods_id', '=', Goods.id)
            ]
            if ignore:
                if isinstance(ignore, int):
                    domain.append(('id', 'not in', [ignore]))

            if attribute:
                domain.append(('attribute_id', '=', attribute.id))

            # 内部移库，从源库位移到目的库位，匹配时从源库位取值; location.py confirm_change 方法
            if self.env.context.get('location'):
                domain.append(
                    ('location_id', '=', self.env.context.get('location')))

            # 出库单行 填写了库位
            if not self.env.context.get('location') and move_line and move_line.location_id:
                domain.append(('location_id', '=', move_line.location_id.id))

            # TODO @zzx需要在大量数据的情况下评估一下速度
            # 出库顺序按 库位 就近、先到期先出、先进先出
            lines = self.env['wh.move.line'].search(
                domain, order='location_id, expiration_date, cost_time, id')

            qty_to_go, uos_qty_to_go, cost = qty, uos_qty, 0    # 分别为待出库商品的数量、辅助数量和成本
            for line in lines:
                if qty_to_go <= 0 and uos_qty_to_go <= 0:
                    break

                matching_qty = min(line.qty_remaining, qty_to_go)
                matching_uos_qty = matching_qty / Goods.conversion

                matching_records.append({'line_in_id': line.id, 'expiration_date': line.expiration_date,
                                         'qty': matching_qty, 'uos_qty': matching_uos_qty})

                cost += matching_qty * line.get_real_cost_unit()
                qty_to_go -= matching_qty
                uos_qty_to_go -= matching_uos_qty
            else:
                decimal_quantity = self.env.ref('core.decimal_quantity')
                if not ignore_stock and float_compare(qty_to_go, 0, decimal_quantity.digits) > 0 and not self.env.context.get('wh_in_line_ids'):
                    raise UserError(u'商品%s %s的库存数量不够本次出库' % (Goods.code and '[%s]' % Goods.code or '',  Goods.name,))
                if self.env.context.get('wh_in_line_ids'):
                    domain = [('id', 'in', self.env.context.get('wh_in_line_ids')),
                              ('state', '=', 'done'),
                              ('warehouse_dest_id', '=', warehouse.id),
                              ('goods_id', '=', Goods.id)]
                    if attribute:
                        domain.append(('attribute_id', '=', attribute.id))
                    line_in_id = self.env['wh.move.line'].search(
                        domain, order='expiration_date, cost_time, id')
                    if line_in_id:
                        matching_records.append({'line_in_id': line_in_id.id, 'expiration_date': line_in_id.expiration_date,
                                                 'qty': qty_to_go, 'uos_qty': uos_qty_to_go})

            return matching_records, cost

    _used_not_allowed_modification = ({'uom_id','uos_id','conversion'},
                                      '商品已被使用， 不允许修改单位或转化率')
    def write(self, vals):
        used_fields, used_msg = self._used_not_allowed_modification
        if len(used_fields)>0 and ( set(vals.keys()).intersection(used_fields) ):
            # 所有用到了商品的字段
            self.env.cr.execute("select imf.name, imf.model from goods_reference_black_list grbl "+
                                 "left join ir_model_fields imf on imf.model_id = grbl.ref_model_id" +
                                " where imf.relation=%s " +
                                "and imf.ttype in ('many2one') and imf.store=true;",
                                ('goods', ))
            relation_fields = self.env.cr.fetchall()
            for goods in self:
                been_used = False
                # 所有用到了当前商品的记录
                for field, model in relation_fields:
                    if not been_used:
                        sql = "select id from " + model.replace('.', '_') + \
                            " where " + field + "=" + str(goods.id) + ";"
                        self.env.cr.execute(sql)
                        if self.env.cr.fetchall():
                            been_used = True
                if been_used:
                    raise UserError(used_msg)
        return super().write(vals)

    def _compute_count(self):
        ''' 此商品作为组合件的BOM个数 '''
        for s in self:
            bom_lines = self.env['wh.bom.line'].search(
                    [('goods_id', '=', s.id),
                     ('type', '=', 'parent')])
            s.bom_ids = [(6, 0, list(set([l.bom_id.id for l in bom_lines])))]
            s.bom_count = len(s.bom_ids)
            move_lines = self.env['wh.move.line'].search(
                    [('goods_id', '=', s.id),
                     ('state', '=', 'done')])
            s.move_line_count = len(move_lines)

    def button_list_bom(self):
        return {
            'name': '%s 物料清单' % self.name,
            'view_mode': 'list,form',
            'res_model': 'wh.bom',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.bom_ids.ids)],
        }

    def button_list_move(self):
        return {
            'name': '%s 库存调拨' % self.name,
            'view_mode': 'list',
            'res_model': 'wh.move.line',
            'type': 'ir.actions.act_window',
            'domain': [('goods_id', '=', self.id)],
            'context': {'search_default_done':1}
        }

class GoodsReferenceBlackList(models.Model):
    _name = 'goods.reference.black.list'
    _description = '商品引用检测黑名单'
    
    ref_model_id = fields.Many2one('ir.model', '模型', help='指定的模型若有引用商品的，该商品对应的单位或转化率无法进行修改')
