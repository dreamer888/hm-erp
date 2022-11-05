
from datetime import datetime,timedelta
from odoo import api, fields, models


class Partner(models.Model):
    _inherit = 'partner'

    def action_view_buy_history(self):
        '''
        This function returns an action that display buy history of given sells order ids.
        Date range [365 days ago, now]
        '''
        self.ensure_one()
        date_end = fields.Date.context_today(self)
        date_start = self.env.user.company_id.start_date

        if (date_end - date_start).days > 365:
            date_start = date_end - timedelta(days=365)

        buy_order_track_wizard_obj = self.env['buy.order.track.wizard'].create({'date_start': date_start,
                                                                                'date_end': date_end,
                                                                                'partner_id': self.id})

        return buy_order_track_wizard_obj.button_ok()
