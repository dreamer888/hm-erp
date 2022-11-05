{
    'name': "hmERP 销售报价模块",
    'author': "唤梦科技",
    'website': "http://www.dreammm.net",
    'category': 'hmERP',
    'summary': 'hmERP报价单',
    "description":
    '''
                        该模块实现了 hmERP 给客户报价的功能。
    ''',
    'version': '11.11',
    'application': True,
    'depends': ['sell','good_crm'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/sell_quotation_view.xml',
        'data/sell_quotation_data.xml',
        'report/report_data.xml',
    ],
    'demo': [
        'data/demo.xml',
    ]
}
