# Copyright 2018 唤梦科技 ((http://www.dreammm.net).)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'hmERP Sell To Buy',
    'version': '11.11',
    'author': '唤梦科技',
    'website': 'http://www.dreammm.net',
    'category': 'hmERP',
    'summary': '以销订购',
    'description': """根据销售订单创建采购订单""",
    'depends': [
        'buy', 'sell'
    ],
    'data': [
        'views/buy_view.xml',
        'wizard/sell_to_buy_wizard_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
}
