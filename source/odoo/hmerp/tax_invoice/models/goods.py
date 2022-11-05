
from odoo import api, fields, models

class Goods(models.Model):
    """
    继承了core里面定义的goods 模块，增加税收分类编码，并定义了视图和添加字段。
    """
    _inherit = 'goods'

    tax_catagory = fields.Char(string = '发票税收分类编码')
