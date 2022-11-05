{
    'name': "hmERP 贸易行业解决方案模块",
    'author': "唤梦科技",
    'website': "http://www.dreammm.net",
    'category': 'hmERP',
    'summary': 'hmERP贸易行业解决方案',
    "description":
    '''
                        该模块实现了 hmERP 按需补货的功能。

                        根据商品的现有库存及最低库存量，结合采购订单、采购入库单、销售订单、销售出库单、其他出入库单等，自动计算出商品的采购订单或者组装单。
    ''',
    'version': '11.11',
    'application': True,
    'depends': ['sell', 'buy', 'asset', 'task'],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_request_data.xml',
        'views/stock_request_view.xml',
    ],
}
