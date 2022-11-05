
from odoo import tools
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger=logging.getLogger(__name__)


# 补货申请单确认状态可选值
STOCK_REQUEST_STATES = [
    ('unsubmit', '未提交'),
    ('draft', '未确认'),
    ('done', '已确认'),
    ('cancel', '已作废')]


class StockRequest(models.Model):
    _name = 'stock.request'
    _inherit = ['mail.thread']
    _description = '补货申请'

    name = fields.Char('编号')
    date = fields.Date('日期',
                       default=lambda self: fields.Date.context_today(self),
                       states={'done': [('readonly', True)]})
    user_id = fields.Many2one(
        'res.users',
        '经办人',
        ondelete='restrict',
        states={'done': [('readonly', True)]},
        default=lambda self: self.env.user,
        help='单据经办人',
    )
    line_ids = fields.One2many('stock.request.line',
                               'request_id',
                               '补货申请行',
                               states={'done': [('readonly', True)]})
    state = fields.Selection(STOCK_REQUEST_STATES, '确认状态', readonly=True,
                             help="补货申请的确认状态", copy=False,
                             index=True,
                             default='unsubmit')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def stock_query(self):
        ''' 点击 查询库存 按钮 生成补货申请行
                                    每行一个商品一个属性的 数量，补货数量
         '''
        self.ensure_one()
        self._fill_direct_request() # 只考虑独立需求
        self._fill_rel_request()    # 下推相关需求
        self.clear_lines()
        self.state = 'draft'
    
    def _fill_direct_request(self):
        goods = self.env['goods'].search([('no_stock', '=', False)])
        for good in goods:
            qty = 0  # 当前数量
            to_delivery_qty = 0  # 未出库数量
            to_receipt_qty = 0  # 未入库数量
            to_sell_qty = 0  # 未确认销售数量
            to_buy_qty = 0  # 未确认采购数量

            wh_move_lines = self.env['wh.move.line'].search(
                [('goods_id', '=', good.id)])

            attribute_dict = {}
            to_delivery_dict = {}
            to_receipt_dict = {}
            to_sell_dict = {}
            to_buy_dict = {}
            wh_scrap_id = self.env.company.wh_scrap_id.id
            for wh_move_line in wh_move_lines:
                # 涉及废品库的出入库不影响需求计算
                if wh_move_line.warehouse_dest_id.id == wh_scrap_id \
                      or wh_move_line.warehouse_id.id == wh_scrap_id:
                    continue
                # 计算当前数量
                if wh_move_line.state == 'done':
                    if wh_move_line.warehouse_dest_id.type == 'stock':  # 目的库位为库存库位
                        if wh_move_line.attribute_id:  # 商品存在属性
                            if wh_move_line.attribute_id not in attribute_dict:
                                attribute_dict.update(
                                    {wh_move_line.attribute_id: wh_move_line.qty_remaining})
                            else:
                                attribute_dict[wh_move_line.attribute_id] += wh_move_line.qty_remaining
                        else:  # 商品不存在属性
                            qty += wh_move_line.qty_remaining
                # 计算未发货和未到货数量
                else:
                    if wh_move_line.type == 'out':
                        if wh_move_line.attribute_id:  # 商品存在属性
                            if wh_move_line.attribute_id not in to_delivery_dict:
                                to_delivery_dict.update(
                                    {wh_move_line.attribute_id: wh_move_line.goods_qty})
                            else:
                                to_delivery_dict[wh_move_line.attribute_id] += wh_move_line.goods_qty
                        else:  # 商品不存在属性
                            to_delivery_qty += wh_move_line.goods_qty
                    elif wh_move_line.type == 'in':
                        if wh_move_line.attribute_id:  # 商品存在属性
                            if wh_move_line.attribute_id not in to_receipt_dict:
                                to_receipt_dict.update(
                                    {wh_move_line.attribute_id: wh_move_line.goods_qty})
                            else:
                                to_receipt_dict[wh_move_line.attribute_id] += wh_move_line.goods_qty
                        else:  # 商品不存在属性
                            to_receipt_qty += wh_move_line.goods_qty
            # 计算未销售数量
            sell_order_lines = self.env['sell.order.line'].search([('goods_id', '=', good.id),
                                                                   ('order_id.state', '=', 'draft')])
            for line in sell_order_lines:
                if line.attribute_id:  # 商品存在属性
                    if line.attribute_id not in to_sell_dict:
                        to_sell_dict.update({line.attribute_id: line.quantity})
                    else:
                        to_sell_dict[line.attribute_id] += line.quantity
                else:  # 商品不存在属性
                    to_sell_qty += line.quantity
            # 计算未采购数量
            buy_order_lines = self.env['buy.order.line'].search([('goods_id', '=', good.id),
                                                                 ('order_id.state', '=', 'draft')])
            for line in buy_order_lines:
                if line.attribute_id:  # 商品存在属性
                    if line.attribute_id not in to_buy_dict:
                        to_buy_dict.update({line.attribute_id: line.quantity})
                    else:
                        to_buy_dict[line.attribute_id] += line.quantity
                else:  # 商品不存在属性
                    to_buy_qty += line.quantity

            # 生成补货申请行
            qty_available = 0  # 可用库存
            if good.attribute_ids:  # 商品存在属性
                for attribute in good.attribute_ids:
                    qty = attribute in attribute_dict and attribute_dict[attribute] or 0
                    to_sell_qty = attribute in to_sell_dict and to_sell_dict[attribute] or 0
                    to_delivery_qty = attribute in to_delivery_dict and to_delivery_dict[
                        attribute] or 0
                    to_buy_qty = attribute in to_buy_dict and to_buy_dict[attribute] or 0
                    to_receipt_qty = attribute in to_receipt_dict and to_receipt_dict[
                        attribute] or 0
                    qty_available = qty + to_receipt_qty + \
                        to_buy_qty - to_delivery_qty - to_sell_qty
                    if True:  # qty_available < good.min_stock_qty:
                        _logger.info('商品 %s %s 有 %d 的独立需求' %
                            (good.name, attribute.name, good.min_stock_qty - qty_available))
                        self.env['stock.request.line'].create({
                            'request_id': self.id,
                            'goods_id': good.id,
                            'attribute_id': attribute.id,
                            'qty': qty,
                            'to_sell_qty': to_sell_qty,
                            'to_delivery_qty': to_delivery_qty,
                            'to_buy_qty': to_buy_qty,
                            'to_receipt_qty': to_receipt_qty,
                            'min_stock_qty': good.min_stock_qty,
                            'request_qty': good.min_stock_qty - qty_available,
                            'uom_id': good.uom_id.id,
                            'supplier_id': good.supplier_id and good.supplier_id.id or False,
                            'get_way': good.get_way,
                            'to_push_qty': good.get_way != 'po' and good.min_stock_qty - qty_available,
                        })
            else:  # 商品不存在属性
                qty_available = qty + to_receipt_qty + \
                    to_buy_qty - to_delivery_qty - to_sell_qty
                if True:  # qty_available < good.min_stock_qty:
                    _logger.info('商品 %s 有 %d 的独立需求' %
                            (good.name, good.min_stock_qty - qty_available))
                    self.env['stock.request.line'].create({
                        'request_id': self.id,
                        'goods_id': good.id,
                        'qty': qty,
                        'to_sell_qty': to_sell_qty,
                        'to_delivery_qty': to_delivery_qty,
                        'to_buy_qty': to_buy_qty,
                        'to_receipt_qty': to_receipt_qty,
                        'min_stock_qty': good.min_stock_qty,
                        'request_qty': good.min_stock_qty - qty_available,
                        'uom_id': good.uom_id.id,
                        'supplier_id': good.supplier_id and good.supplier_id.id or False,
                        'get_way': good.get_way,
                        'to_push_qty': good.get_way != 'po' and good.min_stock_qty - qty_available,
                    })

    def _fill_rel_request(self):
        '''
        相关需求逐级下推
        '''
        while True:
            if not any([l.to_push_qty > 0 for l in self.line_ids]):
                break
            for line in self.line_ids:
                if line.to_push_qty <= 0:
                    continue
                bom_line = self.env['wh.bom.line'].search(
                    [('goods_id', '=', line.goods_id.id),
                     ('attribute_id', '=', line.attribute_id.id),
                     ('bom_id.active', '=', True),
                     ('type', '=', 'parent')])
                if not bom_line:
                    raise UserError('未找到补货申请行商品%s%s%s的物料清单。' % (
                        line.goods_id.code or '',
                        line.goods_id.name,
                        line.attribute_id.name or ''))
                for o in bom_line.bom_id.line_child_ids:    # BOM行
                    # 忽略BOM行上的虚拟商品
                    if o.goods_id.no_stock:
                        continue
                    # 是否已有此商品的需求
                    exist_line = self.env['stock.request.line'].search([
                        ('request_id', '=', self.id),
                        ('goods_id', '=', o.goods_id.id),
                        ('attribute_id', '=', o.attribute_id.id),
                    ])
                    need_qty = o.goods_qty * line.request_qty / bom_line.goods_qty
                    # 有则加入
                    if exist_line:
                        _logger.info('商品 %s %s 有 %d 的相关需求并入' %
                            (o.goods_id.name, o.attribute_id.name or '', need_qty))
                        exist_line.request_qty += need_qty
                        exist_line.rel_req_qty += need_qty
                        if exist_line.get_way != 'po':
                            exist_line.to_push_qty += need_qty
                    # 无则创建
                    else:
                        qty = to_receipt_qty = 0
                        for wml in self.env['wh.move.line'].search([
                               ('type', '=', 'in'),
                               ('goods_id', '=', o.goods_id.id),
                               ('attribute_id', '=', o.attribute_id.id)
                                ]):
                            if wml.state == 'done':
                                qty += wml.qty_remaining
                            else:
                                to_receipt_qty += wml.qty_remaining
                        to_buy_qty = sum([l.quantity for l in 
                            self.env['buy.order.line'].search(
                                [('order_id.state', '=', 'draft'),
                                 ('goods_id', '=', o.goods_id.id),
                                 ('attribute_id', '=', o.attribute_id.id)])])
                        qty_available = qty + to_receipt_qty + to_buy_qty - need_qty
                        _logger.info('商品 %s %s 有 %d 的相关需求' %
                            (o.goods_id.name, o.attribute_id.name or '', need_qty))
                        request_line_ids = self.env['stock.request.line'].create({
                                'request_id': self.id,
                                'goods_id': o.goods_id.id,
                                'attribute_id': o.attribute_id and o.attribute_id.id or False,
                                'rel_req_qty': need_qty,
                                'qty': qty,
                                'to_receipt_qty': to_receipt_qty,
                                'to_buy_qty': to_buy_qty,
                                'min_stock_qty': o.goods_id.min_stock_qty,
                                'request_qty': o.goods_id.min_stock_qty - qty_available,
                                'uom_id': o.goods_id.uom_id.id,
                                'supplier_id': o.goods_id.supplier_id and o.goods_id.supplier_id.id or False,
                                'get_way': o.goods_id.get_way,
                                'to_push_qty': o.goods_id.get_way != 'po' and o.goods_id.min_stock_qty - qty_available,
                                })
                line.to_push_qty = 0

    def clear_lines(self):
        for line in self.line_ids:
            if line.request_qty <= 0:
                line.sudo().unlink()

    def _get_buy_order_line_data(self, line, buy_order):
        price = line.goods_id.cost
        for vendor_price in line.goods_id.vendor_ids:
            if vendor_price.date and vendor_price.date > buy_order.date:
                continue
            if vendor_price.vendor_id == buy_order.partner_id \
                    and line.request_qty >= vendor_price.min_qty:
                price = vendor_price.price
                break

        return {
            'order_id': buy_order.id,
            'goods_id': line.goods_id.id,
            'attribute_id': line.attribute_id and line.attribute_id.id or False,
            'uom_id': line.uom_id.id,
            'quantity': line.request_qty,
            'price': price,
            'note': '补货申请单号：%s' % line.request_id.name
        }

    def stock_request_done(selfs):
        for self in selfs:
            if self.state == 'done':
                raise UserError('请不要重复确认')
            for line in self.line_ids:
                _logger.info('正在处理%s' % line.goods_id.name)
                if line.request_qty <= 0:
                    _logger.info('忽略%s' % line.goods_id.name)
                    continue
                if line.goods_id.get_way == 'po':
                    # 创建采购订单
                    if not line.supplier_id:
                        raise UserError('请输入补货申请行商品%s%s 的供应商。' % (
                            line.goods_id.name, line.attribute_id.name or ''))
                    self._create_po(line)
                    
                elif line.goods_id.get_way == 'ous':
                    # 创建委外单
                    if not line.supplier_id:
                        raise UserError('请输入补货申请行商品%s%s 的供应商。' % (
                            line.goods_id.name, line.attribute_id.name or ''))
                    self._create_outsource(line)
                else:
                    self._create_assembly(line)
            self.state = 'done'
    
    def _create_outsource(self, line):
        # 创建委外单
        bom_line = self.env['wh.bom.line'].search(
            [('goods_id', '=', line.goods_id.id),
             ('attribute_id', '=', line.attribute_id.id),
             ('bom_id.active', '=', True),
                ('bom_id.type', '=', 'outsource'),
                ('type', '=', 'parent')])
        outsource = self.env['outsource'].create({
            'bom_id': bom_line.bom_id.id,
            'outsource_partner_id': line.supplier_id.id,
            'goods_qty': 0,
            })
        outsource.onchange_bom()
        outsource.goods_qty = line.request_qty
        outsource.onchange_goods_qty()
        outsource.note = ' 补货申请单号：%s' % line.request_id.name
        # 如果待处理行中有属性，则把它传至的组合件行中
        if line.attribute_id:
            for line_in in assembly.line_in_ids:
                line_in.attribute_id = line.attribute_id

    def _create_assembly(self, line):
        # 创建组装单
        bom_line = self.env['wh.bom.line'].search(
            [('goods_id', '=', line.goods_id.id),
             ('attribute_id', '=', line.attribute_id.id),
             ('bom_id.active', '=', True),
                ('bom_id.type', '=', 'assembly'),
                ('type', '=', 'parent')])
        assembly = self.env['wh.assembly'].create({
            'bom_id': bom_line.bom_id.id,
            'goods_qty': 0,
            })
        assembly.onchange_bom()
        assembly.goods_qty = line.request_qty
        assembly.onchange_goods_qty()
        assembly.note = ' 补货申请单号：%s' % line.request_id.name
        # 如果待处理行中有属性，则把它传至组装单的组合件行中
        if line.attribute_id:
            for line_in in assembly.line_in_ids:
                line_in.attribute_id = line.attribute_id

    def _create_po(self, line):
        # 找供应商相同的采购订单
        buy_order = self.env['buy.order'].search(
            [('partner_id', '=', line.supplier_id.id),
             ('state', '=', 'draft')])
        if len(buy_order) >= 1:
            buy_order = buy_order[0]
        else:
            # 创建新的采购订单
            buy_order = self.env['buy.order'].with_context(
                                    warehouse_dest_type='stock').create({
                                        'partner_id': line.supplier_id.id
                                        })
        # 找相同的采购单行
        buy_order_line = self.env['buy.order.line'].search(
            [('order_id.partner_id', '=', line.supplier_id.id),
             ('order_id.state', '=', 'draft'),
             ('goods_id', '=', line.goods_id.id),
             ('attribute_id', '=', line.attribute_id.id)])
        if len(buy_order_line) > 1:
            raise UserError('供应商%s 商品%s%s 存在多条未确认采购订单行。请联系采购人员处理。'
                % (line.supplier_id.name, line.goods_id.name, line.attribute_id.name or ''))
        if buy_order_line:
            # 增加原订单行的商品数量
            buy_order_line.quantity += line.request_qty
            buy_order_line.note = buy_order_line.note or ''
            buy_order_line.note += ' %s' % (line.request_id.name)
        else:
            # 创建采购订单行
            vals = self._get_buy_order_line_data(line, buy_order)
            bol = self.env['buy.order.line'].create(vals)
            bol.onchange_price()

class StockRequestLine(models.Model):
    _name = 'stock.request.line'
    _description = '补货申请行'

    request_id = fields.Many2one('stock.request', '补货申请')
    goods_id = fields.Many2one('goods', '商品')
    attribute_id = fields.Many2one('attribute', '属性')
    
    # 需求
    to_sell_qty = fields.Float('未确认销售数量', digits='Quantity')
    to_delivery_qty = fields.Float(
        '未出库数量', digits='Quantity')
    min_stock_qty = fields.Float(
        '安全库存数量', digits='Quantity')
    rel_req_qty = fields.Float(
        '相关需求数量', digits='Quantity')
    # 供给
    qty = fields.Float('当前数量', digits='Quantity')
    to_buy_qty = fields.Float('未确认采购数量', digits='Quantity')
    to_receipt_qty = fields.Float(
        '未入库数量', digits='Quantity')
    
    request_qty = fields.Float('申请补货数量', digits='Quantity')
    get_way = fields.Char('获取方式')
    to_push_qty = fields.Float('未下推数量', digits='Quantity')

    uom_id = fields.Many2one('uom', '单位')
    supplier_id = fields.Many2one('partner', '供应商')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class SourceOrderLine(models.Model):
    _inherit = 'source.order.line'

    order_name = fields.Char('订单号', compute='_compute_order_name', store=True)
    order_ref = fields.Char('对方订单号', compute='_compute_order_name', store=True)

    @api.depends('name')
    def _compute_order_name(self):
        for s in self:
            s.order_name = ''
            s.order_ref = ''
            wh_move = self.env['sell.delivery'].search(
                [('invoice_id', '=', s.name.id)])
            if not wh_move:
                wh_move = self.env['buy.receipt'].search(
                    [('invoice_id', '=', s.name.id)])
            if wh_move:
                s.order_name = wh_move.order_id.name
                s.order_ref = wh_move.order_id.ref
