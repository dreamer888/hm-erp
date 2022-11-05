#   This file is part of hmERP
{
    'name': 'Web Stock Query',
    'version': '13.0.0.1',
    "author": "朱正翔, 胡巍",
    "website": "http://www.dreammm.net",
    'category': 'Technical Settings',
    'depends': ['warehouse'],
    'data': [
        'views/assets_backend.xml',
    ],
    'description':
    """
        全局范围右上角中添加一个快速搜索框，快速查看对应商品数量余额，并可直接打开所有商品的余额表
    """,
    'qweb': [
        'static/src/xml/query.xml',
    ],
}
