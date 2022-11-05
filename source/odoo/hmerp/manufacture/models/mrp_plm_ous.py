from odoo import fields, api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class MrpPlmOus(models.Model):
    _name = "mrp.plm.ous"
    _description="工序委外订单"
    _inherit = 'mrp.plm.task'

    partner_id = fields.Many2one('partner', '供应商', ondelete='restrict', states={'done': [('readonly', True)]}, help='供应商')
    currency_id = fields.Many2one('res.currency', '外币币别', states={'done': [('readonly', True)]}, help='外币币别')
    price = fields.Float('加工单价', states={'done': [('readonly', True)]}, store=True, digits='Price', help='不含税单价，由含税单价计算得出')
    price_taxed = fields.Float('含税单价', digits='Price', states={'done': [('readonly', True)]},
                               help='含税单价，取自商品成本或对应供应商的采购价')
    discount_rate = fields.Float('折扣率%', states={'done': [('readonly', True)]}, help='折扣率')
    discount_amount = fields.Float('折扣额', states={'done': [('readonly', True)]}, digits='Amount',
                                   help='输入折扣率后自动计算得出，也可手动输入折扣额')
    amount = fields.Float('金额', compute='_compute_all_amount', store=True, digits='Amount',
                          help='金额  = 价税合计  - 税额')
    tax_rate = fields.Float('税率(%)', states={'done': [('readonly', True)]}, default=lambda self: self.env.user.company_id.import_tax_rate,
                            help='默认值取公司进项税率')
    tax_amount = fields.Float('税额', compute='_compute_all_amount', store=True, digits='Amount',
                              help='由税率计算得出')
    subtotal = fields.Float('价税合计', compute='_compute_all_amount', store=True, digits='Amount',
                            help='含税单价 乘以 数量')
    invoice_ids = fields.One2many('money.invoice', compute='_compute_invoice', string='Invoices')
    invoice_count = fields.Integer(compute='_compute_invoice', string='Invoices Count', default=0)                            
    qty_task = fields.Float('委外数量', states={'done': [('readonly', True)]}, digits='Quantity')
    qty_pending = fields.Float('待委外数量', compute='_compute_proc_mat_ids', readonly=True)
    qty_receipt = fields.Float('实收数量', compute='_compute_proc_mat_ids', readonly=True)
    plm_ous_conf_ids = fields.One2many('mrp.plm.ous.conf', 'plm_ous_id', readonly=True)
    plm_ous_retu_ids = fields.One2many('mrp.plm.ous.retu', 'plm_ous_id', readonly=True)
    plm_ous_qc_ids = fields.One2many('mrp.plm.ous.qc', 'plm_ous_id', readonly=True)
    qty_conf = fields.Float('收货数量', compute='_compute_plm_ous_conf', default=0)
    qty_retu = fields.Float('退回数量', compute='_compute_plm_ous_conf', default=0)
    plm_ous_conf_count = fields.Integer(compute='_compute_plm_ous_conf', readonly=True)
    plm_ous_retu_count = fields.Integer(compute='_compute_plm_ous_conf', readonly=True)
    plm_ous_qc_count = fields.Integer(compute='_compute_plm_ous_conf', readonly=True)
    partner_ids = fields.One2many('partner', 'id', compute='_compute_partner_ids', store=False)

    @api.depends('plm_ous_conf_ids', 'plm_ous_retu_ids')
    def _compute_invoice(self):
        for ous in self:
            money_invoices = self.env['money.invoice'].search([
                ('name', '=', ous.name)])
            ous.invoice_ids = not money_invoices and ous.plm_ous_conf_ids.mapped('invoice_id') + ous.plm_ous_retu_ids.mapped('invoice_id') or money_invoices + ous.plm_ous_conf_ids.mapped('invoice_id') + ous.plm_ous_retu_ids.mapped('invoice_id')
            ous.invoice_count = len(ous.invoice_ids.ids)

    @api.onchange('partner_id')
    def partner_id_onchange(self):
        for l in self:
            price_msg, price_id = self.env['ous.price.strategy'].get_price_id(l.partner_id, l.goods_id,l.mrp_proc_id,l.date)
            if price_id:
                l.price = price_id.price
                l.price_taxed = price_id.price_taxed
                l.discount_rate = price_id.discount_rate
                l.tax_rate = l.goods_id.get_tax_rate(l.goods_id, l.partner_id, 'buy')
                l.discount_amount = (l.qty_task * price_id.price * price_id.discount_rate * 0.01)
                l.onchange_price()    
                l._compute_all_amount()
    @api.depends('mrp_proc_id')
    def _compute_partner_ids(self):
        for b in self:
            ids = self.env['ous.partner.line'].search([('mrp_proc_id', '=', b.mrp_proc_id.id)])
            if len(ids) > 0:
                b.partner_ids = ids.mapped('partner_id')
            else:
                b.partner_ids = False

    @api.depends('plm_id', 'dealing_line_id', 'ous_dealing_line_id')
    def _compute_proc_mat_ids(self):
        super()._compute_proc_mat_ids()
        for line in self:
            if not line.dealing_line_id and not line.ous_dealing_line_id:
                line.qty_pending = line.plm_proc_line_id.qty - sum(l1.qty_task for l1 in line.plm_id.plm_ous_ids.filtered(\
                                lambda l2: l2.state == 'done' and l2.plm_proc_line_id.id == line.plm_proc_line_id.id))
            else:
                if line.dealing_line_id:
                    line.qty_pending = line.dealing_line_id.qty - \
                            sum(l1.qty_task for l1 in line.dealing_line_id.dealing_id.mrp_plm_ous_ids.filtered(\
                            lambda l2: l2.state == 'done' and l2.dealing_line_id.id == line.dealing_line_id.id))
                else:
                    line.qty_pending = line.ous_dealing_line_id.qty - \
                            sum(l1.qty_task for l1 in line.ous_dealing_line_id.ous_dealing_id.mrp_plm_ous_ids.filtered(\
                            lambda l2: l2.state == 'done' and l2.ous_dealing_line_id.id == line.ous_dealing_line_id.id))
            line.qty_receipt = line.qty_conf - line.qty_retu
            
    @api.depends('qty_task', 'price_taxed', 'discount_amount', 'tax_rate')
    def _compute_all_amount(selfs):
        for self in selfs:
            '''当订单行的数量、含税单价、折扣额、税率改变时，改变采购金额、税额、价税合计'''
            self.subtotal = self.price_taxed * self.qty_task - self.discount_amount  # 价税合计
            self.tax_amount = self.subtotal / \
                 (100 + self.tax_rate) * self.tax_rate  # 税额
            self.amount = self.subtotal - self.tax_amount  # 金额

    @api.depends('plm_ous_conf_ids', 'plm_ous_retu_ids', 'plm_ous_qc_ids')
    def _compute_plm_ous_conf(self):
        for l in self:
            l.plm_ous_conf_count = len([l1 for l1 in l.plm_ous_conf_ids])
            l.plm_ous_retu_count = len([l1 for l1 in l.plm_ous_retu_ids])
            l.plm_ous_qc_count = len([l1 for l1 in l.plm_ous_qc_ids])
            l.qty_conf = sum(l1.qty for l1 in l.plm_ous_conf_ids.filtered(lambda l2: l2.state == 'done'))
            l.qty_retu = sum(l1.qty for l1 in l.plm_ous_retu_ids.filtered(lambda l2: l2.state == 'done'))

    @api.onchange('goods_id', 'qty_task')
    def onchange_goods_id(self):
        '''当订单行的商品变化时，带出商品上的单位、成本价。
        在采购订单上选择供应商，自动带出供货价格，没有设置供货价的取成本价格。'''
        if self.goods_id:
            if not self.partner_id:
                raise UserError('请先选择一个供应商！')
            self.uom_id = self.goods_id.uom_id
            self.price = self.goods_id.cost
            for line in self.goods_id.vendor_ids:
                if line.date and line.date > self.date:
                    continue
                if line.vendor_id == self.partner_id \
                        and self.qty_task >= line.min_qty:
                    self.price = line.price
                    break
            self.tax_rate = self.goods_id.get_tax_rate(self.goods_id, self.partner_id, 'buy')

    @api.onchange('price', 'tax_rate')
    def onchange_price(self):
        '''当订单行的不含税单价改变时，改变含税单价'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)  # 不含税单价
        decimal = self.env.ref('core.decimal_price')
        if float_compare(price, self.price, precision_digits=decimal.digits) != 0:
            self.price_taxed = self.price * (1 + self.tax_rate * 0.01)

    @api.constrains('tax_rate')
    def _check_tax_rate(self):
        for record in self:
            if self.tax_rate > 100:
                raise UserError('税率不能输入超过100的数')
            if self.tax_rate < 0:
                raise UserError('税率不能输入负数')
            
    @api.onchange('qty_task', 'price_taxed', 'discount_rate')
    def onchange_discount_rate(self):
        '''当数量、单价或优惠率发生变化时，优惠金额发生变化'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)
        self.discount_amount = (self.qty_task * price *
                                self.discount_rate * 0.01)

    def button_done(self):
        """
        """
        for line in self:
            if line.state == 'done':
                raise UserError('请不要重复确认！')
            if not line.partner_id:
                raise UserError('%s %s，供应商不能为空' % (self._description, self.name))      
            line.write({
                'state': 'done',
            })
            
            line._compute_proc_mat_ids()
            if line.qty_pending < 0:
                raise UserError('%s %s,委外订单数量大于生产需求' % (self._description, self.name))            
            line._create_task_conf()
            self.create_plm_ous(line, line.qty_pending)

    def create_plm_ous(self, l, qty):
        rec = self.with_context(is_return=True)
        if qty > 0:
            usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
            rec.env['mrp.plm.ous'].create( {
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_id': l.plm_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'qty_task': qty

                })

    def button_draft(self):
        """
        """
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤回！')
        self.write({
            'state': 'draft',
        })
        plm_ous_conf = self.env['mrp.plm.ous.conf'].search(
            [('plm_ous_id', '=', self.id)])
        plm_ous_conf.unlink()

    def _create_task_conf(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            ous_conf_ids = self.env['mrp.plm.ous.conf'].search([
                ('plm_ous_id', '=', l.id),
                ('state', '=', 'draft')], order="id")
            # 搜到的最后一条是当前正在审核的委外入库单
            if len(ous_conf_ids) > 1:
                if l.qty_task + l.qty_retu <= l.qty_conf:
                    ous_conf_ids[0].unlink()
                else:
                    ous_conf_ids[0].qty_pending = l.qty_task + l.qty_retu - l.qty_conf
                    ous_conf_ids[0].onchange_price()
                    ous_conf_ids[0].onchange_discount_rate()
                    ous_conf_ids[0]._compute_all_amount()
            elif l.qty_task + l.qty_retu > l.qty_conf:
                mrp_plm_id = rec.env['mrp.plm.ous.conf'].create({
                    'company_id': l.company_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'partner_id': l.partner_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_ous_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': l.qty_pending
                })
                mrp_plm_id.price = l.price
                mrp_plm_id.tax_rate = l.tax_rate
                mrp_plm_id.onchange_price()
                mrp_plm_id.discount_rate = l.discount_rate
                mrp_plm_id.onchange_discount_rate()      
                mrp_plm_id._compute_all_amount()                

    def action_view_plm_ous_conf(self):
        self.ensure_one()
        action = {
            'name': '工序委外收货',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.conf',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_conf_ids = [plm_conf.id for plm_conf in self.plm_ous_conf_ids]
        # choose the view_mode accordingly
        if len(plm_ous_conf_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ous_conf_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ous_conf_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_ous_conf_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ous_conf_ids and plm_ous_conf_ids[0] or False
        return action

    def action_view_plm_ous_retu(self):
        self.ensure_one()
        action = {
            'name': '委外退回',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.retu',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_retu_ids = [plm_retu.id for plm_retu in self.plm_ous_retu_ids]
        # choose the view_mode accordingly
        if len(plm_ous_retu_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ous_retu_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ous_retu_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_ous_retu_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ous_retu_ids and plm_ous_retu_ids[0] or False
        return action

    def action_view_plm_ous_qc(self):
        self.ensure_one()
        action = {
            'name': '工序委外质检',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.qc',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_qc_ids = [plm_qc.id for plm_qc in self.plm_ous_qc_ids]
        # choose the view_mode accordingly
        if len(plm_ous_qc_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ous_qc_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ous_qc_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_ous_qc_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ous_qc_ids and plm_ous_qc_ids[0] or False
        return action

    def action_view_invoice(self):
        '''
        This function returns an action that display existing invoices of given purchase order ids( linked/computed via buy.receipt).
        When only one found, show the invoice immediately.
        '''

        self.ensure_one()
        if self.invoice_count == 0:
            return False
        view_id = self.env.ref('money.money_invoice_tree').id
        action = {
            'name': '结算单（供应商发票）',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'money.invoice',
            'view_id': view_id,
            'target': 'current',
        }
        invoice_ids = self.invoice_ids.ids
        action['domain'] = "[('id','in',[" + \
            ','.join(map(str, invoice_ids)) + "])]"
        action['view_mode'] = 'tree'
        return action