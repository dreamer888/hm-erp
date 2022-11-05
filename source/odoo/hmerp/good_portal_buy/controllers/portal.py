from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.osv import expression


class PortalBuy(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_address_id.partner_id

        BuyOrder = request.env['buy.order'].sudo()
        BuyOrderLine = request.env['buy.order.line'].sudo()
        buy_order_count = BuyOrder.search_count([
            ('partner_id', '=', partner.id),
            ('type', '=', 'buy'),
            ('state', 'in', ['done']),
            ('goods_state', 'in', ['未入库', '部分入库'])
        ])
        all_line = BuyOrderLine.search([
            ('order_id.partner_id', '=', partner.id),
            ('order_id.type', '=', 'buy'),
            ('order_id.state', '=', 'done'),
            ('order_id.goods_state', '!=', '部分入库剩余作废'),
        ])
        
        # 采购欠交数量
        todo_in = 0 
        for l in all_line:
            if l.quantity_in < l.quantity:
                todo_in += l.quantity - l.quantity_in
        values.update({
            'buy_order_count': buy_order_count,
            'todo_in': int(todo_in),
        })
        return values
    
    #
    # Buy Orders
    #
    @http.route(['/my/buy/orders', '/my/buy/orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_buy_orders(self, page=1, date_begin=None, date_end=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_address_id.partner_id
        BuyOrder = request.env['buy.order'].sudo()

        domain = [
            ('partner_id', '=', partner.id),
            ('type', '=', 'buy'),
        ]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin),
                       ('create_date', '<=', date_end)]

        # count for pager
        order_count = BuyOrder.search_count(domain)
        # pager
        pager = request.website.pager(
            url="/my/buy/orders",
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=order_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        orders = BuyOrder.search(
            domain, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'date': date_begin,
            'orders': orders,
            'page_name': 'order',
            'pager': pager,
            'default_url': '/my/buy/orders',
        })
        return request.render("good_portal_buy.portal_my_buy_orders", values)

    @http.route(['/my/buy/orders/<int:order>'], type='http', auth="user", website=True)
    def buy_orders_followup(self, order=None, **kw):
        # check if order belong to user
        partner = request.env.user.partner_address_id.partner_id
        domain = [
            ('id', '=', order),
            ('partner_id', '=', partner.id),
            ('type', '=', 'buy'),
        ]
        BuyOrder = request.env['buy.order'].sudo()
        order_count = BuyOrder.search_count(domain)
        # if exist
        if order_count>0:
            the_order = request.env['buy.order'].browse([order])
            order_sudo = the_order.sudo()
            return request.render("good_portal_buy.buy_orders_followup", {
                'order': order_sudo,
            })
        else:
            # order_sudo = None
            return "Error"
        #
    # Buy Orders
    #
    @http.route(['/my/buy/order/lines', '/my/buy/orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_buy_order_lines(self, page=1, date_begin=None, date_end=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_address_id.partner_id
        BuyOrderLine = request.env['buy.order.line'].sudo()

        domain = [
            ('order_id.partner_id', '=', partner.id),
            ('order_id.state', '=', 'done'),
            ('order_id.goods_state', '!=', '部分入库剩余作废'),
            ('order_id.type', '=', 'buy'),
        ]

        # content according to pager and archive selected
        order_lines = BuyOrderLine.search(
            domain, order='goods_id, attribute_id, order_id DESC')
        
        # {(goods_id1, attribute_id1):
        #      [[order1, quantity_1, quantity_in1,date1]...]...}
        sum_dict = {}
        for l in order_lines:
            if l.quantity > l.quantity_in:
                new_key = (l.goods_id, l.attribute_id)
                if new_key in list(sum_dict.keys()):
                    sum_dict[new_key].append(
                        [l.order_id,
                         l.quantity,
                         l.quantity_in])
                else:
                    sum_dict[new_key] = [
                        [l.order_id,
                         l.quantity,
                         l.quantity_in], ]
        todo_lines = []
        for good_key in list(sum_dict.keys()):
            goods_id = good_key[0]
            attribute_id = good_key[1]
            sum_quantity = 0
            sum_todo = 0
            order_list = ''
            for o in sum_dict[good_key]:
                sum_quantity += o[1]
                sum_todo += o[1] - o[2]
                order_list += '''
               <p><a href="/my/buy/orders/%d">%s</a> %s</p>
                ''' % (o[0].id, o[0].name, o[0].planned_date)
            todo_lines.append(
                [goods_id, attribute_id, sum_quantity, sum_todo, order_list])

        values.update({
            'todo_lines': todo_lines,
        })
        return request.render("good_portal_buy.portal_my_buy_order_lines", values)
