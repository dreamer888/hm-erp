# 清单管理
{
    'name': '拣货单和打包',
    'version': '13.0',
    'author': "唤梦科技",
    'summary': '小件快递发货，按拣货单拣货，按面单复核',
    'category': 'hmERP',
    'description':
    '''
        拣货单的生成
        打印,删除,及货物的打包.
    ''',
    'data': [
         'security/ir.model.access.csv',
         'report/report.xml',
         'views/wave.xml',
         'views/express_menu.xml',
    ],
    'depends': ['warehouse', 'sell'],
    'qweb': [
        'static/src/xml/*.xml',
    ],

}
