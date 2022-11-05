from openerp.tests.common import TransactionCase
from odoo.tests.common import Form
from odoo.exceptions import ValidationError, UserError


class TestDeliveryNotice(TransactionCase):
    def setUp(self):
        super(TestDeliveryNotice, self).setUp()
        # 准备订单
        self.env.ref('sell.sell_order_2').sell_order_done()
        # 准备库存
        self.warehouse_obj = self.env.ref('warehouse.wh_in_whin0')
        self.warehouse_obj.approve_order()
        for l in self.env['wh.move.line'].search([]):
            l.read()
        # 创建发货通知单
        self.del_notice = self.env['delivery.notice'].create(
            {
                'custom_id': self.env.ref('core.jd').id,
            }
        )
    
        self.del_notice.onchange_custom_id()



    def test_main(self):
        #确认发货通知单
        self.del_notice.delivery_notice_done()
        #撤销确认发货通知单
        self.del_notice.delivery_notice_draft()

    def test_name_search(self):
        # 使用订单号来搜索采购订单明细行
        result = self.env['sell.order.line'].name_search(self.env.ref('sell.sell_order_2').name)
        real_result = [(self.env.ref('sell.sell_order_line_2_3').id,
                        self.env.ref('sell.sell_order_2').name
                        + '_'
                        + self.env.ref('goods.cable').name)]

        self.assertEqual(result, real_result)
        # 使用空值来搜索采购订单明细行
        result = self.env['sell.order.line'].name_search()
        
    def test_error(self):
        #测试存在此客户未确认的发货通知单
        sell_notice_another = self.env['delivery.notice'].create(
            {
                'custom_id': self.env.ref('core.jd').id,
            }
        )
        
        sell_notice_another.onchange_custom_id()
        # 重复确认销售发货通知单
        self.del_notice.delivery_notice_done()
        with self.assertRaises(UserError):
            self.del_notice.delivery_notice_done()
        # 确认一个没有明细行的通知单
        with self.assertRaises(UserError):
            sell_notice_another.delivery_notice_done()
        # 重复撤销确认的发货通知单
        self.del_notice.delivery_notice_draft()
        with self.assertRaises(UserError):
            self.del_notice.delivery_notice_draft()
