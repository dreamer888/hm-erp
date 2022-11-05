from odoo import api, fields, models, tools


class MrpOusProgressReport(models.Model):
    _name = 'mrp.ous.progress.report'
    _description = '工序委外进度分析'
    _auto = False

    
    name = fields.Char('单据号码')
    date = fields.Date('单据日期')
    user_id = fields.Many2one('res.users', '经办人')
    order_id = fields.Many2one('sell.order', '销售订单')
    plm_id = fields.Many2one('mrp.plm', '生产加工单')
    plm_qty = fields.Float('加工数量', digits='Quantity')
    mrp_proc_id = fields.Many2one('mrp.proc', '工序')
    partner_id = fields.Many2one('partner', '供应商')
    warehouse_dest_id = fields.Many2one('warehouse', '仓库')
    goods_id = fields.Many2one('goods', '商品')
    category_id = fields.Many2one('core.category', '商品类别')
    uom = fields.Char('单位', compute='_compute_uom')
    qty_task = fields.Float('委外数量', digits='Quantity')
    qty_conf = fields.Float('收货数量', digits='Quantity')
    qty_retu = fields.Float('退回数量', digits='Quantity')
    qty_receipt = fields.Float('实交数量', digits='Quantity')
    need_qc = fields.Boolean('需质检')
    qty_ok = fields.Float('合格数量', digits='Quantity')
    qty_bad = fields.Float('不良数量', digits='Quantity')
    plm_ous_qc_ids = fields.One2many('mrp.plm.ous.qc', 'plm_ous_id', readonly=True)
    state = fields.Selection([
                ('draft', '草稿'),
                ('done', '已确认'),
                ], string='状态')

    @api.depends('goods_id')
    def _compute_uom(self):
        for l in self:
            l.uom = (l.goods_id.uom_id.name if l.goods_id and l.goods_id.uom_id else '')

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, 'mrp_ous_progress_report')
        cr.execute("""
            CREATE or REPLACE VIEW mrp_ous_progress_report as(
                SELECT ous.id, ous.name, ous.date, ous.partner_id, ous.user_id, plm.order_id, ous.plm_id, plm.goods_id,plm_line.mrp_proc_id,plm_line.need_qc,
                       ous.qty_task,cf.qty_conf - rt.qty_retu qty_receipt,cf.qty_conf,rt.qty_retu,qc.qty_ok,qc.qty_bad,ous.state
                FROM mrp_plm_ous AS ous
                LEFT JOIN mrp_plm_proc_line AS plm_line ON ous.plm_proc_line_id = plm_line.id
                LEFT JOIN mrp_plm AS plm ON plm.id = ous.plm_id
                LEFT JOIN (
                    SELECT cf.plm_ous_id, SUM(cf.qty) qty_conf 
                    FROM mrp_plm_ous_conf AS cf
                    WHERE cf.state = 'done'
                    GROUP BY cf.plm_ous_id
                ) AS cf ON cf.plm_ous_id = ous.id
                LEFT JOIN (
                    SELECT rt.plm_ous_id, SUM(rt.qty) qty_retu 
                    FROM mrp_plm_ous_retu AS rt
                    WHERE rt.state = 'done'
                    GROUP BY rt.plm_ous_id
                ) AS rt ON rt.plm_ous_id = ous.id
                LEFT JOIN (
                    SELECT qc.plm_ous_id, SUM(qc.qty - coalesce(dtl.qty_bad, 0)) qty_ok, SUM(coalesce(dtl.qty_bad, 0)) qty_bad 
                    FROM mrp_plm_ous_qc AS qc
                    LEFT JOIN (
                        SELECT dtl.qc_id,SUM(dtl.qty) qty_bad FROM mrp_plm_ous_qc_line dtl
                        GROUP BY dtl.qc_id
                    )dtl on dtl.qc_id = qc.id
                    WHERE qc.state = 'done'
                    GROUP BY qc.plm_ous_id
                ) AS qc ON qc.plm_ous_id = ous.id
            )
        """)