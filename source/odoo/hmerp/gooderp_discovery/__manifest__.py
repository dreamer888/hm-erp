{
    'name': 'hmERP洞察',
    'version': '13.0',
    'description': '订阅异常数据并显示报告',
    'summary': '订阅异常数据并显示报告',
    'author': 'jeff@osbzr.com',
    'website': 'http://www.dreammm.net',
    'license': 'AGPL-3',
    'category': 'hmERP',
    'depends': [
        'core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/discovery_channel_view.xml',
        'wizard/discovery_wizard_view.xml',
    ],
    'demo': [
    ],
}
