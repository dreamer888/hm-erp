{
    'name': 'hmERP 生产管理',
    'author': '珠天创（珠海）软件科技有限责任公司',
    'category': 'hmERP manufacture',
    'description': '该模块包含了hmERP生产管理相关功能',
    'version': '13.01',
    'depends': ['core', 'staff', 'goods', 'sell', 'buy', 'warehouse','scm'],
    'demo': ['data/demo.xml'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/goods_view.xml',
        'views/ous_price_strategy_view.xml',
        'views/mrp_bom_category_view.xml',
        'views/mrp_bom_view.xml',
        'views/mrp_workcenter_view.xml',
        'views/mrp_plm_view.xml',
        'views/mrp_plan_view.xml',
        'views/mrp_plm_in_view.xml',
        'views/mrp_plm_cons_view.xml',
        'views/mrp_plm_cons_add_view.xml',
        'views/mrp_plm_cons_retu_view.xml',
        'views/mrp_plm_task_view.xml',
        'views/mrp_plm_task_conf_view.xml',
        'views/mrp_plm_task_qc_view.xml',
        'views/mrp_plm_task_defectdealing_view.xml',
        'views/mrp_plm_ous_view.xml',
        'views/mrp_plm_ous_conf_view.xml',
        'views/mrp_plm_ous_retu_view.xml',
        'views/mrp_plm_ous_qc_view.xml',
        'views/mrp_plm_ous_defectdealing_view.xml',
        'views/mrp_plm_scrap_view.xml',
        'views/mrp_proc_view.xml',
        'views/mrp_proc_cause_view.xml',
        'views/mrp_proc_class_view.xml',
        'views/mrp_proc_type_view.xml',
        'views/ous_partner_strategy_view.xml',
        'views/partner_quality_grade_view.xml',
        'menu/menu.xml',
        'report/mrp_mat_detial_report_view.xml',
        'report/mrp_in_detial_report_view.xml',
        'report/mrp_ous_progress_report_view.xml',
        'report/mrp_plm_progress_report_view.xml',        
        'wizard/bom_copy_wizard_view.xml',
        'wizard/mrp_mat_detial_wizard_view.xml',
        'wizard/mrp_in_detial_wizard_view.xml',
        'wizard/mrp_ous_progress_wizard_view.xml',
        'wizard/mrp_plm_progress_wizard_view.xml',        
    ],
    'installable': True,
    'auto_install': False,
}