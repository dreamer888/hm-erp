# -*- coding: utf-8 -*-
# Copyright 2018 唤梦科技 ((http://www.dreammm.net).)

{
    'name': 'hmERP 招聘问卷',
    'version': '13.0.1.0',
    'author': '唤梦科技',
    'website': 'http://www.dreammm.net',
    'category': 'hmERP',
    'summary': '招聘问卷',
    'description': """在招聘流程中使用问卷表格""",
    'depends': [
        'staff_hire', 'survey',
    ],
    'data': [
        'views/hire_applicant_view.xml',
        'views/staff_job_view.xml',
    ],
    'demo': ['tests/demo.xml',

    ],
    'installable': True,
    'application': False,
}
