# -*- coding: utf-8 -*-
##############################################################################
{
    "name": "hmERP自定义工作流",
    "version": "13.0.1.0",
    'license': 'AGPL-3',
    "depends": ["base", "web", "calendar"],
    "author": "jeff@osbzr.com",
    "category": "hmERP",
    "description": """
       hmERP自定义工作流
    """,
    "data": [
        'secureity/ir.model.access.csv',
        'views/assets.xml',
        'views/workflow.xml',
        'wizard/wizard_workflow.xml',
    ]
}
