from odoo import fields, api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
import datetime


class MrpPlmOusConf(models.Model):
    _name = "mrp.plm.ous.conf"                       
    _description = "工序委外收货"
    _inherit = 'mrp.plm.task.conf'

    date = fields.Date('单据日期', required=True, copy=False, default=fields.Date.context_today,
                       help='单据创建日期，默认为当前天')
    plm_ous_id = fields.Many2one('mrp.plm.ous', '工序委外订单', readonly=True, copy=False)
    partner_id = fields.Many2one('partner', '供应商', states={'done': [('readonly', True)]}, ondelete='restrict', help='供应商')
    currency_id = fields.Many2one('res.currency', '外币币别', states={'done': [('readonly', True)]}, help='外币币别')
    price = fields.Float('加工单价', store=True, states={'done': [('readonly', True)]}, digits='Price', help='不含税单价，由含税单价计算得出')
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
    invoice_id = fields.Many2one('money.invoice', '发票号', copy=False,
                                 ondelete='set null',
                                 help='产生的发票号')
    date_due = fields.Date('到期日期', copy=False,
                           default=lambda self: fields.Date.context_today(
                               self),
                           help='付款截止日期')
    plm_ous_retu_ids = fields.One2many('mrp.plm.ous.retu', 'plm_ous_conf_id', readonly=True)
    plm_ous_qc_ids = fields.One2many('mrp.plm.ous.qc', 'plm_ous_conf_id', readonly=True)
    plm_ous_retu_count = fields.Integer(compute='_compute_plm_ous', readonly=True)
    plm_ous_qc_count = fields.Integer(compute='_compute_plm_ous', readonly=True)
    qty_retu = fields.Float('退回数量', digits='Quantity', compute='_compute_plm_ous', default=0, readonly=True)
    qty_qc = fields.Float('质检数量', digits='Quantity', compute='_compute_plm_ous', default=0, readonly=True)
    qty_ok = fields.Float('合格数量', digits='Quantity', compute='_compute_plm_ous', default=0, readonly=True)
    qty_bad = fields.Float('不良数量', digits='Quantity', compute='_compute_plm_ous', default=0, readonly=True)
    qty_pending = fields.Float('待收货数量', digits='Quantity', compute='_compute_qty_pending')

    @api.depends('qty', 'price_taxed', 'discount_amount', 'tax_rate')
    def _compute_all_amount(selfs):
        for self in selfs:
            '''当订单行的数量、含税单价、折扣额、税率改变时，改变采购金额、税额、价税合计'''
            self.subtotal = self.price_taxed * self.qty - self.discount_amount  # 价税合计
            self.tax_amount = self.subtotal / \
                 (100 + self.tax_rate) * self.tax_rate  # 税额
            self.amount = self.subtotal - self.tax_amount  # 金额

    @api.depends('plm_ous_id')
    def _compute_qty_pending(self):
        for l in self:
            l.qty_pending = l.plm_ous_id.qty_task - l.plm_ous_id.qty_conf + l.plm_ous_id.qty_retu

    @api.depends('plm_ous_retu_ids', 'plm_ous_qc_ids')
    def _compute_plm_ous(self):
        for l in self:
            l.plm_ous_retu_count = len([l1 for l1 in l.plm_ous_retu_ids])
            l.plm_ous_qc_count = len([l1 for l1 in l.plm_ous_qc_ids])
            l.qty_retu = sum(l1.qty for l1 in l.plm_ous_retu_ids.filtered(lambda l2: l2.state == 'done'))
            l.qty_qc = sum(l1.qty for l1 in l.plm_ous_qc_ids.filtered(lambda l2: l2.state == 'done'))
            l.qty_ok = sum(l1.qty_ok for l1 in l.plm_ous_qc_ids.filtered(lambda l2: l2.state == 'done'))
            l.qty_bad = sum(l1.qty_bad for l1 in l.plm_ous_qc_ids.filtered(lambda l2: l2.state == 'done'))

    @api.onchange('goods_id', 'qty')
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
                        and self.qty >= line.min_qty:
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
            
    @api.onchange('qty', 'price_taxed', 'discount_rate')
    def onchange_discount_rate(self):
        '''当数量、单价或优惠率发生变化时，优惠金额发生变化'''
        price = self.price_taxed / (1 + self.tax_rate * 0.01)
        self.discount_amount = (self.qty * price *
                                self.discount_rate * 0.01)

    def _get_invoice_vals(self, partner_id, category_id, date, amount, tax_amount):
        '''返回创建 money_invoice 时所需数据'''
        return {
            'move_id': False,
            'name': self.name,
            'partner_id': partner_id.id,
            'category_id': category_id.id,
            'date': date,
            'amount': amount,
            'reconciled': 0,
            'to_reconcile': amount,
            'tax_amount': tax_amount,
            'date_due': self.date_due,
            'state': 'draft',
            'note': False,
        }
    def _receipt_make_invoice(self):
        '''委外入库单 生成结算单'''
        invoice_id = False
        amount = self.amount
        tax_amount = self.tax_amount
        categ = self.env.ref('money.core_category_purchase')
        if not float_is_zero(amount, 2):
            invoice_id = self.env['money.invoice'].create(
                self._get_invoice_vals(
                    self.partner_id, categ, self.date, amount, tax_amount)
            )
        return invoice_id

    def button_done(self):
        """
        """
        for line in self:
            if line.state == 'done':
                raise UserError('请不要重复确认！')
            if line.plm_ous_id:
                line.plm_ous_id._compute_plm_ous_conf()
                line._compute_qty_pending()  # 计算待收货数量qty_pending
                if line.qty_pending < 0:
                    raise UserError('%s %s,收货数量大于委外订单数量' % (self._description, self.name))
                line.plm_ous_id._create_task_conf()  # 更新此入库单相关的委外订单的相关字段，如果尚有产品需入库，则创建新的工序委外入库单
            line._create_task_qc()   # 创建工序委外质检报告
            invoice_id = line._receipt_make_invoice()
            line.write({
                'state': 'done',
                'invoice_id': invoice_id and invoice_id.id,
            })

    def button_draft(self):
        """
        """
        for l in self:
            if l.state == 'draft':
                raise UserError('请不要重复撤回！')
            # 查找产生的结算单
            invoice_ids = self.env['money.invoice'].search(
                [('name', '=', self.invoice_id.name)])
            for invoice in invoice_ids:
                if invoice.state == 'done':
                    invoice.money_invoice_draft()
                invoice.unlink()
            qc_ids = self.env['mrp.plm.ous.qc'].search([('plm_ous_conf_id', '=', l.id)])
            if len(qc_ids) > 0:
                qc_ids.unlink()
            retu_ids = self.env['mrp.plm.ous.retu'].search([('plm_ous_conf_id', '=', l.id)])
            if len(retu_ids) > 0:
                retu_ids.unlink()
            l.write({
                'state': 'draft',
            })

    def button_retu(self):
        self.ensure_one()
        plm_ous_retu_ids = []
        if len(plm_ous_retu_ids) == 0:
            retu_id = self._create_task_retu()
            if retu_id > 0:
                plm_ous_retu_ids.append(retu_id)
            else:
                raise UserError('%s %s，可退货数量等于0' % (self._description, self.name))
        
        if len(plm_ous_retu_ids) == 0:
            return False
        action = {
            'name': '生产报工',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.retu',
            'view_id': False,
            'target': 'current',
        }

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

    def _create_task_qc(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            if l.plm_proc_line_id.need_qc == True and l.qty - l.qty_qc > 0:
                # 创建工序委外质检报告
                mrp_plm_id = rec.env['mrp.plm.ous.qc'].create({
                    'company_id': l.company_id.id,
                    'partner_id': l.partner_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_ous_id': l.plm_ous_id.id,
                    'plm_ous_conf_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': l.qty - l.qty_qc
                })
    
    def _create_task_retu(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_retu = l.qty - l.qty_retu
            """
            需质检时，可退回数量=质检合格数量 - 已退回数量
            """
            if l.plm_proc_line_id.need_qc:
                qty_retu = l.qty_ok - l.qty_retu
            if qty_retu > 0:
                mrp_plm_id = rec.env['mrp.plm.ous.retu'].create({
                    'type': 'ous_retu',
                    'company_id': l.company_id.id,
                    'partner_id': l.partner_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_ous_id': l.plm_ous_id.id,
                    'plm_ous_conf_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': qty_retu
                })
                mrp_plm_id.price = l.price
                mrp_plm_id.tax_rate = l.tax_rate
                mrp_plm_id.onchange_price()
                mrp_plm_id.discount_rate = l.discount_rate
                mrp_plm_id.onchange_discount_rate()      
                mrp_plm_id._compute_all_amount()
                return mrp_plm_id.id
            return False

    def action_view_plm_ous_retu(self):
        action = {
            'name': '生产报工',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.retu',
            'view_id': False,
            'target': 'current',
        }
        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_retu_ids = [plm_retu.id for plm_retu in self.plm_ous_retu_ids]
        if len(plm_ous_retu_ids) == 0:
            retu_id = self._create_task_retu()
            if retu_id > 0:
                plm_ous_retu_ids.append(retu_id)

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
            'name': '生产报工',
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


class MrpPlmOusRetu(models.Model):
    _name = "mrp.plm.ous.retu"
    _description = "工序委外退回"
    _inherit = 'mrp.plm.ous.conf'

    type = fields.Selection([
            ('qc_retu','质检退回'),
            ('ous_retu','委外退回')], readonly=True, default='ous_retu', string='退回类型')
    plm_ous_conf_id = fields.Many2one('mrp.plm.ous.conf', '委外收货单', readonly=True)
    ous_dealing_id = fields.Many2one('mrp.plm.ous.defectdealing', '委外不良处理', readonly=True)
    qty_pending = fields.Float('待退回数量', digits='Quantity', compute='_compute_qty_pending')

    @api.depends('plm_ous_conf_id', 'ous_dealing_id')
    def _compute_qty_pending(self):
        for l in self:
            if l.plm_ous_conf_id:
                if l.plm_proc_line_id.need_qc:      
                    l.qty_pending = l.plm_ous_conf_id.qty_ok - l.plm_ous_conf_id.qty_retu
                else:
                    l.qty_pending = l.plm_ous_conf_id.qty - l.plm_ous_conf_id.qty_retu
            elif l.ous_dealing_id:
                l.qty_pending = l.ous_dealing_id.qty_retu - l.ous_dealing_id.qty_retu_to

    def button_done(self):
        """
        """
        for line in self:
            if line.state == 'done':
                raise UserError('%s %s, 请不要重复确认！'% (self._description, self.name))
            if line.plm_ous_conf_id:
                line.plm_ous_conf_id._compute_plm_ous()
                line._compute_qty_pending()
                if line.qty_pending < 0:
                    if not line.plm_proc_line_id.need_qc:
                        raise UserError('%s %s,退货数量大于收货数量' % (self._description, self.name))
                    else:
                        raise UserError('%s %s,退货数量大于收货数量' % (self._description, self.name))            
            if line.plm_ous_id:
                line.plm_ous_id._compute_plm_ous_conf()
                line.plm_ous_id._create_task_conf()
            invoice_id = self._receipt_make_invoice()
            line.write({
                'state': 'done',
                'invoice_id': invoice_id and invoice_id.id,
            })
                
    def button_draft(self):
        """
        """
        for l in self:
            if l.state == 'draft':
                raise UserError('请不要重复撤回！')
            if l.plm_ous_id:
                l.plm_ous_id._compute_plm_ous_conf()
                if l.plm_ous_id.qty_task - l.plm_ous_id.qty_conf + l.plm_ous_id.qty_retu < 0:
                    raise UserError('%s %s, 撤回后导致订单%s超交' % (self._description, self.name,l.plm_ous_id.name)) 
                l.plm_ous_id._create_task_conf()
                l.write({
                        'state': 'draft',
                    })
        # 查找产生的结算单
        invoice_ids = self.env['money.invoice'].search(
            [('name', '=', self.invoice_id.name)])
        for invoice in invoice_ids:
            if invoice.state == 'done':
                invoice.money_invoice_draft()
            invoice.unlink()
        


class MrpPlmOusQc(models.Model):
    _name = "mrp.plm.ous.qc"
    _description = "工序委外质检报告"
    _inherit = 'mrp.plm.task.qc'

    partner_id = fields.Many2one('partner', '供应商', states={'done': [('readonly', True)]}, ondelete='restrict', help='供应商')
    plm_ous_id = fields.Many2one('mrp.plm.ous', '工序委外订单', readonly=True)
    plm_ous_conf_id = fields.Many2one('mrp.plm.ous.conf', '工序委外收货', readonly=True, help='关联生产报工ID')    
    line_ids = fields.One2many('mrp.plm.ous.qc.line', 'qc_id', '质检不良明细', states={'done': [('readonly', True)]})
    qty_ok = fields.Float('合格数量', digits='Quantity', compute='_compute_qty', readonly=True)
    qty_bad = fields.Float('不合格数量', digits='Quantity', compute='_compute_qty', readonly=True)
    qty_dealing = fields.Float('不良处理数量', digits='Quantity', compute='_compute_plm_ous_defectdealing', readonly=True)
    qty_pending = fields.Float("待质检数量", digits='Quantity', compute="_compute_qty_pending",readonly=True)
    plm_ous_dealing_ids = fields.One2many('mrp.plm.ous.defectdealing', 'plm_ous_qc_id', readonly=True)
    plm_ous_defectdealing_count = fields.Integer(compute='_compute_plm_ous_defectdealing', readonly=True)

    @api.depends('plm_ous_dealing_ids')
    def _compute_plm_ous_defectdealing(self):
        for line in self:
            line.plm_ous_defectdealing_count = len([l for l in line.plm_ous_dealing_ids])
            line.qty_dealing = sum(l.qty for l in line.plm_ous_dealing_ids.filtered(lambda l1: l1.state == 'done'))

    @api.depends('plm_ous_conf_id')
    def _compute_qty_pending(self):
        for l in self:
            l.qty_pending = 0
            if l.plm_ous_conf_id:
                l.qty_pending = l.plm_ous_conf_id.qty - l.plm_ous_conf_id.qty_qc

    @api.depends('line_ids')
    def _compute_qty(self):
        for line in self:
            line.qty_ok = line.qty - sum(l.qty for l in line.line_ids)
            line.qty_bad = sum(l.qty for l in line.line_ids)

    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('%s %s, 请不要重复确认！' % (self._description, self.name))
            if l.qty < l.qty_bad:
                raise UserError('%s %s,不良数量大于质检数量 ！' % (self._description, self.name))
            l.write({
                'state': 'done',
            })
            if l.plm_ous_conf_id:
                l.plm_ous_conf_id._compute_plm_ous()
                l._compute_qty_pending()
                if l.qty_pending < 0:
                    raise UserError('%s %s,质检数大于收货数量！' % (self._description, self.name))
                l.plm_ous_conf_id._create_task_qc()
            l._create_plm_ous_defectdealing()

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })
            dealing_ids = self.env['mrp.plm.ous.defectdealing'].search([('plm_ous_qc_id', '=', l.id)])
            if len(dealing_ids) > 0:
                dealing_ids.unlink()    
    
    def _create_plm_ous_defectdealing(self):
        """
        """
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_scrap = sum(l1.qty for l1 in l.line_ids.filtered(lambda l2: l2.disposal_mode == 'scrap'))
            qty_replan = sum(l1.qty for l1 in l.line_ids.filtered(lambda l2: l2.disposal_mode == 'replan'))
            qty_retu = sum(l1.qty for l1 in l.line_ids.filtered(lambda l2: l2.disposal_mode == 'retu'))
            qty_rework = l.qty_bad - qty_scrap - qty_replan - qty_retu
            if l.qty_bad > l.qty_dealing:
                mrp_plm_id = rec.env['mrp.plm.ous.defectdealing'].create({
                    'company_id': l.company_id.id,
                    'partner_id': l.partner_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'plm_ous_id': l.plm_ous_id.id,
                    'plm_ous_qc_id': l.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'qty': l.qty_bad - l.qty_dealing,
                    'qty_rework': qty_rework,
                    'qty_retu': qty_retu,
                    'qty_scrap': qty_scrap,
                    'qty_replan': qty_replan
                })

    def action_view_plm_ous_defectdealing(self):
        action = {
            'name': '不良处理',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.defectdealing',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_dealing_ids = [plm_dealing.id for plm_dealing in self.plm_ous_dealing_ids]
        # choose the view_mode accordingly
        if len(plm_dealing_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_dealing_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_dealing_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_ous_defectdealing_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_dealing_ids and plm_dealing_ids[0] or False
        return action
    
    def unlink(self):
        for l in self:
            if not l.state == 'draft':
                raise UserError('%s %s, 不为草稿状态，不许删除' % (self._description , l.name))
        super().unlink()

class MrpPlmOusQcLine(models.Model):
    _name = "mrp.plm.ous.qc.line"
    _description = "委外工序不良明细"
    _inherit = 'mrp.plm.task.qc.line'
    qc_id = fields.Many2one('mrp.plm.ous.qc', '工序质检报告', help='绑定质检报告id')
    disposal_mode = fields.Selection(selection_add=[('retu', '退回')], default='retu', string='处置方式', required=True)

class MrpPlmOusDefectdealing(models.Model):
    _name = "mrp.plm.ous.defectdealing"
    _description = "工序委外质检不良处理"
    _inherit = 'mrp.plm.task.defectdealing'

    partner_id = fields.Many2one('partner', '供应商', states={'done': [('readonly', True)]}, ondelete='restrict', help='供应商')
    plm_ous_id = fields.Many2one('mrp.plm.ous', '生产任务单', readonly=True, help='关联生产任务ID')
    plm_ous_qc_id = fields.Many2one('mrp.plm.ous.qc', '工序不良处理单', readonly=True, help='关联生产报工ID') 
    rework_line_ids = fields.One2many('mrp.plm.ous.defectdealing.line', 'dealing_id', string='返工任务明细', states={'done': [('readonly', True)]})
    qty_pending = fields.Float('待处理数量', digits='Quantity', compute='_compute_qty_pending', readonly=True)
    ous_dealing_ids = fields.One2many(string='质检不良明细', related='plm_ous_qc_id.line_ids', readonly=True)
    plm_task_ids = fields.One2many('mrp.plm.task', 'ous_dealing_id', readonly=True)
    plm_ous_ids = fields.One2many('mrp.plm.ous', 'ous_dealing_id', readonly=True)
    plm_ous_retu_ids = fields.One2many('mrp.plm.ous.retu', 'ous_dealing_id', readonly=True)
    plm_ids = fields.One2many('mrp.plm', 'ous_dealing_id', readonly=True)
    plm_scrap_ids = fields.One2many('mrp.plm.scrap', 'ous_dealing_id', readonly=True)

    plm_task_count = fields.Integer(compute='_compute_to_info', readonly=True)
    plm_ous_count = fields.Integer(compute='_compute_to_info', readonly=True)
    plm_ous_retu_count = fields.Integer(compute='_compute_to_info', readonly=True)
    plm_count = fields.Integer(compute='_compute_to_info', readonly=True)
    plm_scrap_count = fields.Integer(compute='_compute_to_info', readonly=True)
       
    @api.depends('plm_task_ids', 'plm_ous_ids', 'plm_ous_retu_ids', 'plm_ids', 'plm_scrap_ids')
    def _compute_to_info(self):
        for l in self:
            l.plm_task_count = len([l1 for l1 in l.plm_task_ids])
            l.plm_ous_count = len([l1 for l1 in l.plm_ous_ids])
            l.plm_ous_retu_count = len([l1 for l1 in l.plm_ous_retu_ids])
            l.plm_count = len([l1 for l1 in l.plm_ids])
            l.plm_scrap_count = len([l1 for l1 in l.plm_scrap_ids])
            l.qty_scrap_to = sum(l1.qty for l1 in l.plm_scrap_ids.filtered(lambda l2:l2.state == 'done'))
            l.qty_retu_to = sum(l1.qty for l1 in l.plm_ous_retu_ids.filtered(lambda l2:l2.state == 'done'))

    @api.depends('plm_ous_id')
    def _compute_qty_pending(self):
        for line in self:
            line.qty_pending = line.plm_ous_id.qty_task - line.plm_ous_id.qty_conf - line.plm_ous_id.qty_retu

    def button_done(self):
        for l in self:
            if l.state == 'done':
                raise UserError('%s %s, 请不要重复确认！' % (l._description, l.name))
            if l.qty <= 0:
                raise UserError('%s %s, 不良处理数量必需大于0！' % (l._description, l.name))
            if l.qty_rework < 0:
                raise UserError('%s %s, 返工数量不许小于0！' % (l._description, l.name))
            if l.qty_rework > 0 and len([l1 for l1 in l.rework_line_ids]) == 0:
                raise UserError('%s %s, 返工数量大于0时，返工明细不能为空！' % (l._description, l.name))
            l.write({
                'state': 'done',
            })
            if l.plm_ous_qc_id:
                l.plm_ous_qc_id._compute_plm_ous_defectdealing()
                l._compute_qty_pending()
                if l.qty_pending < 0:
                    raise UserError('%s %s, 不良处理数量大于不良数量' % (l._description, l.name))
                l.plm_ous_qc_id._create_plm_ous_defectdealing()

        self._create_mrp_plm_task()
        self._create_mrp_plm_scrap()
        self._create_mrp_plm()
        self._create_ous_retu()

    def button_draft(self):
        for l in self:
            l.write({
                'state': 'draft',
            })
            plm = self.env['mrp.plm'].search(
                [('ous_dealing_id', '=', l.id)])
            plm.unlink()
            plm_ous = self.env['mrp.plm.ous'].search(
                [('ous_dealing_id', '=', l.id)])
            plm_ous.unlink()
            plm_ous_retu = self.env['mrp.plm.ous.retu'].search(
                [('ous_dealing_id', '=', l.id)])
            plm_ous_retu.unlink()
            plm_task = self.env['mrp.plm.task'].search(
                [('ous_dealing_id', '=', l.id)])
            plm_task.unlink()  
            plm_scrap = self.env['mrp.plm.scrap'].search(
                [('ous_dealing_id', '=', l.id)])
            plm_scrap.unlink()   

    def _create_mrp_plm_task(self):
        """
        产生返工任务单
        """
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            up_task = False 
            for p in l.rework_line_ids:
                mrp_plm_task = False
                mrp_plm_task_line = {
                        'user_id':usr.id,
                        'department_id':usr.department_id.id,
                        'plm_proc_line_id': l.plm_proc_line_id.id,
                        'rework_task_id': l.plm_task_id.id,
                        'rework_ous_id': l.plm_ous_id.id,
                        'workcenter_id': p.workcenter_id.id,
                        'ous_dealing_id': l.id,
                        'goods_id': l.goods_id.id,
                        'goods_uom_id': l.goods_uom_id.id,
                        'plm_id': l.plm_id.id,
                        'qty_task':l.qty
                    }
                if p.get_way == 'self':            
                    mrp_plm_task = rec.env['mrp.plm.task'].create(mrp_plm_task_line)
                    mrp_plm_task.dealing_line_id = p.id
                else:
                    mrp_plm_task = rec.env['mrp.plm.ous'].create(mrp_plm_task_line)
                    mrp_plm_task.ous_dealing_line_id = p.id
                
                if up_task != False:
                    if p.get_way == 'self':  
                        up_task.next_task_id = mrp_plm_task
                    else:
                        up_task.next_ous_id = mrp_plm_task
                up_task = mrp_plm_task
        
    def _create_mrp_plm(self):
        """
        产生重开生产加工单
        """
        rec = self.with_context(is_return=True)
        for l in self:
            if l.qty_replan > 0:
                mrp_plm_id = rec.env['mrp.plm'].create({
                    'partner_id': l.plm_id.partner_id.id,
                    'user_id': l.plm_id.user_id.id,
                    'date': datetime.datetime.now(),
                    'type': 'work',
                    'ref': l.plm_id.ref,
                    'warehouse_id': l.plm_id.warehouse_id.id,
                    'department_id': l.plm_id.department_id.id,
                    'uom_id': l.plm_id.uom_id.id,
                    'goods_id': l.plm_id.goods_id.id,
                    'bom_id': l.plm_id.bom_id.id,
                    'order_id': l.plm_id.order_id.id,
                    'ous_dealing_id': l.id,
                    'plm_from_id': l.plm_id.id,
                    'remark': l.plm_id.remark
                })
                for l1 in l.plm_id.line_ids:
                    mrp_plm_line_id = rec.env['mrp.plm.line'].create({
                        'plm_id': mrp_plm_id.id,
                        'goods_id': l1.goods_id.id,
                        'uom_id': l1.uom_id.id,
                        'warehouse_id': l1.warehouse_id.id,
                        'radix': l1.radix,
                        'rate_waste': l1.rate_waste,
                        'mrp_proc_id': l1.mrp_proc_id.id,
                        'remark': l1.remark
                    })
                for l2 in l.plm_id.line_proc_ids:
                    mrp_plm_line_proc_id = rec.env['mrp.plm.proc.line'].create({
                        'plm_id': mrp_plm_id.id,
                        'sequence': l2.sequence,
                        'mrp_proc_id': l2.mrp_proc_id.id,
                        'qty_proc': l2.qty_proc,
                        'proc_ctl': l2.proc_ctl,
                        'need_qc': l2.need_qc,
                        'qc_department_id': l2.qc_department_id.id,
                        'workcenter_id': l2.workcenter_id.id,
                        'get_way': l2.get_way,
                        'rate_self': l2.rate_self,
                        'sub_remark': l2.sub_remark,
                        'rate_waste': l2.rate_waste,
                        'time_uom': l2.time_uom,
                        'pre_time': l2.pre_time,
                        'work_time': l2.work_time,
                        'price_std': l2.price_std,
                        'price': l2.price,
                        'remark': l2.remark
                    })
                mrp_plm_id.qty = l.qty_replan

    def _create_ous_retu(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_retu = l.qty_retu - l.qty_retu_to
            """
            需质检时，可退回数量=质检合格数量 - 已退回数量
            """
            if qty_retu > 0:
                mrp_plm_id = rec.env['mrp.plm.ous.retu'].create({
                    'type': 'qc_retu',
                    'company_id': l.company_id.id,
                    'partner_id': l.partner_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_ous_id': l.plm_ous_id.id,
                    'ous_dealing_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': qty_retu
                })
                mrp_plm_id.price = l.plm_ous_id.price
                mrp_plm_id.tax_rate = l.plm_ous_id.tax_rate
                mrp_plm_id.onchange_price()
                mrp_plm_id.discount_rate = l.plm_ous_id.discount_rate
                mrp_plm_id.onchange_discount_rate()      
                mrp_plm_id._compute_all_amount()
                return mrp_plm_id.id
            return False

    def unlink(self):
        for l in self:
            if not l.state == 'draft':
                raise UserError('%s %s, 不为草稿状态，不许删除' % (self._description , l.name))
        super().unlink()
    
    def action_view_plm(self):
        action = {
            'name': '生产加工单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ids = [plm.id for plm in self.plm_ids]
        # choose the view_mode accordingly
        if len(plm_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ids and plm_ids[0] or False
        return action

    def action_view_plm_task(self):
        action = {
            'name': '生产任务单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.task',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_task_ids = [plm.id for plm in self.plm_task_ids]
        # choose the view_mode accordingly
        if len(plm_task_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_task_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_task_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_task_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_task_ids and plm_task_ids[0] or False
        return action
    def action_view_plm_ous(self):
        action = {
            'name': '工序委外订单',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_ids = [plm.id for plm in self.plm_ous_ids]
        # choose the view_mode accordingly
        if len(plm_ous_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_ous_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_ous_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_ous_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_ous_ids and plm_ous_ids[0] or False
        return action

    def _create_task_retu(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_retu = l.qty - l.qty_retu
            """
            需质检时，可退回数量=质检合格数量 - 已退回数量
            """
            if l.plm_proc_line_id.need_qc:
                qty_retu = l.qty_ok - l.qty_retu
            if qty_retu > 0:
                mrp_plm_id = rec.env['mrp.plm.ous.retu'].create({
                    'type': 'ous_retu',
                    'company_id': l.company_id.id,
                    'partner_id': l.partner_id.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_ous_id': l.plm_ous_id.id,
                    'plm_ous_conf_id': l.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'dealing_line_id': l.dealing_line_id.id,
                    'ous_dealing_line_id': l.ous_dealing_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': qty_retu
                })
                mrp_plm_id.price = l.price
                mrp_plm_id.tax_rate = l.tax_rate
                mrp_plm_id.onchange_price()
                mrp_plm_id.discount_rate = l.discount_rate
                mrp_plm_id.onchange_discount_rate()      
                mrp_plm_id._compute_all_amount()
                return mrp_plm_id.id
            return False

    def action_view_plm_ous_retu(self):
        action = {
            'name': '生产报工',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.ous.retu',
            'view_id': False,
            'target': 'current',
        }
        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_ous_retu_ids = [plm_retu.id for plm_retu in self.plm_ous_retu_ids]
        if len(plm_ous_retu_ids) == 0:
            retu_id = self._create_task_retu()
            if retu_id:
                plm_ous_retu_ids.append(retu_id)

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

    def action_view_plm_scrap(self):
        action = {
            'name': '生产报废报告',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.plm.scrap',
            'view_id': False,
            'target': 'current',
        }

        #receipt_ids = sum([order.receipt_ids.ids for order in self], [])
        plm_scrap_ids = [plm_scrap.id for plm_scrap in self.plm_scrap_ids]
        # choose the view_mode accordingly
        if len(plm_scrap_ids) > 1:
            action['domain'] = "[('id','in',[" + \
                ','.join(map(str, plm_scrap_ids)) + "])]"
            action['view_mode'] = 'tree,form'
        elif len(plm_scrap_ids) == 1:
            view_id = self.env.ref('manufacture.mrp_plm_scrap_form').id
            action['views'] = [(view_id, 'form')]
            action['res_id'] = plm_scrap_ids and plm_scrap_ids[0] or False
        return action

    def _create_mrp_plm_scrap(self):
        rec = self.with_context(is_return=True)
        usr = self.env['staff'].search([('user_id', '=', self.env.uid)])
        for l in self:
            qty_scrap = l.qty_scrap - l.qty_scrap_to
            if qty_scrap > 0:          
                mrp_plm_id = rec.env['mrp.plm.scrap'].create({
                    'ous_dealing_id': l.id,
                    'user_id':usr.id,
                    'department_id':usr.department_id.id,
                    'company_id': l.company_id.id,
                    'workcenter_id': l.workcenter_id.id,
                    'goods_id': l.goods_id.id,
                    'goods_uom_id': l.goods_uom_id.id,
                    'plm_id': l.plm_id.id,
                    'plm_proc_line_id': l.plm_proc_line_id.id,
                    'next_task_id': l.next_task_id.id,
                    'next_ous_id': l.next_ous_id.id,
                    'qty': qty_scrap
                })



class MrpPlmOusDefectdealingLine(models.Model):
    _name = 'mrp.plm.ous.defectdealing.line'
    _description = '生产不良返工明细'    
    _inherit = 'mrp.plm.proc.line'

    dealing_id = fields.Many2one('mrp.plm.ous.defectdealing', '不良处理', readonly=True)
    qty = fields.Float('加工数量', compute='_compute_qty',  digits='Quantity')

    @api.depends('dealing_id')
    def _compute_qty(self):
        for l in self:
            if l.dealing_id:
                l.qty = l.dealing_id.qty_rework

    @api.onchange('mrp_proc_id')
    def mrp_proc_id_onchange(self):
        super().mrp_proc_id_onchange()
        for l in self:
            if l.dealing_id and l.qty == 0:
                l.qty = l.dealing_id.qty_rework