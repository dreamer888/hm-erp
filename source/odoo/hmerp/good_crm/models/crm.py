
from odoo import api, fields, models

# 状态可选值
LEAD_STATES = [
    ('todo', '新建'),
    ('doing', '正在进行'),
    ('done', '已完成'),
    ('cancel', '无效'),
]

class Lead(models.Model):
    _name = 'lead'
    _description = '线索'

    name = fields.Char('名称', required=True)
    note = fields.Text('描述')
    customer_name = fields.Char('客户公司名称')
    contact = fields.Char('联系人信息')
    state = fields.Selection(LEAD_STATES, '状态', default='todo')
    channel_id = fields.Many2one('core.value', '渠道',
                                 ondelete='restrict',
                                 domain=[('type', '=', 'channel')],
                                 context={'type': 'channel'})
    source = fields.Char('来源')
    track_date = fields.Date('跟进日期')
    track_result = fields.Text('跟进结果')

    def new_opp(self):
        return {
            'name': "创建商机",
            'res_model': 'opportunity',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': {'default_name': self.name,
                        'default_lead_id': self.id,
                       'default_note':'%s %s %s' % (self.customer_name,
                                                    self.contact,
                                                    self.note)}
        }

    def set_cancel(self):
        self.state = 'cancel'


class Opportunity(models.Model):
    _name = 'opportunity'
    _inherits = {'task': 'task_id'}
    _inherit = ['mail.thread']
    _order = 'planned_revenue desc, priority desc, id'
    _description = '商机'

    @api.model
    def _select_objects(self):
        records = self.env['business.data.table'].search([])
        models = self.env['ir.model'].search(
            [('model', 'in', [record.name for record in records])])
        return [(model.model, model.name) for model in models]

    @api.depends('line_ids.price', 'line_ids.quantity')
    def _compute_total_amount(selfs):
        """
        计算报价总额
        :return:
        """
        for self in selfs:
            self.total_amount = sum(
                line.price * line.quantity for line in self.line_ids)

    @api.model
    def _read_group_status_ids(self, status, domain, order):
        # 看板或列表视图上分组时显示所有阶段（即使该阶段没有记录）
        status_ids = self.env['task.status'].search([('project_type_id', '=', False)])
        return status_ids

    @api.model
    def _default_status(self):
        '''创建商机时，阶段默认为todo状态的阶段，即 新建'''
        return self.task_id._default_status()

    task_id = fields.Many2one('task',
                              '任务',
                              ondelete='cascade',
                              required=True)
    planned_revenue = fields.Float('预期收益',
                                   track_visibility='always')
    ref = fields.Reference(string='相关记录',
                           selection='_select_objects')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'partner',
        '客户',
        ondelete='restrict',
        help='待签约合同的客户',
    )
    date = fields.Date('预计采购时间')
    line_ids = fields.One2many(
        'goods.quotation',
        'opportunity_id',
        string='商品报价',
        copy=True,
    )
    total_amount = fields.Float(
        '报价总额',
        track_visibility='always',
        compute='_compute_total_amount',
    )
    success_reason_id = fields.Many2one(
        'core.value',
        '成败原因',
        ondelete='restrict',
        domain=[('type', '=', 'success_reason')],
        context={'type': 'success_reason'},
        help='成败原因分析',
    )

    lead_id = fields.Many2one('lead', '线索')

    channel_id = fields.Many2one('core.value', related='lead_id.channel_id')

    source = fields.Char('来源', related='lead_id.source')

    status = fields.Many2one(
        'task.status',
        string='状态',
        group_expand='_read_group_status_ids',
        default=_default_status,
        track_visibility='onchange',
        ondelete='restrict',
        domain="[('project_type_id', '=', False)]",
    )

    def assign_to_me(self):
        ''' 继承任务 指派给自己，将商机指派给自己，并修改状态 '''
        for o in self:
            o.task_id.assign_to_me()

    def write(self, vals):
        if vals.get('status'):
            for s in self:
                s.lead_id.state = s.status.state
        return super().write(vals)

    @api.model
    def create(self, vals):
        ret = super().create(vals)
        for s in ret:
            s.lead_id.state = 'doing'
        return ret


class GoodsQuotation(models.Model):
    _name = 'goods.quotation'
    _description = '商品报价'

    opportunity_id = fields.Many2one('opportunity',
                                     '商机',
                                     index=True,
                                     required=True,
                                     ondelete='cascade',
                                     help='关联的商机')
    goods_id = fields.Many2one('goods',
                               '商品',
                               ondelete='restrict',
                               help='商品')
    quantity = fields.Float('数量',
                            default=1,
                            digits='Quantity',
                            help='数量')
    price = fields.Float('单价',
                         required=True,
                         digits='Price',
                         help='商品报价')
    note = fields.Char('描述',
                       help='商品描述')
