# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class Partner(models.Model):
    _inherit = 'partner'

    main_fax = fields.Char(string='傳真')
    main_mail = fields.Char(string='電子郵件')
