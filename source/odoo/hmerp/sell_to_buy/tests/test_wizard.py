from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestSellToBuyWizard(TransactionCase):

    def setUp(self):
        super(TestSellToBuyWizard, self).setUp()
        self.order = self.env.ref('buy.buy_order_1')
        self.sell_order = self.env.ref('sell.sell_order_1')
        self.sell_line_1 = self.env.ref('sell.sell_order_line_1')
        self.sell_line_1.copy()
        self.sell_order.sell_order_done()
        self.wizard = self.env['sell.to.buy.wizard'].with_context({'active_id': self.order.id}).create({'sell_line_ids': [(4, l.id) for l in self.sell_order.line_ids]})


    def test_button_ok(self):
        '''生成按钮，复制销售订单行到采购订单中'''
        self.wizard.button_ok()
        self.assertEqual(len(self.order.line_ids), 3)
        for line in self.sell_order.line_ids:
            self.assertTrue(line.is_bought)
