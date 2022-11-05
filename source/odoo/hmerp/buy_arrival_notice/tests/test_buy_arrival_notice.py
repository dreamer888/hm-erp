from openerp.tests.common import TransactionCase
from odoo.tests.common import Form
from odoo.exceptions import ValidationError, UserError


class TestArrivalNotice(TransactionCase):
    def setUp(self):
        super(TestArrivalNotice, self).setUp()
        self.env.ref('buy.buy_order_1').buy_order_done()
        self.buy_notice = self.env['arrival.notice'].create(
            {
                'vendor_id': self.env.ref('core.lenovo').id,
            }
        )
    
        self.buy_notice.onchange_vendor_id()



    def test_main(self):
        #确认采购到货通知单
        self.buy_notice.notice_done()
        #撤销确认的到货通知单
        self.buy_notice.notice_draft()

    def test_name_search(self):
        # 使用订单号来搜索采购订单明细行
        result = self.env['buy.order.line'].name_search(self.env.ref('buy.buy_order_1').name)
        real_result = [(self.env.ref('buy.buy_order_line_1').id,
                        self.env.ref('buy.buy_order_1').name
                        + '_'
                        + self.env.ref('goods.keyboard').name)]

        self.assertEqual(result, real_result)
        # 使用空值来搜索采购订单明细行
        result = self.env['buy.order.line'].name_search()
        
    def test_error(self):
        #测试存在此供应商未确认的到货通知单
        buy_notice_another = self.env['arrival.notice'].create(
            {
                'vendor_id': self.env.ref('core.lenovo').id,
            }
        )
        
        buy_notice_another.onchange_vendor_id()
        #重复确认采购到货通知单
        self.buy_notice.notice_done()
        with self.assertRaises(UserError):
            self.buy_notice.notice_done()
        #确认一个没有明细行的通知单
        with self.assertRaises(UserError):
            buy_notice_another.notice_done()
        #重复撤销确认的到货通知单
        self.buy_notice.notice_draft()
        with self.assertRaises(UserError):
            self.buy_notice.notice_draft()
        #添加重复的采购单行
        # with self.assertRaises(ValidationError):
        #     self.env['arrival.notice.line'].create({
        #         'notice_id':self.buy_notice.id,
        #         'buy_line_id':self.buy_notice.line_ids[0].buy_line_id.id,
        #     })
        #新增一个通知单行选择已经收完货的采购单行
