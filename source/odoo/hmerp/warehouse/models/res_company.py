from odoo import api, fields, models


class ResCompany(models.Model):
    '''继承公司对象,添加字段'''
    _inherit = 'res.company'

    wh_scrap_id = fields.Many2one('warehouse',
                                  string='废品库')

    @api.model
    def _get_operating_cost_account_id(self):
        return self._get_operating_cost_account_id_impl()

    @api.model
    def _get_operating_cost_account_id_impl(self):
        return self.env.ref('finance.small_business_chart2211001')

    is_enable_negative_stock = fields.Boolean('允许负库存')
    endmonth_generation_cost = fields.Boolean(
        '月末生成出库凭证', help='月末结帐时一次性生成成本凭证')
    operating_cost_account_id = fields.Many2one('finance.account', default=_get_operating_cost_account_id,
                                                ondelete='restrict',
                                                string='生产费用科目', help='用在组装拆卸的费用上!')
    vendor_price_taxed = fields.Boolean('供应商供货价含税')
