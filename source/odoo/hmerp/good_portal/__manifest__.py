{
    'name': 'hmERP门户',
    'author': "唤梦科技",
    'category': 'hmERP',
    'summary': 'hmERP业务伙伴门户',
    'version': '13.0.1.0',
    'description': """
    给客户或供应商的联系人创建用户，以便他们登陆到公司网站查看对应信息。
    """,
    'depends': [
        'website',
        'partner_address',
    ],
    'data': [
        'views/partner_address_view.xml',
        'views/portal_templates.xml',
    ],
}
