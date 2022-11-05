{
    'name': "hmERP 发票管理",
    'author': "永远的不知",
    'website': "https://www.dreammm.net",
    'category': 'hmERP',
    "description":
    '''
    该模块实现发票管理的基础内容。
    ''',
    'version': '13.0.0.1',
    'depends': ['buy', 'sell', 'money'],
    'data': [
        'security/ir.model.access.csv',
        'view/tax_invoice_view.xml',
        'view/partner_view.xml',
        'view/buy_view.xml',
        'view/sell_view.xml',
        'view/money.xml',
        'wizard/wizard_view.xml'
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'post_init_hook': 'set_draft_invoice_hook',
}
