from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests.common import Form


class TestWizard(TransactionCase):
    ''' 测试分次报工向导 '''

    def setUp(self):
        ''' 准备组装单 '''
        super().setUp()
        self.bom = self.env.ref('warehouse.wh_bom_0').copy(
            {'type': 'assembly'})
        self.env.ref('goods.mouse').using_batch = False
        self.env.ref('goods.mouse').force_batch_one = False
        wh = self.env.ref('warehouse.hd_stock')
        self.ass = self.env['wh.assembly'].create({
            'bom_id': self.bom.id,
            'goods_qty': 2,
            'warehouse_id': wh.id,
            'warehouse_dest_id': wh.id,
        })
        self.ass.onchange_goods_qty()
        self.overage_in = self.browse_ref('warehouse.wh_in_whin0')
        self.overage_in.approve_order()
        for l in self.env['wh.move.line'].search([]):
            l.read()

    def test_normal(self):
        ''' 报工3个中的1个 '''
        ctx = {
            'active_model': self.ass._name,
            'active_ids': [self.ass.id]
        }
        wiz = self.env['wh.produce.wizard'].with_context(ctx).create({})
        wiz_form = Form(wiz)
        wiz_form.qty = 1
        with wiz_form.line_in_ids.edit(0) as line_form:
            line_form.location_id = self.env.ref("warehouse.a001_location")
        res = wiz_form.save()
        res.button_ok()

        wiz = self.env['wh.produce.wizard'].with_context(ctx).create({})
        wiz_form.qty = 1
        with wiz_form.line_in_ids.edit(0) as line_form:
            line_form.location_id = self.env.ref("warehouse.a001_location")
        res = wiz_form.save()
        res.button_ok()

    def test_exceptions(self):
        ''' 报工数量为0报错 '''
        ctx = {
            'active_model': self.ass._name,
            'active_ids': [self.ass.id]
        }
        wiz = self.env['wh.produce.wizard'].with_context(ctx).create({
            'qty': 0,
        })
        with self.assertRaises(UserError):
            wiz.button_ok()
