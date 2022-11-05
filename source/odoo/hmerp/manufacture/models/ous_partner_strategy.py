from odoo.tools.func import lazy
from odoo import fields, api, models
import datetime


class OusPartnerStrategy(models.Model):
    _name = 'ous.partner.strategy'
    _description = '工序委外供应商策略'

    name = fields.Char(compute='_compute_name')
    goods_id = fields.Many2one('goods', '商品', required=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', required=True)
    line_ids = fields.One2many('ous.partner.strategy.line', 'strategy_id')
    details = fields.Html('优先级',compute='_compute_details')
    
    @api.depends('goods_id', 'mrp_proc_id')
    def _compute_name(self):
        for l in self:
            l.name = (l.goods_id.display_name if l.goods_id else '') + ' - ' + (l.mrp_proc_id.name if l.mrp_proc_id else '')

    @api.depends('line_ids')
    def _compute_details(self):
        for v in self:
            vl = {'col':[],'val':[]}
            vl['col'] = ['顺序','','名称']
            for l in v.line_ids:
                vl['val'].append([l.sequence,l.priority])
            v.details = self.env.company._get_html_table(vl)

    @api.onchange('goods_id', 'mrp_proc_id')
    def _default_line_ids(self):
        for line in self:
            if len([l for l in line.line_ids]) == 0:
                line_ids = []
                line_ids.append((0, 0,{'strategy_id': line.id, 'sequence': 1, 'priority': 'price'}))
                line_ids.append((0, 0,{'strategy_id': line.id, 'sequence': 2, 'priority': 'quality'}))
                line_ids.append((0, 0,{'strategy_id': line.id, 'sequence': 3, 'priority': 'cycle'}))
                line.line_ids = line_ids

class OusPartnerStrategyLine(models.Model):
    _name = 'ous.partner.strategy.line'
    _description = '工序委外供应商策略规则'
    _order = 'strategy_id, sequence'
    sequence = fields.Integer('顺序', store=True, help='标记优先级的顺序')
    strategy_id = fields.Many2one('ous.partner.strategy', '委外供应商策略ID', store=True, readonly=True)
    priority = fields.Selection([
        ('price', '价格'),
        ('quality', '品质等级'),
        ('cycle', '周期'),
    ], string='优先级', store=True, readonly=True)

"""
扩展供应商模型
1.增加委外供应商工序绑定明细
2.增加计算字段，单价、品质等级和周期，用于工序委外业务选择供应商时的排序依据
"""
class OusPartnerExtened(models.Model):
    _inherit = 'partner'

    line_proc_ids = fields.One2many('ous.partner.line', 'partner_id', string='工序绑定明细')

    price_sort = fields.Float(store=False, readonly=True)
    grade_sort = fields.Integer(store=False, readonly=True)
    cycle_sort = fields.Integer(store=False, readonly=True)
    
    def _get_sort_val(self):
        goods_id = self.env['goods'].search([('id', '=', self.env.context['goods_id'])])
        mrp_proc_id = self.env['mrp.proc'].search([('id', '=', self.env.context['mrp_proc_id'])])
        date = datetime.datetime.now()
        for l in self:
            l.price_sort = 0
            l.grade_sort = 0
            l.cycle_sort = 0
            if goods_id and mrp_proc_id:
                price_msg, price_id = self.env['ous.price.strategy'].get_price_id(l, goods_id, mrp_proc_id, date)
                if price_id:
                    l.price_sort = price_id.price
                mrp_proc_line = l.line_proc_ids.filtered(lambda _l: _l.mrp_proc_id == mrp_proc_id)
                if mrp_proc_line and len([l2 for l2 in mrp_proc_line]) > 0:
                    l.grade_sort = mrp_proc_line[0].quality_grade_id.grade
                    l.cycle_sort = mrp_proc_line[0].cycle

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if 'OusStrategy' in self.env.context:
            order = ''
            mrp_proc_id = self.env.context['mrp_proc_id']
            goods_id = self.env.context['goods_id']
            
            strategy = self.env['ous.partner.strategy'].search([('goods_id', '=', goods_id), ('mrp_proc_id', '=', mrp_proc_id)])
            priority_ids = False
            if strategy and len([_l for _l in strategy]) > 0:
                priority_ids = strategy[0].line_ids
            if not priority_ids:
                return super().name_search(name=name, args=args, operator=operator, limit=limit)
            
            ids = self.env['partner'].search(args)
            ids._get_sort_val()
            result = [(l.id, l.name) for l in sorted(ids,key=lambda item: self._compute_sort_keys(item, priority_ids))]
            return result
        else:
            return super().name_search(name=name, args=args, operator=operator, limit=limit)

    def _compute_sort_keys(self, item, priority_ids):
        field1 = item[self._get_sort_field(priority_ids[0])]
        field2 = item[self._get_sort_field(priority_ids[1])]
        field3 = item[self._get_sort_field(priority_ids[2])]
        return field1, field2, field3
    
    def _get_sort_field(self, line):
        if line.priority == 'price':
            return 'price_sort'
        if line.priority == 'quality':
            return 'grade_sort'
        if line.priority == 'cycle':
            return 'cycle_sort'
        return 'price_sort'

class OusPartnerLine(models.Model):
    _name = 'ous.partner.line'
    _description = '委外供应商工序绑定明细'
    _sql_constraints = [
        ('_ous_partner_line_uniq', 'unique(partner_id, mrp_proc_id)', '工序不能重复')
    ]

    partner_id = fields.Many2one('partner', '供应商', readonly=True)
    mrp_proc_id = fields.Many2one('mrp.proc', '工序', required=True)
    quality_grade_id = fields.Many2one('partner.quality.grade', '品质等级', required=True)
    cycle = fields.Integer('周期', required=True, default=1)
