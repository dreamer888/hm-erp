
from odoo import fields, models, api
from odoo.exceptions import UserError


class MoneyInvoice(models.Model):
    _inherit = 'money.invoice'

    tax_invoice_id = fields.Many2one('tax.invoice', string='发票号',
                                     readonly=True,
                                     help='结算单对应的发票')

    def _get_tax_invoice_line(self, line):
        '''返回发票单行'''
        return {
            'goods_id': line.goods_id.id,
            'goods_name': line.goods_id.name,
            'quantity': line.goods_qty,
            'uom': line.uom_id.name,
            'price': line.price,
            'tax_rate': line.tax_rate,
            'amount': line.amount,
            'tax': line.tax_amount
        }

    def _get_tax_invoice_line_neg(self, line):
        '''返回负数发票单行'''
        return {
            'goods_id': line.goods_id.id,
            'goods_name': line.goods_id.name,
            'quantity': -line.goods_qty,
            'uom': line.uom_id.name,
            'price': line.price,
            'tax_rate': line.tax_rate,
            'amount': -line.amount,
            'tax': -line.tax_amount
        }

    def _generate_tax_invoice(self, new_id):
        '''返回创建 tax_invoice 时所需数据'''
        tax_invoice_lines = []  # 发货单行
        if new_id.category_id.type != 'income':
            delivery_or_receipt = self.env['buy.receipt'].search(
                [('name', '=', new_id.name)])
            invoice_type = 'in'
            if delivery_or_receipt:
                for line in delivery_or_receipt.line_in_ids:
                    tax_invoice_lines.append(
                        self._get_tax_invoice_line(line))
                for line in delivery_or_receipt.line_out_ids:  # 采购退货单
                    tax_invoice_lines.append(
                        self._get_tax_invoice_line_neg(line))
            else:
                outsource = self.env['outsource'].search(
                    [('name', '=', new_id.name)])
                if outsource:
                    tax_invoice_lines.append({
                        'goods_id': outsource.line_in_ids[0].goods_id.id,
                        'goods_name': '委托加工费',
                        'quantity': outsource.line_in_ids[0].goods_qty,
                        'uom': '套',
                        'price': outsource.line_in_ids[0].goods_qty and round(((outsource.outsource_fee - outsource.tax_amount) / outsource.line_in_ids[0].goods_qty),2),
                        'tax_rate': round(outsource.tax_amount*100/(outsource.outsource_fee - outsource.tax_amount)),
                        'amount': outsource.outsource_fee - outsource.tax_amount,
                        'tax': outsource.tax_amount
                    })
        else:
            delivery_or_receipt = self.env['sell.delivery'].search(
                [('name', '=', new_id.name)])
            invoice_type = 'out'
            for line in delivery_or_receipt.line_out_ids:
                tax_invoice_lines.append(
                    self._get_tax_invoice_line(line))
            for line in delivery_or_receipt.line_in_ids:   # 销售退货单
                tax_invoice_lines.append(
                    self._get_tax_invoice_line_neg(line))

        my_company = new_id.create_uid.company_id
        if not my_company.vat or not my_company.company_registry or not my_company.bank_account_id.num:
            raise UserError('公司的注册地址 税号 开户行账户，不能为空')
        if tax_invoice_lines:
            tax_invoice_id = self.env['tax.invoice'].create({
                'name': new_id.name,
                'partner_id': new_id.partner_id.id,
                'partner_code': new_id.partner_id.tax_num,
                'partner_address': new_id.partner_id.main_address,
                'partner_bank_number':
                    (new_id.partner_id.bank_name + new_id.partner_id.bank_num),
                'order_id': delivery_or_receipt.order_id.name,
                'partner_order': delivery_or_receipt.ref,
                'catagory': new_id.partner_id.tax_catagory,
                'invoice_amount': (new_id.amount - new_id.tax_amount),
                'invoice_tax': new_id.tax_amount,
                'invoice_subtotal': new_id.amount,
                'money_invoice_id': new_id.id,
                'invoice_type': invoice_type,
                'my_company_name': my_company.name,
                'my_company_code': my_company.vat,
                'my_company_address': my_company.company_registry,
                'my_company_bank_number': my_company.bank_account_id.name +
                my_company.bank_account_id.num
            })
            tax_invoice_id.write({'line_ids': [
                (0, 0, line) for line in tax_invoice_lines]})
            new_id.tax_invoice_id = tax_invoice_id

    @api.model
    def create(self, values):
        """
        创建结算单时，创建对应的税务发票。
        """
        new_id = super(MoneyInvoice, self).create(values)
        self._generate_tax_invoice(new_id)
        return new_id

    def unlink(self):
        """
        删除已生成的税务发票
        """
        if self.tax_invoice_id:
            self.tax_invoice_id.state = 'draft'
            self.tax_invoice_id.unlink()

        return super(MoneyInvoice, self).unlink()
