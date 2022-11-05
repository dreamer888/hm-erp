# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

# 销售订单确认状态可选值
ORDER_STATES = [
    ('draft', '草稿'),
    ('done', '已确认'),
    ('cancel', '已作废')]

# 字段只读状态
READONLY_STATES = {
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class DeliveryNotice(models.Model):
    _name = 'delivery.notice'
    _description = '发货通知单'
    _rec_name = 'custom_id'
    _order = 'date desc, state desc, custom_id'

    line_ids = fields.One2many('delivery.notice.line', 'notice_id', '通知单行', states=READONLY_STATES)
    date = fields.Date(string='单据日期', default=fields.date.today(), help='单据日期，默认当天')
    custom_id = fields.Many2one('partner', string='客户',
                                domain=[('c_category_id', '!=', False)],
                                ondelete='restrict', states=READONLY_STATES, help='客户选择')
    express_type = fields.Char(string='承运商', help='承运商',)
    express_code = fields.Char(string='快递单号', help='快递单号',)
    state = fields.Selection(ORDER_STATES, '确认状态', readonly=True,
                             help="发货通知单的确认状态", index=True,
                             copy=False, default='draft')

    def get_lack_qty(self, line_id):
        """查缺货数量，通过发货通知单通知销售发货单"""
        line_obj_ids = self.env['wh.move.line'].search([('sell_line_id', '=', line_id), ('state', '=', 'draft')])
        lack_qty = 0
        for line_obj in line_obj_ids:
            lack_qty += line_obj.all_lack   # 计算缺货数量
        return lack_qty

    @api.onchange('custom_id')
    def onchange_custom_id(self):
        if self.custom_id:
            domain = [('custom_id', '=', self.custom_id.id), ('state', '=', 'draft')]
            if isinstance(self.id, int):
                domain.append(('id', '!=', self.id))
            if self.search(domain):
                self.custom_id = False
                return {'warning': {'title': '已存在未确认的通知单',
                                    'message': '建议修改原通知单而不是新建'}}
            self.line_ids = False
            newline_ids = []
            domain = [('order_id.state', '=', 'done'),
                      ('order_id.goods_state', 'in', ('部分出库', '未出库')),
                      ('order_id.partner_id', '=', self.custom_id.id)]  # 取销售订单已确认、非全部出库订单
            sell_order_line_ids = self.env['sell.order.line'].search(domain)
            for line in sell_order_line_ids:
                lack_qty = self.get_lack_qty(line.id)          # 计算销售出库单行商品缺货数量
                ok_qty = line.quantity - line.quantity_out
                if lack_qty > 0:
                    ok_qty -= lack_qty
                if ok_qty > 0:
                    newline = {'sell_line_id': line.id, 'qty': ok_qty}
                    newline_ids.append((0, 0, newline))
            self.line_ids = newline_ids
    
    def delivery_notice_done(self):
        """确认发货通知单"""
        self.ensure_one()
        if self.state == 'done':
            raise UserError('请不要重复确认')
        if not self.line_ids:
            raise UserError('请输入商品明细行')
        to_mark = []    # 要标记已通知的出库单
        for l in self.line_ids:
            # 找出采购单行对应的发货单行
            if l.goods_id.using_batch:
                if l.goods_id.force_batch_one:
                    # 序列号产品在生成发货单的时候已经是一号一行
                    i = l.qty
                    for move_line in self.env['wh.move.line'].search([('state', '=', 'draft'),
                                                                     ('sell_line_id', '=', l.sell_line_id.id)]):
                        if i > 0:
                            move_line.notice_line_id = l.id
                            to_mark.append(move_line.move_id.id)
                        i -= 1
                else:
                    # 不是序列号产品的批号在发货单生成时只有一行
                    move_line = self.env['wh.move.line'].search([('state', '=', 'draft'),
                                                                ('sell_line_id', '=', l.sell_line_id.id),
                                                                ('notice_line_id', '=', False)])
                    if move_line:
                        move_line.notice_line_id = l.id
                        move_line.goods_qty = l.qty
                        to_mark.append(move_line.move_id.id)
                    else:
                        raise UserError('只有"确认"状态的销售订单才可以通知仓库发货。'
                                        '当前销售订单可能未被确认或已被作废。'
                                        '销售单号：{}'.format(l.sell_line_id.order_id.name))
                        return
            else:
                move_line = self.env['wh.move.line'].search([('state', '=', 'draft'),
                                                            ('sell_line_id', '=', l.sell_line_id.id)])
                move_line.notice_line_id = l.id
                move_line.goods_qty = l.qty
                to_mark.append(move_line.move_id.id)
        for m in self.env['wh.move'].browse(set(to_mark)):
            # 没通知的发货单行删掉
            for line in m.line_in_ids:
                if not line.notice_line_id:
                    line.unlink()
            # 发货单标记为已通知
            m.noticed = True
            m.express_type = self.express_type
            m.express_code = self.express_code
        self.write({'state': 'done'})

    def delivery_notice_draft(self):
        """撤销确认发货通知单"""
        self.ensure_one()
        if self.state == 'draft':
            raise UserError('请不要重复撤销%s' % self._description)
        # 找到所有关联的发货单行，去掉确认功能填充的内容
        for line in self.env['wh.move.line'].search([('notice_line_id', 'in', self.line_ids.ids)]):
            line.notice_line_id = False
            line.move_id.noticed = False
            line.move_id.express_type = False
            line.move_id.express_code = False
        # 把发货单已通知标记去掉
        self.state = 'draft'


class DeliveryNoticeLine(models.Model):
    _name = 'delivery.notice.line'
    _description = '发货通知行'
    _order = 'sell_line_id'

    notice_id = fields.Many2one('delivery.notice', index=True, string="通知号", ondelete='cascade')
    sell_line_id = fields.Many2one('sell.order.line',
                                   '销售单行', ondelete='cascade',
                                   required=True,
                                   help='对应的销售订单行')
    goods_id = fields.Many2one('goods', '商品', help='商品', related='sell_line_id.goods_id')
    attribute_id = fields.Many2one('attribute',
                                   '属性',
                                   help='商品的属性，当商品有属性时，该字段必输', related="sell_line_id.attribute_id")
    qty = fields.Float('商品数量')

    @api.onchange('sell_line_id')
    def onchange_sell_line_id(self):
        if self.sell_line_id:
            self.qty = self.sell_line_id.quantity - self.sell_line_id.quantity_out
            if self.qty <= 0:
                self.sell_line_id = False
                return {
                    'warning': {
                        'title': '此货物已发完',
                        'message': '改销售订单行已完成发货.'
                    }
                }
    
           
class SellOrderLine(models.Model):
    _inherit = "sell.order.line"

    def name_get(self):
        """"在many2one字段里显示 销售订单号_商品名称"""
        res = []
        for Line in self:
            res.append((Line.id, Line.order_id.name + '_' + Line.goods_id.name))
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

    notice_line_id = fields.Many2one('delivery.notice.line', string="通知单行")
    

    

    
