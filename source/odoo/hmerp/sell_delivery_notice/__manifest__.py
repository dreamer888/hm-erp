
{
    'name': "hmERP 发货通知单模块",

    'summary': """发货通知单""",

    'description': """通知客户安排发货""",

    'author': "Jason Zou",
    'website': "http://www.dreammm.net",

    'category': 'hmERP',
    'version': '13.0.1.0',
    

    'depends': ['sell'],
 
    'data': [
        'security/ir.model.access.csv',
        'views/delivery_notice_views.xml',
    ],
}
