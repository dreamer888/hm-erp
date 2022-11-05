from odoo import fields, models, tools, api
import time


class MrpPlmProgressReport(models.Model):
    _name = 'mrp.plm.progress.report'
    _description = '生产进度分析'
    _auto = False

    
    plm_id = fields.Many2one('mrp.plm', '生产加工单')
    name = fields.Char('加工单号')
    date = fields.Date('单据日期')
    type = fields.Selection([('work', '生产加工'), ('rework', '生产返工')], '类型')
    partner_id = fields.Many2one('partner', '客户')
    user_id = fields.Many2one('res.users', '经办人')
    order_id = fields.Many2one('sell.order', '销售订单')
    is_close = fields.Boolean('生产结案')
    goods_id = fields.Many2one('goods', '商品')
    category_id = fields.Many2one('core.category', '商品类别')
    delivery_date = fields.Date('预完工日期')
    qty = fields.Float('生产数量', digits='Quantity')
    qty_cons = fields.Float('领料套数', digits='Quantity')
    qty_in = fields.Float('入库数量', digits='Quantity')
    uom = fields.Char('单位', compute='_compute_uom')
    mrp_proc_id = fields.Many2one('mrp.proc', '工序')
    task_id = fields.Integer('生产任务id')
    task_name = fields.Char('生产任务')   
    task_type = fields.Selection([
        ('ous', '委外'),
        ('self', '自制')], default='self',string='任务类型')    
    buy_partner_id = fields.Many2one('partner', '供应商')
    task_state = fields.Selection([
        ('draft', '草稿'),
        ('ready', '就绪'),
        ('pause', '暂停'),
        ('progress', '进行中'),
        ('done', '已完成'),
        ('cancel', '已取消'),
        ('ous', '委外中'),
        ('ous_pen', '待委外')], string='任务状态')
    qty_task = fields.Float('计划数量', digits='Quantity')
    qty_conf = fields.Float('完工数量', digits='Quantity')
    conf_date = fields.Date('完工日期')
    need_qc = fields.Boolean('需质检')
    qty_ok = fields.Float('合格数量', digits='Quantity')
    qty_bad = fields.Float('不良数量', digits='Quantity')
    state = fields.Selection([
                ('draft', '草稿'),
                ('done', '已确认'),
                ], string='状态')
    """
    @api.depends('plm_ous_qc_ids')
    def _compute_bad_info(self):
        for v in self:
            ids = []
            vl = {'col':[],'val':[]}
            vl['col'] = ['不良原因','','数量','','处理方式']
            for l in v.plm_ous_qc_ids:
                for l1 in l.line_ids:
                    vl['val'].append([l1.mrp_proc_cause_id.name, l1.qty, l1.disposal_mode])
                    ids.append(l1)
            v.bad_info = self.env.company._get_html_table(vl)
            v.plm_ous_qc_bad_ids = ids
    """    
    @api.depends('goods_id')
    def _compute_uom(self):
        for l in self:
            l.uom = (l.goods_id.uom_id.name if l.goods_id and l.goods_id.uom_id else '')

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, 'mrp_plm_progress_report')
        cr.execute("""
            CREATE or REPLACE VIEW mrp_plm_progress_report as(
                SELECT plm_line.id, plm.name, plm.type, plm.date, plm.partner_id, plm.user_id, plm.order_id, plm.is_close, plm.goods_id, gd.category_id,
                       plm.delivery_date, plm.qty, cons.qty_cons, plm_in.qty_in, plm_line.mrp_proc_id,plm_proc.buy_partner_id,plm_proc.task_state,
                       plm_proc.qty_task,plm_proc.qty_conf, plm_proc.conf_date,plm_line.need_qc,qc.qty_ok,qc.qty_bad,plm.state,
                       plm_proc.task_id,plm_proc.task_name,plm_proc.task_type,plm_line.plm_id
                FROM mrp_plm AS plm
                LEFT JOIN mrp_plm_proc_line AS plm_line ON plm.id = plm_line.plm_id
                LEFT JOIN goods AS gd ON gd.id = plm.goods_id
                LEFT JOIN (
                    SELECT ous.id AS task_id,ous.name AS task_name,'ous' task_type,ous.partner_id AS buy_partner_id,
                           case when ous.state = 'done' then 'ous' else 'ous_pen' end AS task_state,
                           ous.plm_proc_line_id, ous.qty_task, SUM(COALESCE(cf.qty,0)) AS qty_conf, MAX(cf.date) conf_date 
                    FROM mrp_plm_ous AS ous 
                    LEFT JOIN (
                        SELECT cf.plm_ous_id,cf.qty, cf.date from mrp_plm_ous_conf AS cf
                        WHERE cf.state = 'done'
                        union all
                        SELECT cf.plm_ous_id,-cf.qty, null from mrp_plm_ous_retu AS cf
                        WHERE cf.state = 'done'
                    ) AS cf on cf.plm_ous_id = ous.id
                    GROUP BY ous.id,ous.name,ous.partner_id,ous.plm_proc_line_id, ous.qty_task
                    union all
                    SELECT tk.id, tk.name,'self' task_type, CAST(null as int) partner_id, tk.state,
                           tk.plm_proc_line_id, tk.qty_task, SUM(COALESCE(cf.qty,0)) AS qty_retu, MAX(cf.date) conf_date 
                    FROM mrp_plm_task AS tk
                    LEFT JOIN mrp_plm_task_conf AS cf on tk.id = cf.plm_task_id and cf.state = 'done'
                    GROUP BY tk.id, tk.name, tk.state, tk.plm_proc_line_id, tk.qty_task
                ) AS plm_proc ON plm_line.id = plm_proc.plm_proc_line_id
                LEFT JOIN (
                    SELECT qc.plm_proc_line_id, SUM(COALESCE(qc.qty_ok, 0)) AS qty_ok, SUM(COALESCE(qc.qty_bad, 0)) AS qty_bad 
                    FROM (
                        SELECT qc.plm_proc_line_id, qc.qty - SUM(COALESCE(dtl.qty,0)) AS qty_ok, qc.qty - SUM(COALESCE(dtl.qty,0)) AS qty_bad 
                        FROM mrp_plm_task_qc AS qc, mrp_plm_task_qc_line AS dtl
                        WHERE dtl.qc_id = qc.id and qc.state = 'done'
                        GROUP BY qc.plm_proc_line_id,qc.qty
                        union all
                        SELECT qc.plm_proc_line_id, qc.qty - SUM(COALESCE(dtl.qty,0)) AS qty_ok, qc.qty - SUM(COALESCE(dtl.qty,0)) AS qty_bad 
                        FROM mrp_plm_ous_qc AS qc, mrp_plm_ous_qc_line AS dtl
                        WHERE dtl.qc_id = qc.id and qc.state = 'done'
                        GROUP BY qc.plm_proc_line_id,qc.qty
                    ) AS qc
                    GROUP BY qc.plm_proc_line_id
                ) AS qc ON qc.plm_proc_line_id = plm_line.id
                LEFT JOIN(
                    SELECT line.plm_id, min(COALESCE(cons.qty_cons,0)
                                            * CASE WHEN COALESCE(line.radix,0) > 0 THEN line.radix ELSE 1 end 
                                            / CASE WHEN COALESCE(line.qty_bom,0) > 0 THEN line.qty_bom ELSE 1 END
                                        ) AS qty_cons
                    FROM mrp_plm_line AS line
                    LEFT JOIN (
                        SELECT dtl.plm_line_id, SUM(COALESCE(dtl.goods_qty,0)) AS qty_cons FROM(
                            SELECT B.plm_line_id, B.goods_qty
                            FROM mrp_plm_cons AS H,wh_move AS wh,wh_move_line AS B
                            WHERE H.mrp_plm_cons_id = wh.id and wh.id = B.move_id and wh.state = 'done'
                            union all
                            SELECT B.plm_line_id, -B.goods_qty
                            FROM mrp_plm_cons_retu AS H,wh_move AS wh,wh_move_line AS B
                            WHERE H.mrp_plm_cons_retu_id = wh.id and wh.id = B.move_id and wh.state = 'done'
                        ) AS dtl
                        GROUP BY dtl.plm_line_id
                    ) AS cons on cons.plm_line_id = line.id
                    GROUP BY line.plm_id
                ) AS cons ON cons.plm_id = plm.id
                LEFT JOIN(
                    SELECT H.plm_id, SUM(B.goods_qty) AS qty_in
                    FROM mrp_plm_in AS H, wh_move AS wh,wh_move_line AS B
                    WHERE H.mrp_plm_in_id = wh.id and wh.id = B.move_id and wh.state = 'done'
                    GROUP BY H.plm_id
                ) AS plm_in ON plm_in.plm_id = plm.id
            )
        """)
        
    def view_plm(self):
        '''查看单据内容'''
        self.ensure_one()
        plm_id = self.plm_id.id
        action = {
            'name': '生产加工单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm',
            'view_id': False,
            'target': 'current',
        }
        view_id = self.env.ref('lexin_mrp.mrp_plm_form').id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = plm_id
        return action

    def view_order(self):
        '''查看单据内容'''
        self.ensure_one()
        order_id = self.order_id.id
        action = {
            'name': '销售订单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sell.order',
            'view_id': False,
            'target': 'current',
        }
        view_id = self.env.ref('sell.sell_order_form').id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = order_id
        return action

    def view_task(self):
        '''查看单据内容'''
        self.ensure_one()
        task_id = self.task_id
        task_type = self.task_type
        name = '生产任务'
        res_model ='mrp.plm.task'
        view_name = 'lexin_mrp.mrp_plm_task_form'
        if task_type == 'ous':
            name = '工序委外'
            res_model ='mrp.plm.ous'
            view_name = 'lexin_mrp.mrp_plm_ous_form'

        action = {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': res_model,
            'view_id': False,
            'target': 'current',
        }
        view_id = self.env.ref(view_name).id
        action['views'] = [(view_id, 'form')]
        action['res_id'] = task_id
        return action