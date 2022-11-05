from odoo import api, fields, models


class Goods(models.Model):
    _inherit = 'goods'

    buy_qc = fields.Boolean('IQC', default=0, help="勾选后，需采走采购质检流程才能入库")
    mrp_qc = fields.Boolean('IPQC', default=0, help="勾选后，可以走工序质检流程")
    pre_days = fields.Integer('准备天数')

    out_warehouse_id = fields.Many2one('warehouse',
                                       '默认发料库',
                                       ondelete='restrict',
                                       help='生产领料默认从该仓库调出')
    in_warehouse_id = fields.Many2one('warehouse',
                                      '默认仓库',
                                      ondelete='restrict',
                                      help='默认的生产完工入库仓库')
    department_id = fields.Many2one('staff.department',
                                    '默认生产部门',
                                    index=True,
                                    ondelete='cascade')

    """TODO:商品自动编码 for Jackey """
    """
    @api.onchange('')
    def auto_code(self):
        return ''
    """
