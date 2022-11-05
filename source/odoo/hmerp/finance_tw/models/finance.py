# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class Voucher(models.Model):
    _inherit = 'voucher'

    amount_total_tw = fields.Float(string='總計', compute='_compute_amount', store=True,
                                   track_visibility='always', digits='Amount', help='憑證金額')

    @api.depends('line_ids')
    def _compute_amount(self):
        for v in self:
            v.amount_text = str(sum([line.debit for line in v.line_ids]))
            v.amount_total_tw = str(sum([line.debit for line in v.line_ids]))
