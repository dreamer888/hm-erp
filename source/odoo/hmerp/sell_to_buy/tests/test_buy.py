from odoo.tests.common import TransactionCase


class TestBuy(TransactionCase):

    def setUp(self):
        super(TestBuy, self).setUp()
        self.order = self.env.ref('buy.buy_order_1')
        self.sell_order = self.env.ref('sell.sell_order_1')
        self.sell_order.sell_order_done()

    def test_sell_to_buy(self):
        '''根据销售订单生成采购订单'''
        res = self.order.sell_to_buy()
        self.assertEqual(res['res_model'], 'sell.to.buy.wizard')

    def test_buy_order_line_unlink(self):
        '''删除采购订单行时，如果对应销售订单行已采购，则去掉打勾'''
        wizard = self.env['sell.to.buy.wizard'].with_context({'active_id': self.order.id}).create(
            {'sell_line_ids': [(6, 0, [l.id for l in self.sell_order.line_ids])]})
        wizard.button_ok()
        for line in self.order.line_ids:
            if line.sell_line_id:
                line.unlink()
