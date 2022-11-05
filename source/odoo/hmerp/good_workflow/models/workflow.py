# -*- coding: utf-8 -*-
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import Warning
from lxml.etree import XML, tostring

btn_contain_template = """
    <div class="o_statusbar_buttons"></div>
"""

btn_template = """
    <button name="workflow_button_action" string="%(btn_str)s"
          context="{'trans_id':'%(trans_id)s'}"
          attrs="{'invisible':[('x_workflow_state','!=', '%(vis_state)s')]}"
          type="object"
          class="oe_highlight"/>
"""

btn_show_log_template =  """
    <button name="workflow_button_show_log"
          string="%(btn_str)s"
          type="object"
          groups="%(btn_grp)s"
          />
"""

btn_workflow_reset_template = """
    <button name="workflow_button_reset"
          string="%(btn_str)s"
          type="object"
          groups="%(btn_grp)s"
          context="{'workflow_id': %(btn_ctx)s}"
          attrs="{'invisible':[('x_workflow_state','in', [%(no_reset_states)s])]}"
          />
"""


arch_template_header = """
    <xpath expr="//header" position="after"></xpath>
"""

arch_template_no_header = """
    <xpath expr="//form/*" position="before"></xpath>
"""

workflow_contain_template = """
    <div class='o_form_statusbar o_from_workflow_contain'></div>
"""

wfk_field_state_template = """
    <field name="%s" widget="statusbar" readonly="1"  statusbar_visible="%s"/>
"""
wfk_field_note_template = """
    <span class="oe_inline">审批意见:<field name="%s" class="oe_inline"/></span>
"""

class GoodWorkFlow(models.Model):
    _name = 'good.workflow'
    _description = '审批流'
    _def_workflow_state_name = 'x_workflow_state'

    @api.depends('node_ids')
    def _compute_default_state(self):
        def _get_start_state(nodes):
            if not nodes:
                return None
            star_id = nodes[0].id
            for n in nodes:
                if n.is_start:
                    star_id = n.id
                    break
            return str(star_id)

        nodes = self.node_ids
        show_nodes = filter(lambda x: x.show_state, nodes)
        no_rest_nodes = filter(lambda x: x.no_reset, nodes)

        self.show_states = ','.join([str(x.id) for x in show_nodes])
        self.default_state = _get_start_state(nodes)
        self.no_reset_states = ','.join(["'%s'" % x.id for x in no_rest_nodes])

    @api.model
    def _default_reset_group(self):
        return self.env['ir.model.data'].xmlid_to_res_id('base.group_system')

    name = fields.Char('名称', required=True, )
    model_id = fields.Many2one('ir.model', '模型', required=True)
    model = fields.Char(related='model_id.model', string='模型名', readonly=True)
    model_view_id = fields.Many2one('ir.ui.view', '视图',
                                    help="审批按钮和状态需要出现在这个表单上")
    view_id = fields.Many2one('ir.ui.view', '生成的视图', readonly=True,
                              help="自动生成的审批按钮和状态视图")
    node_ids = fields.One2many('workflow.node', 'workflow_id', '节点')
    trans_ids = fields.One2many('workflow.trans', 'workflow_id', '迁移')
    active = fields.Boolean('启用', default=True)
    field_id = fields.Many2one('ir.model.fields', '审批状态字段名', readonly=True)
    tracking = fields.Integer('消息记录审批状态', default=1)

    allow_reset = fields.Boolean("允许重置工作流", default=True)
    reset_group = fields.Many2one('res.groups', "重置用户组", 
                                  default=_default_reset_group, required=True)
    no_reset_states = fields.Char(compute='_compute_default_state',
                                  string='不可重置的状态')
    default_state = fields.Char(compute='_compute_default_state',
                                string="默认审批状态", store=False,
                                help='默认的审批状态')
    show_states = fields.Char(compute='_compute_default_state', string="显示的状态",
                              store=False, help='根据节点计算出可显示的审批状态')

    @api.constrains('model_id')
    def check_uniq(self):
        for one in self:
            if self.search_count([('model_id', '=', one.model_id.id)]) > 1:
                raise Warning('每个模型只能有一个审批流')


    @api.model
    def get_default_state(self, model):
        return self.search([('model', '=', model)]).default_state

    @api.model
    def get_field_id(self, model):
        return self.search([('model', '=', model)]).field_id

    def sync2ref_model(self):
        self.ensure_one()
        self._check()
        self.make_field()
        self.make_view()

    def _check(self):
        if not any([n.is_start for n in self.node_ids]):
            raise Warning('审批流必须有开始节点')

    def make_workflow_contain(self):
        workflow_contain = XML(workflow_contain_template)
        workflow_contain.append(self.make_btm_contain())
        workflow_contain.append(XML(wfk_field_state_template % (self.field_id.name, self.show_states)))
        return workflow_contain

    def make_btm_contain(self):
        btn_contain = XML(btn_contain_template)
        for t in self.trans_ids:
            if t.auto:
                continue
            btn = XML(btn_template % {'btn_str': t.name, 'trans_id': t.id, 'vis_state': t.node_from.id})
            if t.group_ids:
                btn.set('groups', t.xml_groups)
            if t.user_ids:
                user_ids_str = ','.join([str(x.id) for x in t.user_ids])
                btn.set('user_ids', user_ids_str)
            btn_contain.append(btn)

        btn_contain.append(XML(btn_show_log_template % {'btn_str': '显示审批历史', 'btn_grp': 'base.group_user'}))
        btn_contain.append(XML(btn_workflow_reset_template % {
            'btn_str': '重置审批流', 'btn_grp': 'base.group_system',
            'btn_ctx': self.id, 'no_reset_states': self.no_reset_states}))
        return btn_contain

    def make_view(self):
        self.ensure_one()
        view_obj = self.env['ir.ui.view']
        have_header = '<header>' in self.model_view_id.arch
        arch = have_header and XML(arch_template_header) or XML(arch_template_no_header)

        workflow_contain = self.make_workflow_contain()

        arch.insert(0, workflow_contain)

        view_data = {
            'name': '%s.workflow.form.view' % self.model,
            'type': 'form',
            'model': self.model,
            'inherit_id': self.model_view_id.id,
            'mode': 'extension',
            'arch': tostring(arch),
            'priority': 100000,
        }

        view = self.view_id
        if not view:
            view = view_obj.create(view_data)
            self.write({'view_id': view.id})
        else:
            view.write(view_data)

        return True

    def make_field(self):
        self.ensure_one()
        fd_obj = self.env['ir.model.fields']
        fd_id = fd_obj.search([('name', '=', self._def_workflow_state_name), ('model_id', '=', self.model_id.id)])
        fd_data = {
            'name': self._def_workflow_state_name,
            'ttype': 'selection',
            'state': 'manual',
            'model_id': self.model_id.id,
            'model': self.model_id.model,
            'modules': self.model_id.modules,
            'tracking': self.tracking,
            'field_description': '审批状态',
            'selection': str(self.get_state_selection()),
        }
        if fd_id:
            fd_id.write(fd_data)
        else:
            fd_id = fd_obj.create(fd_data)

        self.write({'field_id': fd_id.id})
        return True

    @api.model
    def get_state_selection(self):
        return [(str(i.id), i.name) for i in self.node_ids]

    def action_no_active(self):
        self.ensure_one()
        self.view_id.unlink()
        self.field_id.unlink()
        return True


class workflow_node(models.Model):
    _name = "workflow.node"
    _description = "审批节点"
    _order = 'sequence'

    name = fields.Char('名称', required=True)
    sequence = fields.Integer('顺序')
    code = fields.Char('编号', required=False)
    workflow_id = fields.Many2one('good.workflow', '审批流', required=True, index=True, ondelete='cascade')
    split_mode = fields.Selection([('OR', 'Or'), ('AND', 'And')], '迁出模式', size=3, required=False)
    join_mode = fields.Selection([('OR', 'Or'), ('AND', 'And')], '迁入模式', size=3, required=True, default='OR',
                                 help='OR:anyone input Transfers approved, will arrived this node.  AND:must all input Transfers approved, will arrived this node')
    action = fields.Char('模型方法', size=64,
                         help='可在到达此节点时执行当前模型的一个方法')
    arg = fields.Text('方法参数', size=64)
    is_start = fields.Boolean('开始节点', help='此节点是审批流的开始节点')
    is_stop = fields.Boolean('结束节点', help='此节点是审批流的结束节点')
    out_trans = fields.One2many('workflow.trans', 'node_from', '出栈迁移')
    in_trans = fields.One2many('workflow.trans', 'node_to', '入栈迁移')
    show_state = fields.Boolean('显示为状态', default=True, help="勾选了才会在单据上作为审批状态显示")
    no_reset = fields.Boolean('不可重置', default=True, help="勾选了才能在这个节点看到重置按钮")
    event_need = fields.Boolean('创建提醒', help="在日历上创建提醒")
    event_users = fields.Many2many('res.users', 'event_users_trans_ref', 'tid', 'uid', '用户', help="提醒的用户")

    def backward_cancel_logs(self, res_id):
        """
        此节点的迁移记录及其后的迁移记录全部取消
        """
        log_obj = self.env['log.workflow.trans']
        logs = log_obj.search([('res_id', '=', res_id), ('trans_id.node_from.id', '=', self.id)])
        if logs:
            min_date = min([x.create_date for x in logs])
            logs2 = log_obj.search([('res_id', '=', res_id), ('create_date', '>=', min_date)])
            logs.write({'active': False})
            logs2.write({'active': False})

    def check_trans_in(self, res_id):
        self.ensure_one()

        flag = True
        join_mode = self.join_mode
        log_obj = self.env['log.workflow.trans']

        flag = False
        if join_mode == 'OR':
            flag = True
        else:
            in_trans = filter(lambda x: x.is_backward is False, self.in_trans)
            trans_ids = [x.id for x in in_trans]
            logs = log_obj.search([('res_id', '=', res_id), ('trans_id', 'in', trans_ids)])
            log_trans_ids = [x.trans_id.id for x in logs]
            flag = set(trans_ids) == set(log_trans_ids) and True or False

        return flag

    def make_event(self, name):
        data = {
            'name': '%s %s' % (name, self.name),
            'state': 'open',
            'partner_ids': [(6, 0, [u.partner_id.id for u in self.event_users])],
            'start': fields.Datetime.now(),
            'stop': fields.Datetime.now(),
            'start_datetime': fields.Datetime.now(),
            'stop_datetime': fields.Datetime.now(),
            'duration': 1,
            'alarm_ids': [(6, 0, [1])],
        }
        self.env['calendar.event'].create(data)
        return True


class workflow_trans(models.Model):
    _name = "workflow.trans"
    _description = "迁移"
    _order = "sequence"

    @api.depends('group_ids')
    def _compute_xml_groups(self):
        data_obj = self.env['ir.model.data']
        xml_ids = []
        for g in self.group_ids:
            data = data_obj.search([('res_id', '=', g.id), ('model', '=', 'res.groups')])
            xml_ids.append(data.complete_name)
        self.xml_groups = xml_ids and ','.join(xml_ids) or False

    name = fields.Char("名称", required=True, help='两个节点之间的迁移')
    code = fields.Char('编号', required=False)
    group_ids = fields.Many2many('res.groups', 'group_trans_ref', 'tid', 'gid', '用户组', help="可以执行此迁移的用户组")
    user_ids = fields.Many2many('res.users', 'user_trans_ref', 'tid', 'uid', '用户', help="可以执行此迁移的用户")
    condition = fields.Char('条件', required=True, default='True', help='迁移的条件，默认为True')
    node_from = fields.Many2one('workflow.node', '从节点', required=True, index=True, ondelete='cascade', )
    node_to = fields.Many2one('workflow.node', '到节点', required=True, index=True, ondelete='cascade')
    workflow_id = fields.Many2one('good.workflow', related='node_from.workflow_id', store=True)
    model = fields.Char(related='workflow_id.model')
    xml_groups = fields.Char(compute='_compute_xml_groups', string='XML Groups')
    is_backward = fields.Boolean('可重复迁移')
    auto = fields.Boolean('自动', help="如果条件满足，无需点击按钮，自动完成迁移")
    sequence = fields.Integer('顺序号')
    need_note = fields.Boolean('需输入审批意见', help="这个迁移要求必须输入审批意见，常见于拒绝迁移")

    def make_log(self, res_name, res_id, note=''):
        return self.env['log.workflow.trans'].create({'name': res_name, 'res_id': res_id, 'trans_id': self.id, 'note': note})


class log_workflow_trans(models.Model):
    _name = "log.workflow.trans"
    _description = "workflow log"

    name = fields.Char('编号')
    trans_id = fields.Many2one('workflow.trans', '迁移')
    model = fields.Char(related='trans_id.model', string='模型')
    res_id = fields.Integer('id')
    active = fields.Boolean('启用', default=True)
    note = fields.Text('审批意见')
