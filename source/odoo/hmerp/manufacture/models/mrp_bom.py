from odoo import api, fields, models
from odoo.exceptions import UserError


# Bom确认状态可选值
MRP_BOM_STATES = [
    ('draft', '草稿'),
    ('done', '已确认')]


# 字段只读状态, 用户控制确认状态下，某些栏位只读
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class MrpBomCategory(models.Model):
    _name = 'mrp.bom.category'
    _description = 'Bom分类'
    name = fields.Char('名称', required=True)
    parent_id = fields.Many2one('mrp.bom.category',
                                '上级分类',
                                index=True,
                                ondelete='cascade')


class MrpBom(models.Model):
    _name = 'mrp.bom'
    _description = 'Bom 物料清单'

    @api.depends('goods_id', 'bom_code', 'bom_ver')
    def _compute_bom_name(self):
        for m in self:
            m.bom_name = (m.bom_code if m.bom_code else '') + ' ' + (m.goods_id.name if m.goods_id.name else '')

    bom_code = fields.Char('代号', states=READONLY_STATES,)
    bom_ver = fields.Char('版本', states=READONLY_STATES,)
    bom_name = fields.Char('名称', store=False, readonly=True, compute=_compute_bom_name)

    goods_id = fields.Many2one('goods', '商品', required=True, ondelete='restrict', states=READONLY_STATES, help='商品')

    qty = fields.Float('数量', default=1, states=READONLY_STATES, digits='Quantity')
    uom_id = fields.Many2one('uom', '单位', index=True, required=True, states=READONLY_STATES, ondelete='cascade')
    warehouse_id = fields.Many2one('warehouse', '默认仓库', required=True, ondelete='restrict',
                                   states=READONLY_STATES, help='默认的生产完工入库仓库')
    department_id = fields.Many2one('staff.department', '业务部门', index=True,
                                    states=READONLY_STATES, ondelete='cascade')
    mrp_bom_category_id = fields.Many2one('mrp.bom.category', 'Bom分类', index=True,
                                          states=READONLY_STATES, ondelete='cascade')

    remark = fields.Char('备注', Default='')

    stop_date = fields.Date('停用日期', states=READONLY_STATES,)

    state = fields.Selection(MRP_BOM_STATES, '确认状态', readonly=True,
                             help="Bom的确认状态", index=True,
                             copy=False, default='draft')

    line_ids = fields.One2many('mrp.bom.line', 'mrp_bom_id', 'Bom子件行', copy=True,
                               states=READONLY_STATES,
                               help='物料明细行，不能为空')

    line_proc_ids = fields.One2many('mrp.bom.proc.line', 'mrp_bom_id', '工艺线路明细行', copy=True,
                                    states=READONLY_STATES)
    mrp_proc_ids = fields.Many2many('mrp.proc', compute='_compute_mrp_proc_ids', store=False)

    active = fields.Boolean('启用', default=True)

    @api.depends('line_proc_ids')
    def _compute_mrp_proc_ids(self):
        for b in self:
            if len(b.line_proc_ids) > 0:
                b.mrp_proc_ids = b.line_proc_ids.mapped('mrp_proc_id')
            else:
                b.mrp_proc_ids = False

    @api.onchange('goods_id', 'bom_ver')
    def onchange_goods_id(self):
        for m in self:
            if m.goods_id and m.goods_id.uom_id:
                m.uom_id = m.goods_id.uom_id
            if m.goods_id and m.goods_id.in_warehouse_id:
                m.warehouse_id = m.goods_id.in_warehouse_id
            """Bom自动编码"""
            m.auto_code(m)

    """Bom自动编码处理"""
    def auto_code(self, m):
        if m.goods_id:
            g = self.env['goods'].search([('id', '=', m.goods_id.id)])
            if g:
                bom_code = g[0].name + ('-' + m.bom_ver if m.bom_ver else '')
                if m.bom_code != bom_code:
                    m.bom_code = bom_code

    def name_get(self):
        """
        在many2one字段里显示 名称
        """
        res = []

        for bom in self:
            res.append((bom.id, (bom.bom_name if bom.bom_name else '')))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        search_goods = []
        result = []
        args = args or []
        if 'goods_id' in super(MrpBom, self)._context.keys():
            gid = super(MrpBom, self)._context["goods_id"]
            if gid:
                args.append(['goods_id', '=', gid])
        search_goods = super().name_search(name=name, args=args, operator=operator, limit=limit)
        return search_goods

    def mrp_bom_done(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认！')
        if not self.line_ids:
            raise UserError('请输入商品明细行！')
        """检查子件Bom是否引用死循环"""
        self.check_bom_id_loop(0, self.line_ids, '')
        self._compute_down_proc()
        self._check_mat_proc()

        self.write({
            'state': 'done',
        })

    def mrp_bom_draft(self):
        self.write({
            'state': 'draft',
        })

    def button_copy_bom(self):
        self.ensure_one()        
        context = dict(self.env.context or {})
        context.update({'goods_id': self.goods_id.id})
        context.update({'bom_id': self.id})
        
        action= {
            'name': 'BOM复制',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom.copy.dialog.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context
        }

        return action

    def check_bom_id_loop(self, first_id, lines, caption):
        lines = lines or []
        caption = caption or ''
        for b in lines:
            line = self.env['mrp.bom.line'].search([('id', '=', b.id)])
            if line.bom_id:
                if first_id == 0:
                    first_id = line.mrp_bom_id.id
                if first_id == line.bom_id.id:
                    raise UserError('子件Bom %s 引用死循环，请重新录入！' % (caption + '-->' + b.goods_id.display_name))
                ls = self.env['mrp.bom.line'].search([('mrp_bom_id.id', '=', line.bom_id.id), ('bom_id', '!=', False)])
                if ls:
                    self.check_bom_id_loop(first_id, ls, caption + '-->' + b.goods_id.display_name)

    def _compute_down_proc(self):
        for b in self:
            for p in b.line_proc_ids:
                str = ''
                l = b.line_proc_ids.search([('sequence', '=', p.sequence + 1), ('mrp_bom_id', '=', p.mrp_bom_id.id)])
                if len(l):
                    p.down_id = l[0]
                else:
                    p.down_id = False

    def _check_mat_proc(self):
        for b in self:
            for l in b.line_ids:
                if l.mrp_proc_id and l.mrp_proc_id not in b.mrp_proc_ids:
                    raise UserError('领料工序 %s 未指定在工艺线路中！' % l.mrp_proc_id.name)

class MrpBomLine(models.Model):
    _name = 'mrp.bom.line'
    _description = '物料'
    _order = 'mrp_bom_id, sequence'

    @api.depends('goods_id')
    def _compute_using_attribute(self):
        """
        返回子件行中商品是否使用属性
        """
        for line in self:
            line.using_attribute = line.goods_id.attribute_ids and True or False
            
    sequence = fields.Integer('序号', help='此序号决定的工艺线路的顺序，调整后自动挂接承上工序和转下工序')
    bom_id = fields.Many2one('mrp.bom', '子件Bom', index=True, ondelete='cascade', help='子件Bom的编号')

    mrp_bom_id = fields.Many2one('mrp.bom', '母件Bom编号', index=True, copy=False, default=None,
                                 ondelete='cascade', help='关联Bom的编号')
    mrp_proc_id = fields.Many2one('mrp.proc', '领料工序', ondelete='cascade', help='绑定当前工艺线路的工序')
    goods_id = fields.Many2one('goods', '商品', required=True, ondelete='restrict', help='商品')
    using_attribute = fields.Boolean('使用属性', compute=_compute_using_attribute, help='商品是否使用属性')
    attribute_id = fields.Many2one('attribute', '属性', ondelete='restrict',
                                   domain="[('goods_id', '=', goods_id)]",
                                   help='商品的属性，当商品有属性时，该字段必输')
    uom_id = fields.Many2one('uom', '单位', required=True, ondelete='restrict', help='商品计量单位')
    warehouse_id = fields.Many2one('warehouse', '默认发料库', required=True, ondelete='restrict',
                                   help='生产领料默认从该仓库调出')    
    get_way = fields.Selection([
        ('self', '自制'),
        ('ous', '委外'),
        ('po', '采购'),
    ], default='self', string='获取方式')
    qty = fields.Float('数量', default=1, required=True, digits='Quantity', help='下单数量')
    radix = fields.Float('基数', default=1, digits='Quantity')
    rate_waste = fields.Float('损耗率(%)', digits='Quantity')
    remark = fields.Char('备注', Default='')

    @api.onchange('goods_id')
    def onchange_goods_id(self):
        for l in self:
            if l.goods_id and l.goods_id.uom_id:
                l.uom_id = l.goods_id.uom_id
            if l.goods_id and l.goods_id.out_warehouse_id:
                l.warehouse_id = l.goods_id.out_warehouse_id
            if l.goods_id:
                l.get_way = l.goods_id.get_way
                bom = self.env['mrp.bom'].search([('goods_id', '=', l.goods_id.id)])
                if bom and len(bom) > 0:
                    l.bom_id = bom[0].id

    @api.onchange('bom_id')
    def onchange_bom_id(self):
        for l in self:
            if l.bom_id and not l.goods_id:
                l.goods_id = l.bom_id.goods_id


class MrpBomProcLine(models.Model):
    _name = "mrp.bom.proc.line"
    _description = "工艺线路"
    _order = 'mrp_bom_id, sequence'

    @api.depends('down_id')
    def _compute_down(self):
        for cur_l in self:
            search_l = self.search([('id', '=', cur_l.down_id.id), ('mrp_bom_id', '=', cur_l.mrp_bom_id.id)])
            if len(search_l) > 0:
                cur_l.down = search_l[0].mrp_proc_id.name
            else:
                cur_l.down = False

    mrp_bom_id = fields.Many2one('mrp.bom', '母件Bom编号', index=True, copy=False, default=None, ondelete='cascade',
                                 help='关联Bom的编号')
    sequence = fields.Integer('序号', help='此序号决定的工艺线路的顺序，调整后自动挂接承上工序和转下工序')
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', required=True, ondelete='cascade')
    down = fields.Char('转下工序', compute=_compute_down, readolny=True)
    down_id = fields.Many2one('mrp.bom.proc.line', '转下工序ID', readonly=True, ondelete='cascade',
                              help='此栏位由工序状态确认后自动回填')
    qty = fields.Float('单位数量', default=1, digits='Quantity')
    #up_proc = fields.Char('承上工序', compute=_compute_up_proc, readonly=True)
    proc_ctl = fields.Boolean('工序控制', default=0, help='勾选后，转下工序的可报工数，为当前工序的有效完工数(有效完工数：无质检时为报工数，否则为质检合格数)')
    need_qc = fields.Boolean('需检验', default=0)
    qc_department_id = fields.Many2one('staff.department', '质检部门', index=True, ondelete='cascade')
    workcenter_id = fields.Many2one('mrp.workcenter', '工作中心')

    get_way = fields.Selection([('self', '自制'), ('ous', '委外')],
                               '获取方式', required=True, default='self')
    rate_self = fields.Float('自制比率', digits='Quantity', default=100)
    sub_remark = fields.Char('作业描述', default='')
    rate_waste = fields.Float('损耗率', digits='Quantity')
    time_uom = fields.Selection([('s', '秒'), ('m', '分钟'), ('h', '小时')],
                                '时间单位', default='s')
    pre_time = fields.Float('准备时间', digits='Quantity')
    work_time = fields.Float('耗用工时', digits='Quantity')
    price_std = fields.Float('标准工价', digits='Quantity')
    price = fields.Float('加工工价', digits='Quantity')

    worksheet = fields.Binary('PDF', help="Upload your PDF file.")
    worksheet_type = fields.Selection([
        ('pdf', 'PDF'), ('google_slide', 'Google Slide')],
        string="Work Sheet", default="pdf",
        help="Defines if you want to use a PDF or a Google Slide as work sheet."
    )
    worksheet_google_slide = fields.Char('Google Slide', help="Paste the url of your Google Slide. Make sure the access to the document is public.")

    remark = fields.Char('备注', Default='')

    @api.onchange('get_way')
    def get_way_onchange(self):
        for l in self:
            if l.get_way == 'self' and (not l.rate_self or l.rate_self <= 0):
                l.rate_self = 100
            if l.get_way == 'ous' and l.rate_self >= 100:
                l.rate_self = 0

    @api.onchange('mrp_proc_id')
    def mrp_proc_id_onchange(self):
        for l in self:
            if l.mrp_proc_id:
                l.workcenter_id = l.mrp_proc_id.workcenter_id
                l.proc_ctl = l.mrp_proc_id.proc_ctl
                l.need_qc = l.mrp_proc_id.need_qc
                l.qc_department_id = l.mrp_proc_id.qc_department_id
                l.get_way = l.mrp_proc_id.get_way
                l.rate_self = (0 if l.get_way == 'ous' else 100)
                l.rate_waste = l.mrp_proc_id.rate_waste
                l.sub_remark = l.mrp_proc_id.sub_remark
                l.time_uom = l.mrp_proc_id.time_uom
                l.pre_time = l.mrp_proc_id.pre_time
                l.work_time = l.mrp_proc_id.work_time
                l.price_std = l.mrp_proc_id.price_std
                l.price = l.mrp_proc_id.price







