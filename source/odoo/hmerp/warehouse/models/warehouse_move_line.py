
from logging import Logger
import logging
from .utils import safe_division
from jinja2 import Environment, PackageLoader
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging
_logger = logging.getLogger(__name__)

env = Environment(loader=PackageLoader(
    'odoo.addons.warehouse', 'html'), autoescape=True)


class WhMoveLine(models.Model):
    _name = 'wh.move.line'
    _description = '移库单明细'
    _order = 'lot'

    _rec_name = 'note'

    MOVE_LINE_TYPE = [
        ('out', '出库'),
        ('in', '入库'),
        ('internal', '内部调拨'),
    ]

    MOVE_LINE_STATE = [
        ('draft', '草稿'),
        ('done', '已完成'),
        ('cancel', '已作废'),
    ]

    ORIGIN_EXPLAIN = {
        ('wh.assembly', 'out'): '组装单子件',
        ('wh.assembly', 'in'): '组装单组合件',
        ('wh.disassembly', 'out'): '拆卸单组合件',
        ('wh.disassembly', 'in'): '拆卸单子件',
        ('wh.internal', True): '调拨出库',
        ('wh.internal', False): '调拨入库',
        'wh.out.inventory': '盘亏',
        'wh.out.others': '其他出库',
        'wh.in.inventory': '盘盈',
        'wh.in.others': '其他入库',
        'buy.receipt.buy': '采购入库',
        'buy.receipt.return': '采购退货',
        'sell.delivery.sell': '销售出库',
        'sell.delivery.return': '销售退货',
    }

    @api.depends('goods_qty', 'price_taxed', 'discount_amount', 'tax_rate')
    def _compute_all_amount(self):
        '''当订单行的数量、含税单价、折扣额、税率改变时，改变金额、税额、价税合计'''
        for wml in self:
            if wml.tax_rate > 100:
                raise UserError('税率不能输入超过100的数')
            if wml.tax_rate < 0:
                raise UserError('税率不能输入负数')
            wml.subtotal = wml.price_taxed * wml.goods_qty - wml.discount_amount  # 价税合计
            wml.tax_amount = wml.subtotal / \
                (100 + wml.tax_rate) * wml.tax_rate  # 税额
            wml.amount = wml.subtotal - wml.tax_amount  # 金额

    @api.onchange('price', 'tax_rate')
    def onchange_price(self):
        if not self.goods_id:
            return
        '''当订单行的不含税单价改变时，改变含税单价'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)  # 不含税单价
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price_taxed = self.price * (1 + self.tax_rate * 0.01)

    @api.depends('goods_id')
    def _compute_using_attribute(self):
        for wml in self:
            wml.using_attribute = wml.goods_id.attribute_ids and True or False

    @api.depends('move_id.warehouse_id')
    def _get_line_warehouse(self):
        for wml in self:
            wml.warehouse_id = wml.move_id.warehouse_id.id
            if (wml.move_id.origin in ('wh.assembly', 'wh.disassembly', 'outsource')) and wml.type == 'in':
                wml.warehouse_id = self.env.ref(
                    'warehouse.warehouse_production').id

    @api.depends('move_id.warehouse_dest_id')
    def _get_line_warehouse_dest(self):
        for wml in self:
            wml.warehouse_dest_id = wml.move_id.warehouse_dest_id.id
            if (wml.move_id.origin in ('wh.assembly', 'wh.disassembly', 'outsource')) and wml.type == 'out':
                wml.warehouse_dest_id = self.env.ref(
                    'warehouse.warehouse_production').id

    @api.depends('goods_id')
    def _compute_uom_uos(self):
        for wml in self:
            if wml.goods_id:
                wml.uom_id = wml.goods_id.uom_id
                wml.uos_id = wml.goods_id.uos_id

    @api.depends('goods_qty', 'goods_id')
    def _get_goods_uos_qty(self):
        for wml in self:
            if wml.goods_id and wml.goods_qty:
                wml.goods_uos_qty = wml.goods_qty / wml.goods_id.conversion
            else:
                wml.goods_uos_qty = 0

    def _inverse_goods_qty(self):
        for wml in self:
            wml.goods_qty = wml.goods_uos_qty * wml.goods_id.conversion

    @api.depends('goods_id', 'goods_qty')
    def compute_line_net_weight(self):
        for move_line in self:
            move_line.line_net_weight = move_line.goods_id.net_weight * move_line.goods_qty

    move_id = fields.Many2one('wh.move', string='移库单', ondelete='cascade',
                              help='出库/入库/移库单行对应的移库单')
    partner_id = fields.Many2one('partner',string='业务伙伴',related='move_id.partner_id',store=True)
    plan_date = fields.Date('计划日期', default=fields.Date.context_today)
    date = fields.Date('完成日期', copy=False,
                       help='单据完成日期')
    cost_time = fields.Datetime('确认时间', copy=False,
                                help='单据确认时间')
    type = fields.Selection(MOVE_LINE_TYPE,
                            '类型',
                            required=True,
                            default=lambda self: self.env.context.get('type'),
                            help='类型：出库、入库 或者 内部调拨')
    state = fields.Selection(MOVE_LINE_STATE, '状态', copy=False, default='draft',
                             index=True,
                             help='状态标识，新建时状态为草稿;确认后状态为已完成')
    goods_id = fields.Many2one('goods', string='商品', required=True,
                               index=True, ondelete='restrict',
                               help='该单据行对应的商品')
    using_attribute = fields.Boolean(compute='_compute_using_attribute', string='使用属性',
                                     help='该单据行对应的商品是否存在属性，存在True否则False')
    attribute_id = fields.Many2one('attribute', '属性', ondelete='restrict', index=True, 
                                   help='该单据行对应的商品的属性')
    designator = fields.Char('位号')
    using_batch = fields.Boolean(related='goods_id.using_batch', string='批号管理',
                                 readonly=True,
                                 help='该单据行对应的商品是否使用批号管理')
    force_batch_one = fields.Boolean(related='goods_id.force_batch_one', string='每批号数量为1',
                                     readonly=True,
                                     help='该单据行对应的商品是否每批号数量为1,是True否则False')
    lot = fields.Char('入库批号',
                      help='该单据行对应的商品的批号，一般是入库单行')
    lot_id = fields.Many2one('wh.move.line', '批号',
                             domain="[('goods_id', '=', goods_id), ('state', '=', 'done'), ('lot', '!=', False), "
                                    "('qty_remaining', '>', 0), ('warehouse_dest_id', '=', warehouse_id)]",
                             help='该单据行对应的商品的批号，一般是出库单行')
    lot_qty = fields.Float(related='lot_id.qty_remaining', string='批号数量',
                           digits='Quantity',
                           help='该单据行对应的商品批号的商品剩余数量')
    lot_uos_qty = fields.Float('批号辅助数量',
                               digits='Quantity',
                               help='该单据行对应的商品的批号辅助数量')
    location_id = fields.Many2one('location', ondelete='restrict', string='库位', index=True)
    production_date = fields.Date('生产日期', default=fields.Date.context_today,
                                  help='商品的生产日期')
    shelf_life = fields.Integer('保质期(天)',
                                help='商品的保质期(天)')
    uom_id = fields.Many2one('uom', string='单位', ondelete='restrict', compute=_compute_uom_uos,
                             help='商品的计量单位', store=True)
    uos_id = fields.Many2one('uom', string='辅助单位', ondelete='restrict', compute=_compute_uom_uos,
                             readonly=True,  help='商品的辅助单位', store=True)
    warehouse_id = fields.Many2one('warehouse', '调出仓库',
                                   ondelete='restrict',
                                   store=True,
                                   index=True,
                                   compute=_get_line_warehouse,
                                   help='单据的来源仓库')
    warehouse_dest_id = fields.Many2one('warehouse', '调入仓库',
                                        ondelete='restrict',
                                        store=True,
                                        index=True,
                                        compute=_get_line_warehouse_dest,
                                        help='单据的目的仓库')
    goods_qty = fields.Float('数量',
                             digits='Quantity',
                             default=1,
                             required=True,
                             help='商品的数量')
    all_lack = fields.Float('缺货数量', digits='Quantity', compute="_get_lack")
    wh_lack = fields.Float('本仓缺货', digits='Quantity', compute="_get_lack")
    goods_uos_qty = fields.Float('辅助数量', digits='Quantity',
                                 compute=_get_goods_uos_qty, inverse=_inverse_goods_qty, store=True,
                                 help='商品的辅助数量')

    price = fields.Float('单价',
                         store=True,
                         digits='Price',
                         help='商品的单价')
    price_taxed = fields.Float('含税单价',
                               digits='Price',
                               help='商品的含税单价')
    discount_rate = fields.Float('折扣率%',
                                 help='单据的折扣率%')
    discount_amount = fields.Float('折扣额',
                                   digits='Amount',
                                   help='单据的折扣额')
    amount = fields.Float('金额', compute=_compute_all_amount, store=True,
                          digits='Amount',
                          help='单据的金额,计算得来')
    tax_rate = fields.Float('税率(%)',
                            help='单据的税率(%)')
    tax_amount = fields.Float('税额', compute=_compute_all_amount, store=True,
                              digits='Amount',
                              help='单据的税额,有单价×数量×税率计算得来')
    subtotal = fields.Float('价税合计', compute=_compute_all_amount, store=True,
                            digits='Amount',
                            help='价税合计,有不含税金额+税额计算得来')
    note = fields.Text('备注',
                       help='可以为该单据添加一些需要的标识信息')
    cost_unit = fields.Float('单位成本', digits='Price',
                             help='入库/出库单位成本')
    cost = fields.Float('成本', compute='_compute_cost', inverse='_inverse_cost',
                        digits='Amount', store=True,
                        help='入库/出库成本')
    line_net_weight = fields.Float(
        string='净重小计', digits='Weight', compute=compute_line_net_weight, store=True)
    expiration_date = fields.Date('过保日',
                                  help='商品保质期截止日期')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    scrap = fields.Boolean('报废')
    share_cost = fields.Float('采购费用',
                              digits='Amount',
                              help='点击分摊按钮或确认时将采购费用进行分摊得出的费用')

    @api.model
    def create(self, vals):
        new_id = super(WhMoveLine, self).create(vals)
        # 只针对入库单行
        if new_id.type != 'out' and not new_id.location_id and new_id.warehouse_dest_id:
            # 有库存的产品
            qty_now = self.move_id.check_goods_qty(
                new_id.goods_id, new_id.attribute_id, new_id.warehouse_dest_id)[0]
            if qty_now:
                # 建议将产品上架到现有库位上
                new_id.location_id = new_id.env['location'].search([('goods_id', '=', new_id.goods_id.id),
                                                                    ('attribute_id', '=',
                                                                     new_id.attribute_id and new_id.attribute_id.id or False),
                                                                    ('warehouse_id', '=', new_id.warehouse_dest_id.id)],
                                                                   limit=1)
        return new_id

    @api.depends('cost_unit', 'price', 'goods_qty', 'discount_amount', 'share_cost')
    def _compute_cost(self):
        for wml in self:
            wml.cost = 0
            if wml.env.context.get('type') == 'in' and wml.goods_id:
                if wml.price:       #按采购价记成本
                    wml.cost = wml.price * wml.goods_qty - wml.discount_amount + wml.share_cost
                elif wml.cost_unit: # 按出库成本退货
                    wml.cost = wml.cost_unit * wml.goods_qty - wml.discount_amount + wml.share_cost
            elif wml.cost_unit:
                wml.cost = wml.cost_unit * wml.goods_qty

    def _inverse_cost(self):
        for wml in self:
            wml.cost_unit = safe_division(wml.cost, wml.goods_qty)

    def get_origin_explain(self):
        self.ensure_one()
        if self.move_id.origin in ('wh.assembly', 'wh.disassembly'):
            return self.ORIGIN_EXPLAIN.get((self.move_id.origin, self.type))
        elif self.move_id.origin == 'wh.internal':
            return self.ORIGIN_EXPLAIN.get((self.move_id.origin, self.env.context.get('internal_out', False)))
        elif self.move_id.origin in self.ORIGIN_EXPLAIN.keys():
            return self.ORIGIN_EXPLAIN.get(self.move_id.origin)

        return ''

    @api.model
    def default_get(self, fields):
        res = super(WhMoveLine, self).default_get(fields)
        if self.env.context.get('goods_id') and self.env.context.get('warehouse_id'):
            res.update({
                'goods_id': self.env.context.get('goods_id'),
                'warehouse_id': self.env.context.get('warehouse_id')
            })

        return res

    def get_real_cost_unit(self):
        self.ensure_one()
        return safe_division(self.cost, self.goods_qty)

    
    def name_get(self):
        res = []
        for line in self:
            if self.env.context.get('match'):
                res.append((line.id, '%s-%s->%s(%s, %s%s)' %
                            (line.move_id.name, line.warehouse_id.name, line.warehouse_dest_id.name,
                             line.goods_id.name, str(line.goods_qty), line.uom_id.name)))
            else:
                res.append((line.id, line.lot))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        ''' 批号下拉的时候显示批次和剩余数量 '''
        result = []
        domain = []
        if args:
            domain = args
        if name:
            domain.append(('lot', operator, name))
        records = self.search(domain, limit=limit)
        for line in records:
            if line.expiration_date:
                result.append((line.id, '%s %s 余 %s 过保日 %s' % (
                    line.lot, line.warehouse_dest_id.name, line.qty_remaining, line.expiration_date)))
            else:
                result.append((line.id, '%s %s 余 %s' % (
                    line.lot, line.warehouse_dest_id.name, line.qty_remaining)))
        return result

    def check_availability(self):
        if self.warehouse_dest_id == self.warehouse_id:
            # 如果是 商品库位转移生成的内部移库，则不用约束调入仓和调出仓是否相同；否则需要约束
            if not (self.move_id.origin == 'wh.internal' and not self.location_id == False):
                raise UserError('调出仓库不可以和调入仓库一样')
        # 检查属性或批号是否填充，防止无权限人员不填就可以保存
        if self.using_attribute and not self.attribute_id:
            raise UserError('请输入商品：%s 的属性' % self.goods_id.name)
        if self.using_batch:
            if self.type == 'in' and not self.lot:
                raise UserError('请输入商品：%s 的批号' % self.goods_id.name)
            if self.type in ['out', 'internal'] and not self.lot_id:
                raise UserError('请选择商品：%s 的批号' % self.goods_id.name)

    def prev_action_done(self):
        pass

    
    def action_done(self):
        for line in self:
            _logger.info('正在确认ID为%s的移库行' % line.id)
            line.check_availability()
            line.prev_action_done()
            line.write({
                'state': 'done',
                'date': line.move_id.date,
                'cost_time': fields.Datetime.now(self),
            })
            if line.type in ('in', 'internal'):
                locations = self.env['location'].search([('warehouse_id', '=', line.warehouse_dest_id.id)])
                if locations and not line.location_id:
                    raise UserError('调入仓库 %s 进行了库位管理，请在明细行输入库位' % line.warehouse_dest_id.name)
                if line.location_id:
                    line.location_id.write(
                        {'attribute_id': line.attribute_id.id, 'goods_id': line.goods_id.id})

            if line.type == 'in' and line.scrap:
                if not self.env.user.company_id.wh_scrap_id:
                    raise UserError('请在公司上输入废品库')
                dic = {
                    'type': 'internal',
                    'goods_id': line.goods_id.id,
                    'uom_id': line.uom_id.id,
                    'attribute_id': line.attribute_id.id,
                    'goods_qty': line.goods_qty,
                    'warehouse_id': line.warehouse_dest_id.id,
                    'warehouse_dest_id': self.env.user.company_id.wh_scrap_id.id
                }
                if line.lot:
                    dic.update({'lot_id': line.id})
                wh_internal = self.env['wh.internal'].search([('ref', '=', line.move_id.name)])
                if not wh_internal:
                    value = {
                        'ref': line.move_id.name,
                        'date': fields.Datetime.now(self),
                        'warehouse_id': line.warehouse_dest_id.id,
                        'warehouse_dest_id': self.env.user.company_id.wh_scrap_id.id,
                        'line_out_ids': [(0, 0, dic)],
                    }
                    self.env['wh.internal'].create(value)
                else:
                    dic['move_id'] = wh_internal.move_id.id
                    self.env['wh.move.line'].create(dic)

    def check_cancel(self):
        pass

    def prev_action_draft(self):
        pass

    def action_draft(self):
        for line in self:
            line.check_cancel()
            line.prev_action_draft()
            line.write({
                'state': 'draft',
                'date': False,
            })

    def compute_lot_compatible(self):
        for wml in self:
            if wml.warehouse_id and wml.lot_id and wml.lot_id.warehouse_dest_id != wml.warehouse_id:
                wml.lot_id = False

            if wml.goods_id and wml.lot_id and wml.lot_id.goods_id != wml.goods_id:
                wml.lot_id = False

    def compute_lot_domain(self):
        warehouse_id = self.env.context.get('default_warehouse_id')
        lot_domain = [('goods_id', '=', self.goods_id.id), ('state', '=', 'done'),
                      ('lot', '!=', False), ('qty_remaining', '>', 0),
                      ('warehouse_dest_id.type', '=', 'stock')]

        if warehouse_id:
            lot_domain.append(('warehouse_dest_id', '=', warehouse_id))

        if self.attribute_id:
            lot_domain.append(('attribute_id', '=', self.attribute_id.id))

        return lot_domain

    def compute_suggested_cost(self):
        for wml in self:
            if wml.env.context.get('type') == 'out' and wml.goods_id and wml.warehouse_id and wml.goods_qty:
                _, cost_unit = wml.goods_id.get_suggested_cost_by_warehouse(
                    wml.warehouse_id, wml.goods_qty, wml.lot_id, wml.attribute_id)

                wml.cost_unit = cost_unit

            if wml.env.context.get('type') == 'in' and wml.goods_id:
                wml.cost_unit = wml.goods_id.cost

    
    @api.onchange('goods_id')
    def onchange_goods_id(self):
        if self.goods_id:
            self.uom_id = self.goods_id.uom_id
            self.uos_id = self.goods_id.uos_id
            self.attribute_id = False

            partner_id = self.env.context.get('default_partner')
            partner = self.env['partner'].browse(partner_id)
            if self.type == 'in':
                self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, partner, 'buy')
            if self.type == 'out':
                self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, partner, 'sell')

            if self.goods_id.using_batch and self.goods_id.force_batch_one:
                self.goods_qty = 1
                self.goods_uos_qty = self.goods_id.anti_conversion_unit(
                    self.goods_qty)
            else:
                self.goods_qty = self.goods_id.conversion_unit(
                    self.goods_uos_qty or 1)
        else:
            return

        self.compute_suggested_cost()
        self.compute_lot_compatible()

        return {'domain': {'lot_id': self.compute_lot_domain()}}

    
    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        if not self.warehouse_id:
            return
        self.compute_suggested_cost()
        self.compute_lot_domain()
        self.compute_lot_compatible()

        return {'domain': {'lot_id': self.compute_lot_domain()}}

    
    @api.onchange('attribute_id')
    def onchange_attribute_id(self):
        if not self.attribute_id:
            return
        self.compute_suggested_cost()
        return {'domain': {'lot_id': self.compute_lot_domain()}}

    @api.onchange('goods_qty')
    def onchange_goods_qty(self):
        if not self.goods_id:
            return
        self.compute_suggested_cost()

    @api.onchange('goods_uos_qty')
    def onchange_goods_uos_qty(self):
        if self.goods_id:
            self.goods_qty = self.goods_id.conversion_unit(self.goods_uos_qty)
            self.compute_suggested_cost()

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        if self.lot_id:
            if self.lot_id.qty_remaining < self.goods_qty:
                self.goods_qty = self.lot_id.qty_remaining
            self.lot_qty = self.lot_id.qty_remaining
            self.lot_uos_qty = self.goods_id.anti_conversion_unit(self.lot_qty)

            if self.env.context.get('type') in ['internal', 'out']:
                self.lot = self.lot_id.lot

    @api.onchange('goods_qty', 'price_taxed', 'discount_rate')
    def onchange_discount_rate(self):
        if not self.goods_id:
            return
        """当数量、单价或优惠率发生变化时，优惠金额发生变化"""
        price = self.price_taxed / (1 + self.tax_rate * 0.01)
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price = price
        self.discount_amount = self.goods_qty * self.price * self.discount_rate * 0.01

    
    @api.onchange('discount_amount')
    def onchange_discount_amount(self):
        if not self.goods_id:
            return
        """当优惠金额发生变化时，重新取默认的单位成本，以便计算实际的单位成本"""
        self.compute_suggested_cost()

    @api.constrains('goods_qty')
    def check_goods_qty(self):
        """序列号管理的商品数量必须为1"""
        for wml in self:
            if wml.force_batch_one and wml.goods_qty > 1:
                raise UserError('商品 %s 进行了序列号管理，数量必须为1' % wml.goods_id.name)

    def get_lot_id(self):
        if self.type == 'out' and self.goods_id.using_batch:
            domain = [
                ('qty_remaining', '>=', self.goods_qty),
                ('state', '=', 'done'),
                ('warehouse_dest_id', '=', self.warehouse_id.id),
                ('goods_id', '=', self.goods_id.id)
            ]

            line = self.env['wh.move.line'].search(
                domain, order='location_id, expiration_date, cost_time, id',limit=1)
            if line:
                self.lot_id = line.id
                self.lot = line.lot
            else:
                print('not lot for %s in %s' % (self.goods_id.name, self.move_id.name))

    @api.depends('goods_id', 'goods_qty', 'warehouse_id', 'state')
    def _get_lack(self):
        for s in self:
            s.all_lack = 0
            s.wh_lack = 0
            if s.type != 'in' and s.state == 'draft' and s.goods_id:
                s.all_lack = s.goods_qty
                s.wh_lack = s.goods_qty
                qty = s.goods_id.get_stock_qty()
                for i in qty:
                    s.all_lack -= i['qty']
                    if i['warehouse'] == s.warehouse_id.name:
                        s.wh_lack -= i['qty']
