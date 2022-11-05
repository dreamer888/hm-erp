# -*- coding: utf-8 -*-
# Copyright 2018 唤梦科技 ((http://www.dreammm.net).)

{
    'name': 'hmERP 招聘',
    'version': '11.11',
    'author': '唤梦科技',
    'website': 'http://www.dreammm.net',
    'category': 'hmERP',
    'summary': '员工招聘，工作申请，求职',
    'description': """管理招聘流程""",
    'depends': [
        'staff', 'calendar',
    ],
    # always loaded
    'data': [
        'report/hire_report_view.xml',
        'views/staff_job_view.xml',
        'security/ir.model.access.csv',
        'data/hire_data.xml',
        'views/hire_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'tests/demo.xml',
    ],
    'installable': True,
    'application': False,
}
