###############################################################################
#
#    Copyright (c) All rights reserved:
#        (c) 2020  唤梦科技  GoodERP
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses
#    
###############################################################################
{
    'name': '根据批次拆分移库行',
    'summary': '支持一次收发相同产品的多个批次',
    'version': '1.0',

    'description': """
GoodERP的每个移库单行只能有一个批次

这样当用户要针对同一个移库单行输入多个批次时，10版本可以复制行并修改数量

这里创建一个向导，参照odoo的设计，要求用户在向导上输入批次和数量，由系统给用户拆分成多个移库单行

相比之前的设计，减少了手工修改数量导致的错误
    """,

    'author': 'jeff@osbzr.com',
    'maintainer': '唤梦科技',

    'website': 'http://www.dreammm.net',

    'license': 'AGPL-3',
    'category': 'gooderp',

    'depends': [
        'base','scm'
    ],
    'data':[
        'wizard/batch_split_wizard_view.xml',
    ]
}
