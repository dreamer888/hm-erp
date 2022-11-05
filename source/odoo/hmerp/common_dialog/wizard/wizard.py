# Copyright 2016 唤梦科技 (http://www.dreammm.net)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo import fields


class CommonDialogWizard(models.TransientModel):
    _name = 'common.dialog.wizard'
    _description = u'通用的向导'

    message = fields.Text(
        u'消息', default=lambda self: self.env.context.get('message'))

    def do_confirm(self):
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids')

        if active_ids and active_model:
            model = self.env[active_model].browse(active_ids)
            func = getattr(model, self.env.context.get('func'), None)

            if not func:
                raise ValueError(u'错误, model(%s)中找不到定义的函数%s' %
                                 (active_model, self.env.context.get('func')))

            args = self.env.context.get('args') or []
            kwargs = self.env.context.get('kwargs') or {}

            return func(*args, **kwargs)
        else:
            raise ValueError(u'错误, 向导中找不到源单的定义')
