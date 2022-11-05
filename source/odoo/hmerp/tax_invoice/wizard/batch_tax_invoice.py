from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BatchTaxInvoice(models.TransientModel):
    _name = 'batch.tax.invoice'
    _description = '纸质发票合并开票'

    partner_id = fields.Many2one('partner', '业务伙伴',
                                 readonly=True, help='该单据对应的业务伙伴')
    invoice_amount = fields.Float('已选金额', readonly=True, digits="Price")
    invoice_tax = fields.Float('已选税额', readonly=True)
    invoice_code = fields.Char('发票代码', required=True, help='该单据对应的发票代码')
    invoice_number = fields.Char('发票号码', required=True, help='发票号码，多张发票中间用空格分开')
    real_amount = fields.Float('实际金额', digits="Price")
    real_tax = fields.Float('实际税额')
    diff_amount = fields.Float('差异金额', compute='_get_diff', digits="Price")
    diff_tax = fields.Float('差异税额', compute='_get_diff')
    invoice_date = fields.Date('开票日期', required=True,
                               default=lambda self: fields.Date.context_today(self))

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        inv_ids = self.env.context.get('active_ids')
        part_list = []
        invoice_amount = invoice_tax = 0
        for inv in self.env['tax.invoice'].search([('id', 'in', inv_ids)]):
            part_list.append(inv.partner_id.id)
            invoice_amount += inv.invoice_amount
            invoice_tax += inv.invoice_tax
        if len(set(part_list)) != 1:
            raise ValidationError('只能选择一个业务伙伴的发票输入合并开票')
        res.update({
            'partner_id': part_list[0],
            'invoice_amount': invoice_amount,
            'invoice_tax': invoice_tax,
            })
        return res
    
    @api.depends('real_amount', 'real_tax')
    def _get_diff(self):
        for s in self:
            s.diff_amount = s.real_amount - s.invoice_amount
            s.diff_tax = s.real_tax - s.invoice_tax
    
    def button_ok(self):
        if self.real_amount == 0:
            raise ValidationError('请输入发票金额')
        inv_ids = self.env.context.get('active_ids')
        invoices = self.env['tax.invoice'].search([('id', 'in', inv_ids)])
        diff = -self.diff_amount
        if diff > invoices[-1].invoice_amount:
            raise ValidationError('差异金额大于最后一张发票不含税金额，请考虑少选一些发票')
        invoices[-1].invoice_amount_add = self.diff_amount
        diff = -self.diff_tax
        if diff > invoices[-1].invoice_tax:
            raise ValidationError('差异税额大于最后一张发票税额，请考虑少选一些发票')
        invoices[-1].invoice_tax_add = self.diff_tax
        i = 0
        for inv in invoices:
            inv.invoice_code = self.invoice_code + ' '*i
            inv.invoice_number = self.invoice_number
            inv.invoice_date = self.invoice_date
            inv.tax_invoice_done()
            i += 1
