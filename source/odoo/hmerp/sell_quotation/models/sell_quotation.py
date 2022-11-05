
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import float_compare

# 销售订单确认状态可选值
SELL_QUOTATION_STATES = [
    ('draft', '草稿'),
    ('submit','待审批'),
    ('done', '已审批'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class SellQuotation(models.Model):
    _name = 'sell.quotation'
    _inherit = ['mail.thread']
    _description = '报价单'
    _order = "date desc"

    name = fields.Char('报价单编号',
                       index=True,
                       copy=False,
                       default='/')
    partner_id = fields.Many2one('partner',
                                 string='客户',
                                 required=True,
                                 ondelete='restrict',
                                 states = READONLY_STATES)
    partner_address_id = fields.Many2one('partner.address',
                                         ondelete='restrict',
                                         string='联系地址',
                                         states=READONLY_STATES)
    contact = fields.Char('联系人',
                          states=READONLY_STATES)
    mobile = fields.Char('电话',
                         states=READONLY_STATES)
    user_id = fields.Many2one('res.users',
                              ondelete='restrict',
                              string='销售员',
                              default=lambda self: self.env.user,
                              states=READONLY_STATES,
                              required=True)
    date = fields.Date('报价日期',
                       states=READONLY_STATES,
                       required=True,
                       copy=False,
                       default=lambda self: fields.Date.context_today(self))
    opportunity_id = fields.Many2one('opportunity',
                                     ondelete='restrict',
                                     string='商机',
                                     domain="[('partner_id','=',partner_id)]",
                                     states=READONLY_STATES)
    pay_method = fields.Many2one('pay.method',string='付款方式',ondelete='restrict')
    validate_to = fields.Char('报价有效期',
                              states=READONLY_STATES,
                              default='此报价自即日生效，如有新报价，老报价自动失效')


    line_ids = fields.One2many('sell.quotation.line',
                               'quotation_id',
                               string='明细行',
                               states=READONLY_STATES)
    state = fields.Selection(SELL_QUOTATION_STATES,
                             string='确认状态',
                             index=True,
                             copy=False,
                             default='draft')
    note = fields.Text('备注')
    term_id = fields.Many2one('core.value', "贸易条款",
                              domain=[('type', '=', 'price_term')],
                              context={'type': 'price_term'},
                              states=READONLY_STATES,
                              )
    pol = fields.Char('起运港', states=READONLY_STATES)
    pod = fields.Char('目的港', states=READONLY_STATES)

    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    
    # 用于在列表上按商品筛选
    goods_id = fields.Many2one('goods',
                               string='商品',
                               related="line_ids.goods_id",
                               readonly=True)

    details = fields.Html('明细',compute='_compute_details')

    @api.depends('line_ids')
    def _compute_details(self):
        for v in self:
            vl = {'col':[],'val':[]}
            vl['col'] = ['商品','报价']
            for l in v.line_ids:
                vl['val'].append([l.goods_id.name,l.price])
            v.details = v.company_id._get_html_table(vl)

    @api.onchange('partner_address_id')
    def onchange_partner_address_id(self):
        ''' 选择联系人，填充电话 '''
        if self.partner_address_id:
            self.contact = self.partner_address_id.contact
            self.mobile = self.partner_address_id.mobile

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        ''' 选择客户带出其默认联系地址、联系人、电话信息 '''
        if self.partner_id:
            self.contact = self.partner_id.contact
            self.mobile = self.partner_id.mobile
            self.pay_method = self.partner_id.pay_method

            for child in self.partner_id.child_ids:
                if child.is_default_add:
                    self.partner_address_id = child.id
            if self.partner_id.child_ids and not any([child.is_default_add for child in self.partner_id.child_ids]):
                partners_add = self.env['partner.address'].search(
                    [('partner_id', '=', self.partner_id.id)], order='id')
                self.partner_address_id = partners_add[0].id

            address_list = [
                child_list.id for child_list in self.partner_id.child_ids]
            if address_list:
                return {'domain': {'partner_address_id': [('id', 'in', address_list)]}}
            else:
                self.partner_address_id = False

    def sell_quotation_done(self):
        ''' 确认报价单 '''
        for quotation in self:
            if quotation.state == 'done':
                raise UserError('请不要重复确认！')
            if not quotation.line_ids:
                raise UserError('请输入明细行！')

            quotation.state = 'done'

    def sell_quotation_draft(self):
        ''' 拒绝报价单 '''
        for quotation in self:
            if quotation.state == 'draft':
                raise UserError('请不要重复拒绝！')

            quotation.state = 'draft'

    def check_ignore_approve(self):
        '''
        所有报价行
        报价高于前一次报价无需审批
        无前一次报价且报价高于商品上的销售价则无需审批
        '''
        need_approve = False
        for l in self.line_ids:
            last_quot = self.env['sell.quotation.line'].search([('goods_id', '=', l.goods_id.id),
                                                          ('partner_id', '=', self.partner_id.id),
                                                          ('state', '=', 'done'),
                                                          ('id', '<', l.id)],
                                                         limit=1,
                                                         order='date desc')
            if last_quot:
                if l.price < last_quot.price:
                    need_approve = True
                    break
            else:
                if l.price < l.goods_id.price:
                    need_approve = True
                    break
        if not need_approve:
            self.sell_quotation_done()

    def sell_quotation_submit(self):
        ''' 报价单提交审批 '''
        for quotation in self:
            if quotation.state == 'submit':
                raise UserError('请不要重复提交！')
            quotation.state = 'submit'
            quotation.check_ignore_approve()
    
    def sell_quotation_cancel(self):
        ''' 作废报价单 '''
        for quotation in self:
            if quotation.state == 'cancel':
                raise UserError('请不要重复提交！')

            quotation.state = 'cancel'


class SellQuotationLine(models.Model):
    _name = 'sell.quotation.line'
    _description = '报价单行'

    quotation_id = fields.Many2one('sell.quotation',
                                   string='报价单',
                                   required=True,
                                   ondelete='cascade')
    partner_id = fields.Many2one('partner',
                                 related='quotation_id.partner_id',
                                 string='客户',
                                 readonly=1,
                                 store=True)
    date = fields.Date(string='生效日期',
                       related='quotation_id.date',
                       readonly=1,
                       store=True)
    state = fields.Selection(related='quotation_id.state',
                             string='确认状态',
                             readonly=1)
    goods_id = fields.Many2one('goods',
                               string='商品',
                               required=True)
    c_code = fields.Char('客户品号')
    c_name = fields.Char('客户品名')
    lead_time = fields.Char('备货周期')
    price = fields.Float('报价(不含税)', digits='Price')
    tax_rate = fields.Float('税率(%)')
    price_taxed = fields.Float('含税单价', digits='Price')
    qty = fields.Float('起订量', digits='Quantity')
    uom_id = fields.Many2one('uom',
                             ondelete='restrict',
                             string='计量单位',
                             required=True)

    @api.onchange('goods_id')
    def onchange_goods_id(self):
        ''' 当订单行的商品变化时，带出商品上的计量单位、含税价 '''
        if self.goods_id:
            self.uom_id = self.goods_id.uom_id
            # 报价单行单价取之前确认的报价单
            last_quo = self.search([('goods_id', '=', self.goods_id.id),
                                    ('partner_id', '=', self.quotation_id.partner_id.id),
                                    ('state', '=', 'done')], order='date desc', limit=1)
            self.price = last_quo and last_quo.price or self.goods_id.price
            self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, self.quotation_id.partner_id, 'sell')
            self.c_code = last_quo and last_quo.c_code or ''
            self.c_name = last_quo and last_quo.c_name or ''
            self.lead_time = self.goods_id.sell_lead_time
    
    @api.onchange('price', 'tax_rate')
    def onchange_price(self):
        """当不含税单价或税率变化，联动含税单价"""
        if self.price or self.tax_rate:
            price = self.price_taxed / (1 + self.tax_rate * 0.01)  # 不含税单价
            decimal = self.env.ref('core.decimal_price')
            if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
                self.price_taxed = self.price * (1 + self.tax_rate * 0.01)
    
    @api.onchange('price_taxed', 'tax_rate')
    def onchange_discount_rate(self):
        """当含税单价或税率变化，联动未税单价"""
        if self.price_taxed or self.tax_rate:
            price = self.price * (1 + self.tax_rate * 0.01)  # 含税单价
            decimal = self.env.ref('core.decimal_price')
            if float_compare(price, self.price_taxed, precision_digits=decimal.digits) != 0:
                self.price = self.price_taxed / (1 + self.tax_rate * 0.01)


class SellOrderLine(models.Model):
    _inherit = 'sell.order.line'

    quotation_line_id = fields.Many2one('sell.quotation.line', string='报价单行')

    price = fields.Float('未税单价',
                               digits='Price',
                               store=True,
                               related='quotation_line_id.price',
                               help='含税单价，取商品零售价')
    quantity = fields.Float('数量',
                            default=0,
                            required=True,
                            digits='Quantity',
                            help='下单数量')

    @api.onchange('quantity')
    def onchange_quantity(self):
        ''' 当订单行的商品变化时，带出报价单 '''
        if self.quantity:
            rec = self.env['sell.quotation.line'].search([('goods_id', '=', self.goods_id.id),
                                                          ('partner_id', '=', self.order_id.partner_id.id),
                                                          ('state', '=', 'done'),
                                                          ('qty', '<=', self.quantity)],
                                                         order='date desc, write_date desc, qty desc')
            self.quotation_line_id = False
            if not rec:
                raise UserError('客户%s商品%s不存在已确认的起订量低于%s的报价单！' % (self.order_id.partner_id.name, self.goods_id.name, self.quantity))

            if rec:
                self.quotation_line_id = rec[0].id
                self.onchange_price()


class SellOrder(models.Model):
    _inherit = 'sell.order'

    def sell_order_done(self):
        rec = self.line_ids[0].quotation_line_id
        self.term_id = rec.quotation_id.term_id
        self.pol = rec.quotation_id.pol
        self.pod = rec.quotation_id.pod
        return super().sell_order_done()
