{
    'name': "hmERP 核心模块",
    'author': "唤梦科技",
    'summary': '隐藏hm-erp内置技术复杂性，增加基本权限组',
    'website': "http://www.dreammm.net",
    'category': 'hmERP',
    "description":
    '''
                          该模块是 hmERP 的核心模块，完成了基本表的定义和配置。

                           定义了基本类，如 partner,bank_account,goods,staff,uom等；
                           定义了基本配置： 用户、类别等；
                           定义了高级配置： 系统参数、定价策略。
    ''',
    'version': '11.11',
    'depends': ['web',
                'mail',
                'ignore_tree_rng', 
                'common_dialog',
                ],
    'demo': [
        'data/core_demo.xml',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/core_data.xml',
        'views/core_view.xml',
        'views/core_templates.xml',
    ],
    'qweb': [
        'static/src/xml/*.xml',
    ],
}
