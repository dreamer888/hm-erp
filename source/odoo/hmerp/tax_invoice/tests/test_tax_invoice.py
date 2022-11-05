from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestTaxInvoice(TransactionCase):
    def setUp(self):
        super(TestTaxInvoice, self).setUp()
        self.order = self.env.ref('buy.buy_order_1')
        self.order.buy_order_done()
        self.receipt = self.env['buy.receipt'].search(
            [('order_id', '=', self.order.id)])
        self.env.ref('core.comm').num = '012345678923456'
        self.env.user.company_id.vat = '922T'
        self.env.user.company_id.company_registry = '金海路2588弄'
        self.env.user.company_id.bank_account_id = self.env.ref('core.comm')
        # 收货后生成采购税务发票
        self.receipt.buy_receipt_done()
        #把移库单读一遍，不然不会触发库存的计算字段，造成库存不更新，无法出货
        for line in self.env['wh.move.line'].search([]):
            line.read()           
        self.sellorder = self.env.ref('tax_invoice.sell_order_1')
        self.sellorder.sell_order_done()

        self.delivery = self.env['sell.delivery'].search(
            [('order_id', '=', self.sellorder.id)])          

    def test_buy_tax_invoice(self):
        """ 采购税务发票的生成、提交和开具 """
        # 创建时发票的状态应该草稿
        tax_invoice = self.receipt.invoice_id.tax_invoice_id        
        self.assertEqual(tax_invoice.state, 'draft')
        self.assertEqual(tax_invoice.invoice_type, 'in')
        tax_invoice.tax_invoice_submit()
        att_count = tax_invoice.attachment_number
        tax_invoice.action_get_attachment_view()
        tax_invoice.invoice_number = '12345678 23456789'
        tax_invoice.invoice_date = '2020-01-01'
        tax_invoice.tax_invoice_done()

    def test_unlink(self):
        '''取消收货后采购税务发票被删除'''
        self.receipt.buy_receipt_draft()

    def test_sell_tax_invoice(self):    
        '''测试销售发票的生成、提交和开具'''          
        # 通过确认delivery创建销售发票
        self.delivery.sell_delivery_done()
        tax_invoice = self.delivery.invoice_id.tax_invoice_id

        # 公司的 draft_invoice参数设置，创建的结算单应为草稿
        self.assertEqual(self.delivery.invoice_id.state, 'draft')

        # 创建时发票的状态应该草稿
        self.assertEqual(tax_invoice.state, 'draft')
        self.assertEqual(tax_invoice.invoice_type, 'out')

        # 发票行不能为空
        self.assertTrue(tax_invoice.line_ids)

        # 测试申请开票
        tax_invoice.tax_invoice_submit()
        self.assertEqual(tax_invoice.state, 'submit')

        # 写入发票号码 开票日期
        tax_invoice.invoice_number = '12345678 23456789'
        tax_invoice.invoice_date = '2020-01-01'
        tax_invoice.tax_invoice_done()
        self.assertEqual(tax_invoice.state, 'done')

        # 发票done后检查结算单的状态 发票号 发票日期
        self.assertEqual(self.delivery.invoice_id.state, 'done')
        self.assertEqual(self.delivery.invoice_id.bill_number, tax_invoice.invoice_number)
        self.assertEqual(self.delivery.invoice_id.invoice_date, tax_invoice.invoice_date)        

        # 重复done
        with self.assertRaises(UserError):
            tax_invoice.tax_invoice_done()


        
    def test_tax_invoice_create_company_vat_error(self):   
        '''测试税号不能为空'''
        self.env.user.company_id.vat = ''
        with self.assertRaises(UserError):
            self.delivery.sell_delivery_done()   

    def test_tax_invoice_create_company_registry_error(self):  
        '''测试注册地不能为空'''
        self.env.user.company_id.company_registry = ''
        with self.assertRaises(UserError):
            self.delivery.sell_delivery_done() 

    def test_tax_invoice_create_company_account_num_error(self):  
        '''测试银行账号不能为空'''
        self.env.ref('core.comm').num = ''
        with self.assertRaises(UserError):
            self.delivery.sell_delivery_done()            

    def test_tax_invoice_num_none_error(self):    
        '''检查发票号码不能为空'''          
        self.delivery.sell_delivery_done()
        tax_invoice = self.delivery.invoice_id.tax_invoice_id
        tax_invoice.tax_invoice_submit()
        tax_invoice.invoice_number = ''
        tax_invoice.invoice_date = '2020-01-01'
        with self.assertRaises(UserError):
            tax_invoice.tax_invoice_done()

    def test_tax_invoice_num_8digits_error(self):    
        '''检查发票号码应为8位'''
        self.delivery.sell_delivery_done()
        tax_invoice = self.delivery.invoice_id.tax_invoice_id
        tax_invoice.tax_invoice_submit()
        tax_invoice.invoice_number = '3456789'
        tax_invoice.invoice_date = '2020-01-01'
        with self.assertRaises(UserError):
            tax_invoice.tax_invoice_done()

    def test_tax_invoice_multi_num_8digits_error(self):  
        '''多张票时,检查发票号码应为8位'''
        self.delivery.sell_delivery_done()
        tax_invoice = self.delivery.invoice_id.tax_invoice_id
        tax_invoice.tax_invoice_submit()
        tax_invoice.invoice_number = '12345678 3456789'
        tax_invoice.invoice_date = '2020-01-01'
        with self.assertRaises(UserError):
            tax_invoice.tax_invoice_done()

    def test_tax_invoice_date_none_error(self):
        '''检查开票日期不能为空'''
        self.delivery.sell_delivery_done()
        tax_invoice = self.delivery.invoice_id.tax_invoice_id
        tax_invoice.tax_invoice_submit()
        tax_invoice.invoice_number = '12345678 23456789'
        tax_invoice.invoice_date = ''
        with self.assertRaises(UserError):
            tax_invoice.tax_invoice_done()
