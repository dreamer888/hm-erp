# -*- coding: utf-8 -*-
##############################################################################
from lxml import etree
from odoo import api, _, SUPERUSER_ID
from odoo.models import BaseModel
from odoo.exceptions import Warning

from odoo.tools.safe_eval import safe_eval
import logging

_logger = logging.getLogger(__name__)


def workflow_trans_condition_expr_eval(self, lines):
    '''
    判断迁移条件是否成立
    '''
    result = False

    for line in lines.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line == 'True':
            result = True
        elif line == 'False':
            result = False
        else:
            result = eval(line)
    return result


default_get_old = BaseModel.default_get


@api.model
def default_get_new(self, fields_list):
    '''
    从工作流的开始节点取审批状态的默认值
    '''
    res = default_get_old(self, fields_list)
    if 'x_workflow_state' in fields_list:
        res.update({'x_workflow_state': self.env['good.workflow'].get_default_state(self._name)})
    return res


BaseModel.default_get = default_get_new


def workflow_button_action(self):
    ctx = self.env.context.copy()
    t_id = int(self.env.context.get('trans_id'))
    trans = self.env['workflow.trans'].browse(t_id)

    if trans.need_note:
        return {
            'name': '工作流审批',
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'wizard.workflow.message',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx,
        }
    else:
        return self.workflow_action()


def workflow_action(self, message=''):
    t_id = int(self.env.context.get('trans_id'))
    trans = self.env['workflow.trans'].browse(t_id)

    condition_ok = workflow_trans_condition_expr_eval(self, trans.condition)
    _logger.info('>>>>>>%s: %s', trans.condition, condition_ok)

    if not condition_ok:
        if trans.auto:
            _logger.info('condition false:%s', trans.condition)
            return True
        else:
            raise Warning('迁移条件不满足，请联系管理员。')

    # check repeat trans
    if not trans.is_backward:
        if self.env['log.workflow.trans'].search([('res_id', '=', self.id), ('trans_id', '=', t_id)], limit=1):
            raise Warning('迁移已完成')

    log = trans.make_log(self.name, self.id, message)

    # check  can be trans
    node_to = trans.node_to
    can_trans = node_to.check_trans_in(self.id)
    if can_trans:
        self.write({'x_workflow_state': str(node_to.id)})
        action, arg = node_to.action, node_to.arg
        # action
        if trans.is_backward:
            node_to.backward_cancel_logs(self.id)
        else:
            if action:
                _logger.info('======action:%s, arg:%s', action, arg)
                if arg:
                    getattr(self, action)(eval(arg))
                else:
                    getattr(self, action)()

        # calendar event
        if node_to.event_need:
            node_to.make_event(self.name)

        # message to user
        self.message_post(
            body='%s %s' % (self.name, node_to.name),
            message_type="comment",
            subtype="mail.mt_comment",
            partner_ids=[u.partner_id.id for u in node_to.event_users],
        )

        # 3 auto trans
        auto_trains = filter(lambda t: t.auto, node_to.out_trans)
        for auto_t in auto_trains:
            self.with_context(trans_id=auto_t.id).workflow_button_action()

    return True


def workflow_button_show_log(self):
    return {
        'name': '审批历史',
        'view_mode': 'tree',
        'res_model': 'log.workflow.trans',
        'type': 'ir.actions.act_window',
        'target': 'new',
        'domain': [('res_id', '=', self[0].id,)],
    }


def workflow_button_reset(self):
    logs = self.env['log.workflow.trans'].search([('res_id', '=', self[0].id), ('model', '=', self._name)])
    logs.write({'active': False})
    workflow_id = self.env.context.get('workflow_id')
    state = self.env['good.workflow'].browse(workflow_id).default_state
    self.write({'x_workflow_state': state})
    return True


BaseModel.workflow_button_action = workflow_button_action
BaseModel.workflow_action = workflow_action
BaseModel.workflow_button_show_log = workflow_button_show_log
BaseModel.workflow_button_reset = workflow_button_reset


old_fields_view_get = BaseModel.fields_view_get


@api.model
def new_fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
    res = old_fields_view_get(self, view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
    if view_type != 'form':
        return res
    if not self.env['ir.module.module'].sudo().search(
           [('name', '=', 'good_workflow'), ('state', '=', 'installed')]):
        return res
    view = etree.fromstring(res['arch'])
    for tag in view.xpath("//button[@user_ids]"):
        users_str = tag.get('user_ids')
        user_ids = [int(i) for i in users_str.split(',')]
        if self._uid not in user_ids and self._uid != SUPERUSER_ID:
            tag.getparent().remove(tag)
    default_state = self.env['good.workflow'].get_default_state(res['model'])
    field_id = self.env['good.workflow'].get_field_id(res['model'])
    if default_state and field_id:
        view.xpath("//form")[0].set(
            "disable_edit_mode",
            "[('x_workflow_state', '!=', '%s')]" % default_state)
    res['arch'] = etree.tostring(view)
    return res


BaseModel.fields_view_get = new_fields_view_get

write_original = BaseModel.write


def write(self, vals):
    if vals.get('state') and self._name[0:3] not in ['ir.', 'res']:
        if not self.env['ir.module.module'].sudo().search(
           [('name', '=', 'good_workflow'), ('state', '=', 'installed')]):
            return write_original(self, vals)
        stop_node = self.env['workflow.node'].search([
            ('workflow_id.model', '=', self._name),
            ('is_stop', '=', True),
            ])
        if stop_node and stop_node.workflow_id.field_id:
            if self.x_workflow_state and self.x_workflow_state != str(stop_node.id):
                raise Warning('审批完成前不可修改状态')
    return write_original(self, vals)


BaseModel.write = write
