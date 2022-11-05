# Copyright 2016 唤梦科技 (http://www.dreammm.net)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


def open_dialog(self, func, options=None):
    '''弹出窗口显示消息文本并由用户确认继续执行或取消'''
    context = dict(self.env.context or {})
    context.update(options or {})
    context.update({'func': func})

    if not context.get('message'):
        context['message'] = u'确定吗？'

    return {
        'type': 'ir.actions.act_window',
        'res_model': 'common.dialog.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': context
    }

# 所有对象皆可调用此方法
models.BaseModel.open_dialog = open_dialog
