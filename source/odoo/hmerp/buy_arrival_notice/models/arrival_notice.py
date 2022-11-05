# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

# 销售订单确认状态可选值
ORDER_STATES = [
    ('draft', '草稿'),
    ('done', '已确认'),
    ('in', '已入库'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class ArrivalNotice(models.Model):
    _name = 'arrival.notice'
    _description = '到货通知单'
    _rec_name = 'vendor_id'
    _order = 'date desc, state desc, vendor_id'

    line_ids = fields.One2many('arrival.notice.line', 'notice_id', '通知单行', states=READONLY_STATES)
    date = fields.Date(string='单据日期', default=fields.date.today(), help='单据日期，默认当天')
    vendor_id = fields.Many2one('partner', string='供应商',
                                domain=[('s_category_id', '!=', False)],
                                ondelete='restrict', states=READONLY_STATES, help='供应商')
    express_type = fields.Char(string='承运商', help='承运商',)
    express_code = fields.Char(string='快递单号', help='快递单号',)
    state = fields.Selection(ORDER_STATES, '确认状态', readonly=True,
                             help="到货通知单的确认状态", index=True,
                             copy=False, default='draft')

    @api.onchange('vendor_id')
    def onchange_vendor_id(self):
        if self.vendor_id:
            domain = [('vendor_id', '=', self.vendor_id.id), ('state', '=', 'draft')]
            if isinstance(self.id, int):
                domain.append(('id', '!=', self.id))
            if self.search(domain):
                self.vendor_id = False
                return {'warning': {'title': '已存在未确认的通知单',
                                    'message': '建议修改原通知单而不是新建'}}
            self.line_ids = False
            newline_ids = []
            domain = [('order_id.state', '=', 'done'), ('order_id.partner_id', '=', self.vendor_id.id)]
            buy_order_line_ids = self.env['buy.order.line'].search(domain)
            for line in buy_order_line_ids:
                if line.quantity_in < line.quantity:
                    newline = {'buy_line_id': line.id, 'qty': line.quantity - line.quantity_in}
                    newline_ids.append((0, 0, newline))
            self.line_ids = newline_ids
    
    def notice_done(self):
        """确认到货通知单"""
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认')
        if not self.line_ids:
            raise UserError('请输入商品明细行')
        to_mark = []    # 要标记已通知的入库单
        last_move_line = False
        for l in self.line_ids:
            # 找出采购单行对应的入库单行
            if l.goods_id.using_batch:
                if l.goods_id.force_batch_one:
                    # 序列号产品在生成入库单的时候已经是一号一行
                    i = l.qty
                    for move_line in self.env['wh.move.line'].search([('state', '=', 'draft'),
                                                                     ('buy_line_id', '=', l.buy_line_id.id)]):
                        if i > 0:
                            move_line.notice_line_id = l.id
                            to_mark.append(move_line.move_id.id)
                        i -= 1
                else:
                    # 不是序列号产品的批号在入库单生成时只有一行
                    move_line = self.env['wh.move.line'].search([('state', '=', 'draft'),
                                                                ('buy_line_id', '=', l.buy_line_id.id),
                                                                ('notice_line_id', '=', False)])
                    if move_line:
                        move_line.notice_line_id = l.id
                        move_line.goods_qty = l.qty
                        last_move_line = move_line
                        to_mark.append(move_line.move_id.id)
                    else:
                        raise UserError('只有"确认"状态的采购订单才可以通知仓库收货。'
                                        '当前采购订单可能未被确认或已被作废。'
                                        '采购单号：{}'.format(l.buy_line_id.order_id.name))
                        return
            else:
                move_line = self.env['wh.move.line'].search([('state', '=', 'draft'),
                                                            ('buy_line_id', '=', l.buy_line_id.id)])
                move_line.notice_line_id = l.id
                move_line.goods_qty = l.qty
                to_mark.append(move_line.move_id.id)
        for m in self.env['wh.move'].browse(set(to_mark)):
            # 没通知的入库单行删掉
            for line in m.line_in_ids:
                if not line.notice_line_id:
                    line.unlink()
            # 入库单标记为已通知
            m.noticed = True
            m.express_type = self.express_type
            m.express_code = self.express_code
        self.write({'state': 'done'})

    def notice_draft(self):
        """撤销确认到货通知单"""
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销%s' % self._description)
        # 找到所有关联的入库单行
        for line in self.env['wh.move.line'].search([('notice_line_id', 'in', self.line_ids.ids)]):
            line.notice_line_id = False
            line.move_id.noticed = False
            line.move_id.express_type = False
            line.move_id.express_code = False
        # 把入库单已通知标记去掉
        self.state = 'draft'

    @api.constrains('line_ids')
    def _check_line_ids(self):
        lines = []
        for line in self.line_ids:
            line_id = line.buy_line_id.id
            if line_id in lines:
                raise ValidationError('同一订单行%s %s不能重复通知'
                                      % (line.buy_line_id.order_id.name, line.buy_line_id.goods_id.name))
            else:
                lines.append(line_id)


class ArrivalNoticeLine(models.Model):
    _name = 'arrival.notice.line'
    _description = '到货通知行'
    _order = 'buy_line_id'

    notice_id = fields.Many2one('arrival.notice', index=True, string="通知号", ondelete='cascade')

    buy_line_id = fields.Many2one('buy.order.line',
                                  '采购单行', ondelete='cascade',
                                  required=True,                              
                                  help='对应的采购订单行')
    goods_id = fields.Many2one('goods', '商品', help='商品', related='buy_line_id.goods_id')
    attribute_id = fields.Many2one('attribute',
                                   '属性',
                                   help='商品的属性，当商品有属性时，该字段必输', related="buy_line_id.attribute_id")
    qty = fields.Float('商品数量')

    @api.onchange('buy_line_id')
    def onchange_buy_line_id(self):
        if self.buy_line_id:
            self.qty = self.buy_line_id.quantity - self.buy_line_id.quantity_in
            if self.qty <= 0:
                self.buy_line_id = False
                return {
                    'warning':{
                        'title': '此货物已收完',
                        'message': '改采购订单行已完成收货.'
                    }
                }
    
           
class BuyOrderLine(models.Model):
    _inherit = "buy.order.line"

    def name_get(self):
        """在many2one字段里显示 采购单号_商品名称"""
        res = []
        for Line in self:
            res.append((Line.id,Line.order_id.name + '_' + Line.goods_id.name))
        return res 
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """按着订单号搜索"""
        args = args or []
        if name:
            order_line_ids = self.search([('order_id.name', operator, name)] + args)
            return order_line_ids.name_get()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)


class WhMove(models.Model):
    _inherit = 'wh.move'
    
    noticed = fields.Boolean('已通知')


class WhMoveLine(models.Model):
    _inherit = 'wh.move.line'

    notice_line_id = fields.Many2one('arrival.notice.line', string="通知单行")
    

    

    
