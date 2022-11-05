
from odoo import fields, models, api

from odoo.exceptions import UserError
from odoo.tools import float_compare

# 订单确认状态可选值
SELL_ORDER_STATES = [
    ('draft', '草稿'),
    ('done', '已确认'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class SellAdjust(models.Model):
    _name = "sell.adjust"
    _inherit = ['mail.thread']
    _description = "销售变更单"
    _order = 'date desc, id desc'

    name = fields.Char('单据编号', copy=False,
                       help='变更单编号，保存时可自动生成')
    order_id = fields.Many2one('sell.order', '原始单据', states=READONLY_STATES,
                               copy=False, ondelete='restrict',
                               help='要调整的原始销售订单，只能调整已确认且没有全部出库的销售订单')
    date = fields.Date('单据日期', states=READONLY_STATES,
                       default=lambda self: fields.Date.context_today(self),
                       index=True, copy=False,
                       help='变更单创建日期，默认是当前日期')
    line_ids = fields.One2many('sell.adjust.line', 'order_id', '变更单行',
                               states=READONLY_STATES, copy=True,
                               help='变更单明细行，不允许为空')
    approve_uid = fields.Many2one('res.users', '确认人',
                                  copy=False, ondelete='restrict',
                                  help='确认变更单的人')
    state = fields.Selection(SELL_ORDER_STATES, '确认状态',
                             index=True, copy=False,
                             default='draft',
                             help='变更单确认状态')
    note = fields.Text('备注',
                       help='单据备注')
    user_id = fields.Many2one(
        'res.users',
        '经办人',
        ondelete='restrict',
        states=READONLY_STATES,
        default=lambda self: self.env.user,
        help='单据经办人',
    )
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    def sell_adjust_done(self):
        '''确认销售变更单：
        当调整后数量 < 原单据中已出库数量，则报错；
        当调整后数量 > 原单据中已出库数量，则更新原单据及发货单分单的数量；
        当调整后数量 = 原单据中已出库数量，则更新原单据数量，删除发货单分单；
        当新增商品时，则更新原单据及发货单分单明细行。
        '''
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认！')
        if not self.line_ids:
            raise UserError('请输入商品明细行！')
        delivery = self.env['sell.delivery'].search(
            [('order_id', '=', self.order_id.id),
             ('state', '=', 'draft')])
        if not delivery:
            raise UserError('销售发货单已全部出库，不能调整')
        for line in self.line_ids:
            # 检查属性是否填充，防止无权限人员不填就可以保存
            if line.using_attribute and not line.attribute_id:
                raise UserError('请输入商品：%s 的属性' % line.goods_id.name)
            origin_line = self.env['sell.order.line'].search(
                [('goods_id', '=', line.goods_id.id),
                 ('attribute_id', '=', line.attribute_id.id),
                 ('order_id', '=', self.order_id.id)])
            if len(origin_line) > 1:
                raise UserError('要调整的商品 %s 在原始单据中不唯一' % line.goods_id.name)
            if origin_line:
                origin_line.quantity += line.quantity  # 调整后数量
                new_note = '变更单：%s %s。\n' % (self.name, line.note)
                origin_line.note = (origin_line.note and
                                    origin_line.note + new_note or new_note)
                if origin_line.quantity < origin_line.quantity_out:
                    raise UserError(' %s 调整后数量不能小于原订单已出库数量' %
                                    line.goods_id.name)
                elif origin_line.quantity > origin_line.quantity_out:
                    # 查找出原销售订单产生的草稿状态的发货单明细行，并更新它
                    move_line = self.env['wh.move.line'].search(
                        [('sell_line_id', '=', origin_line.id),
                         ('state', '=', 'draft')])
                    if move_line:
                        move_line.goods_qty += line.quantity
                    else:
                        raise UserError('商品 %s 已全部入库，建议新建采购订单' %
                                        line.goods_id.name)
                # 调整后数量与已出库数量相等时，删除产生的发货单分单
                else:
                    # 先删除对应的发货单行
                    move_line = self.env['wh.move.line'].search(
                        [('sell_line_id', '=', origin_line.id), ('state', '=',
                                                                 'draft')])
                    if move_line:
                        move_line.unlink()

                    # 如果发货单明细没有了，则删除发货单
                    if len(delivery.sell_move_id.line_out_ids) == 0:
                        delivery.unlink()
            else:
                vals = {
                    'order_id': self.order_id.id,
                    'goods_id': line.goods_id.id,
                    'attribute_id': line.attribute_id.id,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'price_taxed': line.price_taxed,
                    'discount_rate': line.discount_rate,
                    'discount_amount': line.discount_amount,
                    'tax_rate': line.tax_rate,
                    'note': line.note or '',
                }
                new_line = self.env['sell.order.line'].create(vals)
                delivery_line = []
                if line.goods_id.force_batch_one:
                    i = 0
                    while i < line.quantity:
                        i += 1
                        delivery_line.append(
                            self.order_id.get_delivery_line(new_line, single=True))
                else:
                    delivery_line.append(
                        self.order_id.get_delivery_line(new_line, single=False))
                delivery.write(
                    {'line_out_ids': [(0, 0, li) for li in delivery_line]})
        self.state = 'done'
        self.approve_uid = self._uid


class SellAdjustLine(models.Model):
    _name = 'sell.adjust.line'
    _description = '销售变更单明细'

    @api.depends('goods_id')
    def _compute_using_attribute(self):
        '''返回订单行中商品是否使用属性'''
        for l in self:
            l.using_attribute = l.goods_id.attribute_ids and True or False

    @api.depends('quantity', 'price_taxed', 'discount_amount', 'tax_rate')
    def _compute_all_amount(selfs):
        '''当订单行的数量、单价、折扣额、税率改变时，改变采购金额、税额、价税合计'''
        for self in selfs:
            self.subtotal = self.price_taxed * self.quantity - self.discount_amount  # 价税合计
            self.tax_amount = self.subtotal / \
                (100 + self.tax_rate) * self.tax_rate  # 税额
            self.amount = self.subtotal - self.tax_amount  # 金额

    @api.onchange('price', 'tax_rate')
    def onchange_price(self):
        '''当订单行的不含税单价改变时，改变含税单价'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)  # 不含税单价
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price_taxed = self.price * (1 + self.tax_rate * 0.01)

    order_id = fields.Many2one('sell.adjust', '订单编号', index=True,
                               required=True, ondelete='cascade',
                               help='关联的变更单编号')
    goods_id = fields.Many2one('goods', '商品', ondelete='restrict',
                               help='商品')
    using_attribute = fields.Boolean('使用属性', compute=_compute_using_attribute,
                                     help='商品是否使用属性')
    attribute_id = fields.Many2one('attribute', '属性',
                                   ondelete='restrict',
                                   domain="[('goods_id', '=', goods_id)]",
                                   help='商品的属性，当商品有属性时，该字段必输')
    uom_id = fields.Many2one('uom', '单位', ondelete='restrict',
                             help='商品计量单位')
    quantity = fields.Float('调整数量',
                            default=1,
                            required=True,
                            digits='Quantity',
                            help='相对于原单据对应明细行的调整数量，可正可负')
    price = fields.Float('销售单价',
                         store=True,
                         digits='Price',
                         help='不含税单价，由含税单价计算得出')
    price_taxed = fields.Float('含税单价',
                               digits='Price',
                               help='含税单价，取自商品零售价')
    discount_rate = fields.Float('折扣率%',
                                 help='折扣率')
    discount_amount = fields.Float('折扣额',
                                   digits='Amount',
                                   help='输入折扣率后自动计算得出，也可手动输入折扣额')
    amount = fields.Float('金额',
                          compute=_compute_all_amount,
                          store=True,
                          digits='Amount',
                          help='金额  = 价税合计  - 税额')
    tax_rate = fields.Float('税率(%)', default=lambda self: self.env.user.company_id.import_tax_rate,
                            help='默认值取公司销项税率')
    tax_amount = fields.Float('税额',
                              compute=_compute_all_amount,
                              store=True,
                              digits='Amount',
                              help='由税率计算得出')
    subtotal = fields.Float('价税合计',
                            compute=_compute_all_amount,
                            store=True,
                            digits='Amount',
                            help='含税单价 乘以 数量')
    note = fields.Char('备注',
                       help='本行备注')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    @api.onchange('goods_id')
    def onchange_goods_id(self):
        '''当订单行的商品变化时，带出商品上的单位、默认仓库、价格'''
        if self.goods_id:
            self.uom_id = self.goods_id.uom_id
            # 修正 单价 及含税单价问题
            self.price_taxed = self.goods_id.price * (1 + self.goods_id.tax_rate * 0.01) if self.goods_id.tax_rate else self.goods_id.price

            self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, self.order_id.order_id.partner_id, 'sell')

    @api.onchange('quantity', 'price_taxed', 'discount_rate')
    def onchange_discount_rate(self):
        '''当数量、含税单价或优惠率发生变化时，优惠金额发生变化'''
        self.price = self.price_taxed / (1 + self.tax_rate * 0.01)
        self.discount_amount = (self.quantity * self.price *
                                self.discount_rate * 0.01)

    @api.constrains('tax_rate')
    def _check_(self):
        for record in self:
            if record.tax_rate > 100:
                raise UserError('税率不能输入超过100的数')
            if record.tax_rate < 0:
                raise UserError('税率不能输入负数')
            
    
