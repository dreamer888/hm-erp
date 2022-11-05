from odoo import api, fields, models
from odoo.exceptions import UserError


class MrpProc(models.Model):
    _name = "mrp.proc"
    _description = "工艺资料"
    code = fields.Char('代号', required=True, index=True)
    name = fields.Char('名称', required=True, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心', required=False)
    mrp_proc_type_id = fields.Many2one('mrp.proc.type', '工序类别', index=True, ondelete='cascade')
    mrp_proc_class_id = fields.Many2one('mrp.proc.class', '工序等级', index=True, ondelete='cascade')
    proc_ctl = fields.Boolean('工序控制', default=0, help='勾选后，转下工序的可报工数，为当前工序的有效完工数(有效完工数：无质检时为报工数，否则为质检合格数)')
    need_qc = fields.Boolean('需检验', default=0)
    qc_department_id = fields.Many2one('staff.department', '质检部门', index=True, ondelete='cascade')

    get_way = fields.Selection([('self', '自制'), ('ous', '委外')],
                               '获取方式', required=True, default='self')
    sub_remark = fields.Char('作业描述', default='')
    rate_waste = fields.Float('损耗率')
    time_uom = fields.Selection([('s', '秒'), ('m', '分钟'), ('h', '小时')],
                                '时间单位', required=False, default='s')
    pre_time = fields.Float('准备时间')
    work_time = fields.Float('耗用工时')
    price_std = fields.Float('标准工价')
    price = fields.Float('加工工价')
    remark = fields.Char('备注', default='')

    def name_get(self):
        '''在many2one字段里显示 编号_名称'''
        res = []

        for proc in self:
            res.append((proc.id, proc.code and (
                proc.code + '_' + proc.name) or proc.name))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        '''在many2one字段中支持按编号搜索'''
        args = args or []
        code_search_proc = []
        if name:
            proc_id = self.search([('code','=',name)])
            if proc_id:
                return proc_id.name_get()
            args.append(('code', 'ilike', name))
            proc_ids = self.search(args)
            if proc_ids:
                code_search_proc = proc_ids.name_get()

            args.remove(('code', 'ilike', name))
        search_proc = super().name_search(name=name, args=args,
                                              operator=operator, limit=limit)
        for good_tup in code_search_proc:
            if good_tup not in search_proc:
                search_proc.append(good_tup)
        return search_proc