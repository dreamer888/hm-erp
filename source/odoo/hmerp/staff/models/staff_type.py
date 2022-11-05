# -*- coding: utf-8 -*-
"""
@Time    : 2020/9/27 12:15
@Author  : Jason Zou
@Email   : zou.jason@qq.com
定义扩展人力资源管理模块员工扩展
"""

from odoo import api, fields, models, _
import datetime
from odoo.exceptions import UserError, ValidationError


# 分类的类别
STAFF_TYPE = [('contract_category', '合同类别'),
            ('confident_agreement', '保密协议类别'),
            ('job_type', '岗位类型'),
            ('social_payment_address', '社保公积金缴纳地点'),
            ('professional_title', '职称'),
            ('graduation_certificate', '证书'),
            ('relationship_one', '关系1'),
            ('relationship_two', '关系2'),
            ('leaving_reason', '离职原因'),
            ('political_outlook', '政治面貌'),
            ('household_type', '户籍类型'),
            ('highest_education', '最高学历'),
            ('major_title', '专业'),
            ('university_graduated', '毕业院校'),
            ('learning_form', '学历性质')]

# 当客户要求下拉字段可编辑，可使用此表存储可选值，按type分类，在字段上用domain和context筛选


class StaffType(models.Model):
    _name = 'staff.type'
    _description = '参数项'
    _order = 'type, serial_number'

    name = fields.Char(string='名称', required=True, )
    type = fields.Selection(STAFF_TYPE, '类型',
                            required=True,
                            readonly=True,
                            default=lambda self: self._context.get('type'))
    serial_number = fields.Integer(string='显示顺序', help='显示顺序按类型+显示顺序进行排序显示.')
    active = fields.Boolean(string='状态', default=True, )

    _sql_constraints = [
        ('name_uniq', 'unique(type, name)', '同类型的类别不能重名')
    ]
