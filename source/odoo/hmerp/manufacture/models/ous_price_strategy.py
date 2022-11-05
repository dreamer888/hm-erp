from odoo import fields, api, models
from odoo.exceptions import UserError
import datetime


class OusPriceStrategy(models.Model):
    _name = 'ous.price.strategy'
    _description = '工序委外价格策略'

    @api.depends('goods_id')
    def _compute_using_attribute(self):
        '''返回订单行中商品是否使用属性'''
        for l in self:
            l.using_attribute = l.goods_id.attribute_ids and True or False

    @api.onchange('goods_id')
    def goods_id_onchange(self):
        for l in self:
            if l.goods_id:
                if not l.uom_id:
                    l.uom_id = l.goods_id.uom_id

    @api.onchange('price')
    def price_onchange(self):
        for l in self:
            tax_rate = 0
            if l.goods_id:
                tax_rate = l.goods_id.get_tax_rate(l.goods_id, l.partner_id, 'buy')
            l.price_taxed = l.price * (1 + tax_rate * 0.01)
            
    @api.onchange('price_taxed')
    def price_taxed_onchange(self):
        for l in self:
            tax_rate = 0
            if l.goods_id:
                tax_rate = l.goods_id.get_tax_rate(l.goods_id, l.partner_id, 'buy')
            l.price = l.price_taxed / (1 + tax_rate * 0.01)
    
    @api.depends('bom_id')
    def _compute_mrp_proc_ids(self):
        for l in self:
            l.mrp_proc_ids = []
            if l.bom_id and l.bom_id.line_proc_ids:
                l.mrp_proc_ids = [p for p in l.bom_id.line_proc_ids]
                
    @api.onchange('bom_id')
    def bom_id_onchainge(self):
        for l in self:
            if l.bom_id and (not l.goods_id or l.bom_id.goods_id != l.goods_id):
                l.goods_id = l.bom_id.goods_id
                l.goods_id_onchange()

    def get_partner(self, goods_id, mrp_proc_id, date):
        '''根据规则获取默认供应商'''
        domain = [('goods_id', '=', goods_id.id), ('mrp_proc_id', '=', mrp_proc_id.id), ('start_date', '<=', date), ('enabled', '=', True), ('price', '>', 0)]
        price_ids = self.env['ous.price.strategy'].search(domain)\
                               .filtered(lambda p: not p.end_date or p.end_date >= date)
        min_ids = []
        for l in price_ids:
            if l.start_date == max(l1.start_date for l1 in price_ids.filtered(lambda _l: goods_id.id == l.goods_id.id)):
                min_ids.append(l)
        if min_ids and len([l for l in min_ids]) > 0:
            supplier = sorted(min_ids,key=lambda _l:_l.start_date, reverse = False)[0]
            return supplier.partner_id
        domain = [('goods_id', '=', goods_id.id), ('mrp_proc_id', '=', mrp_proc_id.id), ('state', '=', 'done'), ('price', '>', 0)]
        price_id = sorted(self.env['mrp.plm.ous'].search(domain), key=lambda _l:_l.date, reverse = False)
        if price_id and len(price_id) > 0:
            return price_id[0].partner_id 
        if goods_id and goods_id.supplier_id:
            return goods_id.supplier_id
        return False

    def get_price_id(self, partner_id, goods_id, mrp_proc_id, date):
        '''根据规则获取单价'''
        domain = [('goods_id', '=', goods_id.id), ('mrp_proc_id', '=', mrp_proc_id.id), ('start_date', '<=', date), ('price', '>', 0)]
        if partner_id:
            domain.append(('partner_id', '=', partner_id.id)) 
        price_id = sorted(self.env['ous.price.strategy'].search(domain).filtered(lambda p: not p.end_date or p.end_date >= date),\
                          key=lambda _l:_l.start_date, reverse = False)
        if price_id and len(price_id) > 0:
            return '' , price_id[0]
        if partner_id:
            domain = [('goods_id', '=', goods_id.id), ('mrp_proc_id', '=', mrp_proc_id.id), ('start_date', '<=', date), ('price', '>', 0)]
            price_id = sorted(self.env['ous.price.strategy'].search(domain).filtered(lambda p: not p.end_date or p.end_date >= date),\
                              key=lambda _l:_l.start_date, reverse = False)
            if price_id and len(price_id) > 0:
                return ('供应商 %s 商品 %s 工序 %s 不存在价格策略' % (partner_id.name, goods_id.name, mrp_proc_id.name)) , price_id[0]
        
        domain = [('goods_id', '=', goods_id.id), ('mrp_proc_id', '=', mrp_proc_id.id), ('state', '=', 'done'), ('price', '>', 0)]
        price_id = sorted(self.env['mrp.plm.ous'].search(domain), key=lambda _l:_l.date, reverse = False)
        if price_id and len(price_id) > 0:
            return ('商品 %s 不存在价格策略' % goods_id.name) , price_id[0]
        return ('商品 %s 工序 %s  没有委外并且不存在价格策略' % (goods_id.name, mrp_proc_id.name)), False

    def check_price(self, partner_id, goods_id,date):
        '''根据规则获检测是否有价格策略'''
        price_msg, price_id = self.get_goods_price_id(partner_id, goods_id,date)
        return price_msg

    name = fields.Char('供应商名称', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one('partner', '合作伙伴',
                                 domain="[('s_category_id', '!=', False)]")
    goods_id = fields.Many2one('goods', '商品', required=True)
    attribute_id = fields.Many2one('attribute', '属性',
                                   ondelete='restrict',
                                   domain="[('goods_id', '=', goods_id)]",
                                   help='商品的属性，当商品有属性时，该字段必输')
    using_attribute = fields.Boolean('使用属性', compute=_compute_using_attribute,
                                     help='商品是否使用属性')
    uom_id = fields.Many2one('uom', '单位', required=True)
    qty_start = fields.Float('最小起订量', default=0)
    qty_end = fields.Float('最大起订量', default=0)
    price = fields.Float('单价',digits='Price')
    price_taxed = fields.Float('含税单价',digits='Price')
    discount_rate = fields.Float('折扣率%', help='折扣率')
    start_date = fields.Date('开始日期', required=True, default=lambda self: datetime.datetime.now())
    end_date = fields.Date('结束日期')
    enabled = fields.Boolean('启用', default=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', required=True)
    mrp_proc_ids = fields.Many2many('mrp.proc', compute='_compute_mrp_proc_ids')
    bom_id = fields.Many2one('mrp.bom', 'BOM')