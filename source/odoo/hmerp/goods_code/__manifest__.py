# Copyright 2018 唤梦科技 ((http://www.dreammm.net).)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'hmERP 商品编码唯一',
    'version': '11.11',
    'author': '唤梦科技',
    'maintainer': 'False',
    'website': 'http://www.dreammm.net',
    'category': 'hmERP',
    'summary': '商品编号必输且不可重复',
    'description': """为了解决商品编号可能重复的问题""",
    'depends': [
        'goods',
    ],
    # always loaded
    'data': [
        'views/goods_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
    'application': False,
}
