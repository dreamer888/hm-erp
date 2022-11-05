from odoo import fields, models


class ParetnerQualityGrade(models.Model):
    _name = 'partner.quality.grade'
    _description = '供应商品质等级'

    name = fields.Char('名称', required=True)
    grade = fields.Integer('等级值', required=True, default=1, help='用于供应商策略排序规则(升序)')
    remark = fields.Char('备注')