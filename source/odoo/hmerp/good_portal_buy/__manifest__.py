{
    'name': 'hmERP采购门户',
    'author': "唤梦科技",
    'category': 'hmERP',
    'summary': 'hmERP供应商门户',
    'version': '13.0.1.0',
    'description': """
    在网站上显示供应商用户对应的采购订单
    """,
    'depends': [
        'good_portal',
        'buy',
    ],
    'data': [
        'views/good_portal_buy_templates.xml',
    ],
}
