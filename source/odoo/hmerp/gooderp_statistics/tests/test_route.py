# Copyright 2016 唤梦科技 (http://www.dreammm.net)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import HttpCase


class TestActionStatistics(HttpCase):

    def test_user_info(self):
        ''' 获取用户名字 '''
        response = self.url_open('/get_user_info')
        self.assertEqual(response.status_code, 200)
