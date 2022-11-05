# Copyright 2016 唤梦科技 (http://www.dreammm.net)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import http
from json import dumps
from datetime import datetime


class ActionStatistics(http.Controller):
    '''用于统计用户点击次数并记录在www.dreammm.net'''

    @http.route('/get_user_info', auth='public')
    def get_user_info(self):
        '''获取当前用户名称等信息'''
        user = http.request.env.user

        return dumps({
            'user': user.name,
            'login': user.login,
            'company': user.company_id.name,
            'company_phone': user.company_id.phone,
            'company_start_date': datetime.strftime(user.company_id.start_date,"%Y-%m-%d"),
            'company_street': user.company_id.street
        })
