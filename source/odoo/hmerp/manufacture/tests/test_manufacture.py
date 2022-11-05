from openerp.tests.common import TransactionCase
from odoo.tests.common import Form
from odoo.exceptions import ValidationError, UserError

class TestManufacture(TransactionCase):
    def setUp(self):
        super(TestManufacture, self).setUp()
        
        self.sell_order = self.env.ref('manufacture.sell_order_mrp')
        # 准备原材料库存
        other_in = self.env['wh.in'].create(
            {
                'warehouse_id': self.env.ref('warehouse.warehouse_others').id,
                'warehouse_dest_id': self.env.ref('warehouse.sh_stock').id,
                'type': 'inventory',
                'line_in_ids': [
                    (0, 0, {
                        'goods_id': self.env.ref('manufacture.ballpen_tube').id,
                        'goods_qty': 100,
                    }),
                    (0, 0, {
                        'goods_id': self.env.ref('manufacture.ballpen_refill').id,
                        'goods_qty': 100,
                    }),
                ]
            }
        )
        other_in.approve_order()
        for l in self.env['wh.move.line'].search([]):
            l.read()
    def test_main(self):
        """ 完整的生产流程 """
        # 确认销售订单
        # 客户采购10支圆珠笔
        self.sell_order.sell_order_done()
        self.sell_order.action_view_mrp_plan()
        # 找到生成的计划
        plan = self.sell_order.mrp_plan_ids
        # 执行分析
        plan.button_plan()
        # 产生建议
        plan.button_proposal()
        # 确认计划
        plan.read()
        plan.button_done()
        plan.action_view_buy_order_task()
        plan.action_view_mrp_plm()
        # 计划生成的生产订单
        plm = plan.mrp_plm_ids
        plm.default_get(['warehouse_id'])  # 测试字段 default 方法
        plm.read()                         # 测试字段 compute 方法
        plm.button_done()
        # 投料
        cons = plm.plm_cons_ids
        cons.button_done()
        # 生产订单生成的委外任务单，第一道工序的【制作笔芯】
        ous = plm.plm_ous_ids
        ous.partner_id = self.env.ref('core.lenovo')
        ous.read()
        ous.button_done()
        # 委外收货
        ous_conf = ous.plm_ous_conf_ids
        ous_conf.read()
        ous_conf.button_done()
        # 委外质检
        ous_conf.action_view_plm_ous_qc()
        ous_qc = ous_conf.plm_ous_qc_ids
        # 用户输入质检行
        self.env['mrp.plm.ous.qc.line'].create(
            {'qc_id': ous_qc.id,
             'qty': 2,
             'disposal_mode': 'retu',
            }
        )
        ous_qc.read()
        ous_qc.button_done()
        ous_qc.action_view_plm_ous_defectdealing()
        deal = ous_qc.plm_ous_dealing_ids
        deal.button_done()
        deal.action_view_plm()
        deal.action_view_plm_task()
        deal.action_view_plm_ous()
        deal.action_view_plm_ous_retu()
        deal.action_view_plm_scrap()
        deal.button_draft()
        # 委外退货
        #ous_conf.button_retu()
        ous_conf.action_view_plm_ous_retu()
        retu = ous_conf.plm_ous_retu_ids
        retu.read()
        retu.button_done()
        retu.button_draft()
        ous_qc.button_draft()
        ous_conf.button_draft()
        ous.action_view_plm_ous_conf()
        ous.action_view_plm_ous_retu()
        ous.action_view_plm_ous_qc()
        ous.action_view_invoice()
        # 生产订单生成的生产任务单，这里是第二道工序【组装圆珠笔】
        task = plm.plm_task_ids
        task.button_ready()
        task.button_start()
        task.button_pause()
        task.read()
        task.button_done()
        task.action_view_plm_task_conf()
        # 订单收货
        task_conf = task.task_conf_ids
        task_conf.read()
        task_conf.button_done()
        # 订单质检
        task_conf.action_view_plm_task_qc()
        task_qc = task_conf.plm_task_qc_ids
        # 用户输入质检行，2件需返工
        self.env['mrp.plm.task.qc.line'].create(
            {'qc_id': task_qc.id,
             'qty': 2,
             'disposal_mode': 'rework',
            }
        )
        task_qc.read()
        task_qc.button_done()
        task_qc.action_view_plm_task_defectdealing()
        deal = task_qc.plm_task_dealing_ids
        self.env['mrp.plm.task.defectdealing.line'].create(
            {'dealing_id': deal.id,
             'mrp_proc_id':task.mrp_proc_id.id,
            }
        )
        deal.read(['mrp_plm_ous_count',
                    'mrp_proc_id',
                    'next_mrp_proc_id'])
        deal.button_done()
        deal.action_view_mrp_plm()
        deal.action_view_mrp_plm_task()
        deal.action_view_mrp_plm_ous()
        deal.action_view_mrp_plm_scrap()
        deal.button_draft()
        task_qc.button_draft()
        task_conf.button_draft()
        # 产成品入库 为什么生产任务没完成就可以入库？
        ins = plm.plm_in_ids
        ins.button_done()
        ins.button_draft()

        # 生产补料
        cons_add = self.env['mrp.plm.cons.add'].create(
            {'plm_id': plm.id, 'line_ids': [(0, 0, {
                'warehouse_id': self.env.ref('warehouse.sh_stock').id,
                'goods_id': self.env.ref('manufacture.ballpen_tube').id,
                'uom_id': self.env.ref('core.uom_pc').id,
                'qty': 2})]})
        cons_add.button_done()
        cons_add.action_view_plm_cons()
        cons_add.button_draft()

        # 生产退料
        plm.button_retu()
        cons_retu = plm.plm_cons_retu_ids
        cons_retu.button_done()
        cons_retu.button_draft()
        cons_retu.unlink()

        # 订单相关操作
        plm.action_view_plm_in()
        plm.action_view_plm_cons()
        plm.action_view_plm_task()
        plm.action_view_plm_ous()
        plm.button_cons_add()
        plm.button_retu()
        plm.action_view_plm_cons_retu()
        plm.action_view_plm_cons_add()
        self.env['mrp.in.detial.dialog.wizard'].create({}).button_ok()
        self.env['mrp.mat.detial.dialog.wizard'].create({}).button_ok()
        self.env['mrp.ous.progress.dialog.wizard'].create({}).button_ok()
        self.env['mrp.plm.progress.dialog.wizard'].create({}).button_ok()
        # 反向操作
        cons.button_draft()
        ous.button_draft()
        task.button_draft()
        plm.button_draft()
        plan.button_draft()
        self.sell_order.sell_order_draft()

    def test_Onchange(self):
        """ 测试所有onchange """
        # 销售订单行onchange
        line = Form(self.env['sell.order.line'])
        line.goods_id = self.env.ref('manufacture.ballpen_tube')
        line.goods_id = self.env.ref('manufacture.ballpen')
        line.bom_id = self.env.ref('manufacture.ballpen_bom')

        # 计划行onchange
        form_planline = Form(self.env['mrp.plan.line'])
        form_planline.qty_set = 1
        form_planline.qty_confirm = 1

        # 生产订单onchange
        form_plm = Form(self.env['mrp.plm'])
        form_plm.goods_id = self.env.ref('manufacture.ballpen')
        form_plm.qty = 1
        form_plm.bom_id = self.env.ref('manufacture.ballpen_bom')
        with form_plm.line_ids.new() as form_plm_line:
            form_plm_line.goods_id = self.env.ref('manufacture.ballpen_tube')
            form_plm_line.uom_id = self.env.ref('core.uom_pc')
            form_plm_line.warehouse_id = self.env.ref('warehouse.sh_stock')
            form_plm_line.qty = 1
        with form_plm.line_proc_ids.new() as form_plm_proc:
            form_plm_proc.sequence = 1
            form_plm_proc.get_way = 'ous'
            form_plm_proc.mrp_proc_id = self.env.ref('manufacture.main_proc')
        
        # 工序委外价格策略onchange
        strategy = Form(self.env['ous.price.strategy'])
        strategy.bom_id = self.env.ref('manufacture.ballpen_bom')
        strategy.price = 1
        strategy.price_taxed = 1

        # 工序委外价格策略onchange
        pstrategy = Form(self.env['ous.partner.strategy'])
        pstrategy.mrp_proc_id = self.env.ref('manufacture.main_proc')

        # 工序委外onchange
        form_ous = Form(self.env['mrp.plm.ous'])
        form_ous.partner_id = self.env.ref('core.lenovo')
        form_ous.price = 1
        form_ous.qty_task = 1

        # 工序委外报工onchange
        form_ous_conf = Form(self.env['mrp.plm.ous.conf'])
        form_ous_conf.qty = 1




