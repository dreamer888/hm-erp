{
    'name': "hmERP HR模块",
    'author': "唤梦科技",
    'website': "http://www.dreammm.net",
    'category': 'hmERP',
    "description":
    '''
                            该模块实现了 hmERP 中人力资源的功能。
    ''',
    'version': '11.11',
    'depends': ['finance'],
    'demo': [
        'tests/staff_demo.xml'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'security/rules.xml',
        'views/staff.xml',
        'views/leave.xml',
        'data/mail_data.xml',
        'data/export_data.xml',
    ],
}
