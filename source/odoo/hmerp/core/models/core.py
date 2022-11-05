

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils


groupby_original = models.BaseModel._read_group_process_groupby


@api.model
def _read_group_process_groupby(self, gb, query):
    res = groupby_original(self, gb, query)
    split = gb.split(':')
    gb_function = split[1] if len(split) == 2 else None
    if gb_function and gb_function == 'day':
        res['display_format'] = 'yyyy-MM-dd'    # 按 day 分组显示格式
    if (gb_function and gb_function == 'month') or not gb_function:
        res['display_format'] = 'yyyy-MM'   # 按 month 分组显示格式
    return res


models.BaseModel._read_group_process_groupby = _read_group_process_groupby


# 单据自动编号，避免在所有单据对象上重载

create_original = models.BaseModel.create


@api.model
@api.returns('self', lambda value: value.id)
def create(self, vals):
    if not self._name.split('.')[0] in ['mail', 'ir', 'res'] and not vals.get('name'):
        next_name = self.env['ir.sequence'].next_by_code(self._name)
        if next_name:
            vals.update({'name': next_name})
    record_id = create_original(self, vals)
    return record_id


models.BaseModel.create = create


# 不能删除已确认的单据，避免在所有单据对象上重载

unlink_original = models.BaseModel.unlink

BYPASS_MODELS = [
    'survey.user_input',
    'survey.user_input_line'
    ]


def unlink(self):
    IrLogging = self.env['ir.logging']
    _ignore_models = [
        'ir.logging',
        'website.page',
        'mail.message',
    ]
    for record in self:
        if 'state' in [item[0] for item in record._fields.items()] and self._name not in BYPASS_MODELS:
            if record.state == 'done' and not record._transient:
                raise UserError('不能删除已确认的 %s ！' % record._description)
        if self.is_transient() or self._name in _ignore_models or not record.display_name:
            continue
        IrLogging.sudo().create({
                'name': record.display_name,
                'type': 'client',
                'dbname': self.env.cr.dbname,
                'level': 'WARN',
                'message': '%s被删除' % self._name,
                'path': self.env.user.name,
                'func': 'delete',
                'line': 1})
    unlink_original(self)


models.BaseModel.unlink = unlink


def action_cancel(self):
    for record in self:
        record.state = 'cancel'
    return True


models.BaseModel.action_cancel = action_cancel


# 分类的类别

CORE_CATEGORY_TYPE = [('customer', '客户'),
                      ('supplier', '供应商'),
                      ('goods', '商品'),
                      ('expense', '采购'),
                      ('income', '收入'),
                      ('other_pay', '其他支出'),
                      ('other_get', '其他收入'),
                      ('attribute', '商品属性'),
                      ('finance', '核算')]

# 当客户要求下拉字段可编辑，可使用此表存储可选值，按type分类，在字段上用domain和context筛选


class CoreValue(models.Model):
    _name = 'core.value'
    _description = '可选值'

    name = fields.Char('名称', required=True)
    type = fields.Char('类型', required=True,
                       default=lambda self: self._context.get('type'))
    note = fields.Text('备注', help='此字段用于详细描述该可选值的意义，或者使用一些特殊字符作为程序控制的标识')
    parent_id = fields.Many2one('core.value', '上级')
    color = fields.Integer('Color Index')
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_uniq', 'unique(type,name)', '同类可选值不能重名')
    ]


class CoreCategory(models.Model):
    _name = 'core.category'
    _description = '类别'
    _order = 'type, name'

    name = fields.Char('名称', required=True)
    type = fields.Selection(CORE_CATEGORY_TYPE, '类型',
                            required=True,
                            default=lambda self: self._context.get('type'))
    note = fields.Text('备注')
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_uniq', 'unique(type, name)', '同类型的类别不能重名')
    ]

    def unlink(self):
        for record in self:
            if record.note:
                raise UserError('不能删除系统创建的类别')

        return super(CoreCategory, self).unlink()

class PayMethod(models.Model):
    _name = 'pay.method'
    _description = '付款条件'

    name = fields.Char('名称')
    add_months = fields.Integer(
        string='月数',
    )
    add_days = fields.Integer(
        string='天数',
    )

    def get_due_date(self, key_date=None):
        # 先加月数算到月底，再加天数
        if not key_date:
            key_date = fields.Date.context_today(self)
        due_date = key_date
        if self.add_months:
            due_date = date_utils.add(due_date, months=self.add_months)
            due_date = date_utils.end_of(due_date, 'month')
        if self.add_days:
            due_date = date_utils.add(due_date, days=self.add_days)
        return due_date


class Uom(models.Model):
    _name = 'uom'
    _description = '计量单位'

    name = fields.Char('名称', required=True)
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '单位不能重名')
    ]


class SettleMode(models.Model):
    _name = 'settle.mode'
    _description = '结算方式'

    name = fields.Char('名称', required=True)
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '结算方式不能重名')
    ]


class Staff(models.Model):
    _name = 'staff'
    _description = '员工'

    user_id = fields.Many2one('res.users', '对应用户')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    @api.constrains('user_id')
    def _check_user_id(self):
        '''一个员工只能对应一个用户'''
        for staff in self:
            staffs = []
            if staff.user_id:
                staffs = self.env['staff'].search(
                    [('user_id', '=', staff.user_id.id)])
            if len(staffs) > 1:
                raise UserError('用户 %s 已有对应员工' % staff.user_id.name)


class BankAccount(models.Model):
    _name = 'bank.account'
    _description = '账户'

    name = fields.Char('名称', required=True)
    num = fields.Char('账号')
    balance = fields.Float('余额', readonly=True,
                           digits='Amount')
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '账户不能重名')
    ]


class Service(models.Model):
    ''' 是对其他收支业务的更细分类 '''
    _name = 'service'
    _description = '收支项'

    name = fields.Char('名称', required=True)
    get_categ_id = fields.Many2one('core.category',
                                   '收入类别', ondelete='restrict',
                                   domain="[('type', '=', 'other_get')]",
                                   context={'type': 'other_get'})
    pay_categ_id = fields.Many2one('core.category',
                                   '支出类别', ondelete='restrict',
                                   domain="[('type', '=', 'other_pay')]",
                                   context={'type': 'other_pay'})
    price = fields.Float('价格', required=True)
    tax_rate = fields.Float('税率%')
    active = fields.Boolean('启用', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

class View(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def render_template(self, template, values=None, engine='ir.qweb'):
        if template in ['web.login', 'web.webclient_bootstrap']:
            if not values:
                values = {}
            values["title"] = 'hmERP'
        return super(View, self).render_template(template, values=values, engine=engine)
