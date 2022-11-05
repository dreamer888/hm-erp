##############################################################################
#
#    Copyright (C) 2020  永远的不知().
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundaption, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, models, api
from odoo.exceptions import UserError

# 销售订单确认状态可选值
TAX_INVOICE_STATES = [
    ('draft', '待开具'),
    ('submit', '已通知开票'),
    ('done', '已完成')]

READONLY_STATES = {
    'done': [('readonly', True)],
}

class TaxInvoice(models.Model):
    _name = 'tax.invoice'
    _description = '发票'
    _rec_name = 'name'
    _order = 'create_date DESC'

    state = fields.Selection(TAX_INVOICE_STATES, '状态', readonly=True,
                             help="发票状态标识，新建时状态为草稿，确认后状态为完成", index=True,
                             copy=False, default='draft')

    money_invoice_id = fields.Many2one('money.invoice', '结算单', readonly=True,
                                       ondelete='cascade', help='发票对应的结算单')
    voucher_id = fields.Many2one('voucher','会计凭证',related='money_invoice_id.voucher_id',readonly=True)
    cogs_voucher_id = fields.Many2one('voucher','成本凭证',related='money_invoice_id.cogs_voucher_id',readonly=True)
    my_company_name = fields.Char('本公司名称', readonly=True, help='本公司名称')
    my_company_code = fields.Char('本公司税号', readonly=True)
    my_company_address = fields.Char('本公司地址、电话', readonly=True)
    my_company_bank_number = fields.Char('本公司开户行及帐号', readonly=True)

    partner_id = fields.Many2one('partner', '业务伙伴', ondelete='restrict',
                                 readonly=True, help='该单据对应的业务伙伴')
    partner_code = fields.Char('纳税人税号', readonly=True)
    partner_address = fields.Char('地址、电话', readonly=True)
    partner_bank_number = fields.Char('开户行及帐号', readonly=True)
    partner_order = fields.Char('客户订单号', readonly=True)
    order_id = fields.Char('订单号', copy=False,
                           ondelete='restrict', readonly=True,
                           help='发票对应的订单号')
    name = fields.Char(string='内部序号', copy=False,
                       ondelete='cascade', readonly=True,
                       help='内部发票序号')

    invoice_type = fields.Selection([('in', '进项发票'),
                                     ('out', '销项发票')], '发票种类', readonly=True)
    catagory = fields.Selection([('pt', '增值税普通发票'),
                                 ('zy', '增值税专用发票')], '发票类型', readonly=True)
    invoice_code = fields.Char('发票代码', help='该单据对应的发票代码')
    invoice_number = fields.Char('发票号码', help='发票号码，多张发票中间用空格分开')
    invoice_amount = fields.Float('合计金额', readonly=True, digits="Price")
    invoice_tax = fields.Float('合计税额', readonly=True)
    invoice_amount_add = fields.Float('金额调增')
    invoice_tax_add = fields.Float('税额调增')
    invoice_subtotal = fields.Float('价税合计', readonly=True, help='原始价税合计，不含调增金额')
    invoice_date = fields.Date('开票日期')
    line_ids = fields.One2many('tax.invoice.line', 'tax_invoice_id', '发票明细行')
    attachment_number = fields.Integer(
        compute='_compute_attachment_number', string='附件号')
    note = fields.Text(u"备注")

    _sql_constraints = [
        ('unique_invoice_code_number',
         'unique(invoice_code, invoice_number)',
         '发票代码+发票号码不能相同!'),
    ]

    def action_get_attachment_view(self):
        res = self.env['ir.actions.act_window'].for_xml_id(
            'base', 'action_attachment')
        res['domain'] = [('res_model', '=', 'tax.invoice'),
                         ('res_id', 'in', self.ids)]
        res['context'] = {'default_res_model': 'tax.invoice',
                          'default_res_id': self.id}
        return res

    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group(
            [('res_model', '=', 'tax.invoice'),
             ('res_id', 'in', self.ids)],
            ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count'])
                          for data in attachment_data)
        self.attachment_number = attachment.get(self.id, 0)

    def tax_invoice_submit(self):
        '''提交发票'''
        self.ensure_one()
        if self.state == 'submit':
            raise UserError('请不要重复提交！')
        self.write({
            'state': 'submit',
        })

    def write(self, vals):
        if (vals.get('state') == 'done' or self.state == 'done'):
            if (not vals.get('invoice_number')) and (not self.invoice_number):
                raise UserError('发票号码不能为空')

            invoice_number = vals.get('invoice_number') or self.invoice_number
            for number in invoice_number.split(' '):
                if len(number) != 8:
                    raise UserError('发票号码 %s 长度为 %s ,应该为8' % (number, len(number)))

            if not vals.get('invoice_date') and (not self.invoice_date):
                raise UserError('开票日期不能为空')
        return super(TaxInvoice, self).write(vals)   

    def tax_invoice_done(self):
        '''审核时不合法的给出报错'''
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认！')
        self.write({
            'state': 'done',
        })

        self.money_invoice_id.write({
            'bill_number': self.invoice_number,
            'invoice_date': self.invoice_date,
            'amount':self.invoice_subtotal + self.invoice_amount_add + self.invoice_tax_add,
            'tax_amount':self.invoice_tax + self.invoice_tax_add,
        })        

        self.money_invoice_id.money_invoice_done()
    
    def tax_invoice_done_to_submit(self):
        '''撤销开票回到已申请状态'''
        self.ensure_one()
        if self.state == 'submit':
            raise UserError('请不要重复撤销！')
        self.write({
            'state': 'submit',
        })

        self.money_invoice_id.write({
            'bill_number': '',
        })        

        self.money_invoice_id.money_invoice_draft()

# 定义发票明细行
class tax_invoice_line(models.Model):
    _name = 'tax.invoice.line'
    _description = '发票明细'

    tax_invoice_id = fields.Many2one('tax.invoice', '发票', help='关联发票',ondelete='cascade')
    goods_id = fields.Many2one('goods', string='商品', required=True,
                               index=True, ondelete='restrict',
                               help='该单据行对应的商品', readonly=True)
    goods_name = fields.Char('货物名称', readonly=True)
    partnumber = fields.Char('规格型号', readonly=True)
    note = fields.Text('备注')
    uom = fields.Char('单位', readonly=True)
    quantity = fields.Float('数量', readonly=True)
    price = fields.Float('价格', readonly=True, digits="Price")
    amount = fields.Float('金额', readonly=True, digits="Price")
    tax_rate = fields.Float('税率', readonly=True)
    tax = fields.Float('税额', readonly=True)
    tax_catagory = fields.Char(
        '税收分类编码', help='20170101以后使用的税收分类编码，这个很重要', readonly=True)
