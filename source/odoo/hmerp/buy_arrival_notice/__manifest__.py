
{
    'name': "hmERP 采购到货通知单模块",

    'summary': """采购到货通知单""",

    'description': """
        【采购员】

         在【接到供应商送货通知后】

         需要【创建到货通知单】

         以便【通知仓库本次到货对应的订单和数量】
    """,

    'author': "朱鑫涛",
    'website': "http://www.dreammm.net",

    'category': 'hmERP',
    'version': '13.0.1.0',
    

    'depends': ['buy'],
 
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
}
