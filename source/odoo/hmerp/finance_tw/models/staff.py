# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class Staff(models.Model):
    _inherit = 'staff'

    type_of_certification_tw = fields.Selection([
        ('ID', '身份證'),
        ('Passport_card', '護照'),
    ], string='證照類型', default='ID', required=True)
