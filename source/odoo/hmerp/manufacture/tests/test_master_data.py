from openerp.tests.common import TransactionCase
from odoo.tests.common import Form
from odoo.exceptions import ValidationError, UserError

class TestBOM(TransactionCase):
    def setUp(self):
        super(TestBOM, self).setUp()
        self.bom = self.env.ref('manufacture.ballpen_bom')

    def test_main(self):
        '''BOM处理主流程'''
        #审核BOM
        self.bom.mrp_bom_done()
        #反审核BOM
        self.bom.mrp_bom_draft()
        # 计算字段
        self.assertEqual(len(self.bom.mrp_proc_ids), 2)
        # 测试onchange
        with Form(self.bom) as new_bom:
            new_bom.goods_id = self.env.ref('goods.mouse')
            new_bom.goods_id = self.env.ref('manufacture.ballpen')
        with Form(self.bom).line_ids.new() as new_line:
            new_line.warehouse_id = self.env.ref('warehouse.sh_stock')
            new_line.goods_id = self.env.ref('manufacture.ballpen_refill')
        with Form(self.bom).line_ids.new() as new_line:
            new_line.warehouse_id = self.env.ref('warehouse.sh_stock')
            new_line.bom_id = self.bom
        with Form(self.bom).line_proc_ids.new() as new_proc:
            new_proc.get_way = 'ous'
            new_proc.get_way = 'self'
            new_proc.mrp_proc_id = self.env.ref('manufacture.main_proc')
        # 复制bom
        res_action = self.bom.button_copy_bom()
        wizard = self.env[res_action.get('res_model')].with_context(
            {'bom_id':self.bom.id,
             'goods_id':self.bom.goods_id.id
             }).create(
            {'goods_id':self.bom.goods_id.copy({'name':self.bom.goods_id.name + '_cp'}).id})
        wizard.do_confirm()