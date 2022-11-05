

from odoo import models, fields, api
from odoo import tools


class ReportAuxiliaryAccounting(models.Model):
    _name = 'report.auxiliary.accounting'
    _auto = False
    _description = '辅助核算余额表'

    account_id = fields.Many2one('finance.account', '会计科目')
    auxiliary_id = fields.Many2one(
        'auxiliary.financing', '辅助核算', ondelete='restrict')
    debit = fields.Float('借方金额', digits='Amount')
    credit = fields.Float('贷方金额', digits='Amount')
    balance = fields.Float('余额', digits='Amount')

    def view_voucher_line_detail(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'voucher.line',
            'name': "%s - %s 明细行" % (self.account_id.name, self.auxiliary_id.name),
            'view_mode': 'tree',
            'domain': [('account_id', '=', self.account_id.id), ('auxiliary_id', '=', self.auxiliary_id.id)],
        }

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, 'report_auxiliary_accounting')
        cr.execute(
            """
            create or replace view report_auxiliary_accounting as (
                  SELECT min(line.id) as id,
                         line.account_id as account_id,
                         line.auxiliary_id as auxiliary_id,
                         sum(line.debit) as debit,
                         sum(line.credit) as credit,
                         sum(COALESCE(line.debit,0) - COALESCE(line.credit,0)) as balance
                  FROM voucher_line line
                  WHERE  line.voucher_id is NOT NULL AND
                  line.auxiliary_id IS  NOT NULL and
                  line.state = 'done' AND
                         (line.debit !=0 OR
                  line.credit !=0)
                  GROUP BY line.account_id, line.auxiliary_id
            )
        """)
