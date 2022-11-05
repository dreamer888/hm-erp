{
    'name': "hmERP 销售子产品出货模块",
    'author': "唤梦科技",
    'website': "http://www.dreammm.net",
    'category': 'hmERP',
    'summary': 'hmERP组合销售',
    "description":
    '''
                        该模块实现了 hmERP 销售组合产品时自动出货子产品的功能。
    ''',
    'version': '11.11',
    'application': True,
    'depends': ['sell'],
    'data': [
        'views/sell_delivery_parts_view.xml',
    ],
    'demo': [
    ]
}
