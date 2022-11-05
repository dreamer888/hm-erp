from odoo import api, fields, models


class Partner(models.Model):
    '''
    业务伙伴可能是客户： c_category_id 非空

    '''
    _inherit = 'partner'

    tax_catagory = fields.Selection([('pt', '增值税普通发票'),
                                     ('zy', '增值税专用发票')], '发票类型', default='zy')
