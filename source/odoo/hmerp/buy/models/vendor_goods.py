
from odoo import fields, models



class VendorGoods(models.Model):
    _name = 'vendor.goods'
    _description = '供应商供货价格表'
    _order = 'sequence,date desc,min_qty desc'

    sequence = fields.Integer('优先级')
    goods_id = fields.Many2one(
        string='商品',
        required=True,
        comodel_name='goods',
        ondelete='cascade',
        help='商品',
    )

    vendor_id = fields.Many2one(
        string='供应商',
        required=True,
        comodel_name='partner',
        domain=[('s_category_id', '!=', False)],
        ondelete='cascade',
        help='供应商',
    )

    price = fields.Float('供货价',
                         digits='Price',
                         help='供应商提供的价格')

    code = fields.Char('供应商商品编号',
                       help='供应商提供的商品编号')

    name = fields.Char('供应商商品名称',
                       help='供应商提供的商品名称')

    min_qty = fields.Float('起订量',
                           digits='Quantity',
                           help='采购商品时，大于或等于起订量时，商品的价格才取该行的供货价')
    date = fields.Date('生效日期')
    note = fields.Text('备注')

    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class Partner(models.Model):
    _inherit = 'partner'

    goods_ids = fields.One2many(
        string='供应商品',
        comodel_name='vendor.goods',
        inverse_name='vendor_id',
        help='供应商供应的商品价格列表',
    )


class Goods(models.Model):

    _inherit = 'goods'

    vendor_ids = fields.One2many(
        string='供应价格',
        comodel_name='vendor.goods',
        inverse_name='goods_id',
        help='各供应商提供的基于起订量的供货价格列表',
    )
