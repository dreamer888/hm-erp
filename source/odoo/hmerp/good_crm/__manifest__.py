{
    'name': "hmERP CRM",

    'summary': """
        管理客户跟进过程""",

    'description':
    '''
                        该模块实现了 hmERP 中客户跟进过程管理的功能。
    ''',

    'author': "唤梦科技",
    'website': "http://www.dreammm.net",

    'category': 'hmERP',
    'version': '11.11',

    'depends': ['task'],

    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/crm_view.xml',
        'data/crm_data.xml',
    ],
    'application': True,
}
