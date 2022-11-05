# -*- coding: utf-8 -*-
{
    'name': "hmERP 會計模組-台灣科目",
    'author': "歐度資訊、齊暘資訊 ( JasonWu)",
    'website': "",
    'category': 'Extra',
    "description":
        '''
                此模塊實現 台灣版 小企業 IFRS 會計科目
                用以取代預設的中國會計科目表及相關報表
        ''',
    'depends': ['num_to_china',
                'core',
                'finance',
                'asset',
                'staff',
                'scm',
                ],
    'version': '13.01',
    'data': [
        "data/asset_data_tw.xml",
        "data/finance_data_tw.xml",
        'data/tw_balance_sheet_data.xml',
        'data/tw_profit_statement_data.xml',
        'data/task_data.xml',
        'views/finance_tw.xml',
        'views/partner.xml',
        'views/staff_company_form.xml',
        'views/staff_employee_form.xml',
        'report/report_data.xml'
    ],
    "pre_init_hook": "pre_init_remove_constraint",
    "post_init_hook": "post_init_constraint",
}
