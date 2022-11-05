# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'hmERP 培训模块',
    'version': '1.1',
    'website': 'http://www.dreammm.net',
    'category': 'hmERP',
    'sequence': 45,
    'summary': '该模块实现了 hmERP 中人力资源培训管理的功能。',
    'depends': ['mail','web','staff'],
    'description': "该模块实现了 hmERP 中人力资源培训管理的功能。",
    'data': [
        'security/groups_security.xml',
        'security/ir.model.access.csv',
        'views/staff_train_views.xml',
    ],
    'demo': [],
    'qweb': [],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
