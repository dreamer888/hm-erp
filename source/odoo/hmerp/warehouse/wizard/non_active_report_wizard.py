
from odoo import models, fields, api
from datetime import datetime
import pytz
from lxml import etree


class NonActiveReport(models.TransientModel):
    _name = 'non.active.report'
    _description = '库龄报表'

    warehouse_id = fields.Many2one('warehouse', string='仓库')
    goods_id = fields.Many2one('goods', string='商品')
    attribute_id = fields.Many2one('attribute', string='属性')
    first_stage_day_qty = fields.Float(string='第一阶段数量')
    second_stage_day_qty = fields.Float(string='第二阶段数量')
    third_stage_day_qty = fields.Float(string='第三阶段数量')
    four_stage_day_qty = fields.Float(string='第四阶段数量')
    subtotal = fields.Float('合计')
    latest_move_date = fields.Datetime('最后发货日期')
    latest_move_qty = fields.Float('最后发货数量')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """
        继承系统自带的 视图构造方法 fields_view_get 实现动态的修改 呆滞报表的表头 string动态
        :param view_id:
        :param toolbar:
        :param submenu:
        :return:
        """
        res = super(NonActiveReport, self).fields_view_get(
            view_id=view_id, toolbar=toolbar, submenu=submenu)
        if self._context.get('first_stage_day'):
            now_date = datetime.strftime(
                datetime.now(pytz.timezone("UTC")), '%Y-%m-%d')
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='first_stage_day_qty']"):
                node.set('string', u"0~%s天" %
                         (self._context.get('first_stage_day')))
            for node in doc.xpath("//field[@name='second_stage_day_qty']"):
                node.set('string',
                         u"%s天~%s天" % (self._context.get('first_stage_day'), self._context.get('second_stage_day')))
            for node in doc.xpath("//field[@name='third_stage_day_qty']"):
                node.set('string',
                         u"%s天~%s天" % (self._context.get('second_stage_day'), self._context.get('third_stage_day')))
            for node in doc.xpath("//field[@name='four_stage_day_qty']"):
                node.set('string', u"大于%s天" %
                         (self._context.get('third_stage_day')))
            res['arch'] = etree.tostring(doc)
        return res


class NonActiveReportWizard(models.TransientModel):
    _name = 'non.active.report.wizard'
    _description = '库龄报表向导'

    warehouse_id = fields.Many2one('warehouse', string='仓库')
    first_stage_day = fields.Integer(string='第一阶段天数', required=True)
    second_stage_day = fields.Integer(string='第二阶段天数', required=True)
    third_stage_day = fields.Integer(string='第三阶段天数', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    
    def get_warehouse_goods_stage_data(self, warehouse_id, first_stage_day, second_stage_day, third_stage_day):
        """
        用sql 找到 系统 在所输入的时间阶段的对应的商品的 数量
        :param warehouse_id:  仓库id
        :param first_stage_day:  第一阶段天数
        :param second_stage_day:第一阶段天数
        :param third_stage_day: 第三阶段天数
        :return: 返回list dict
        """
        if warehouse_id:
            wahouse_id_sql = "AND wh_dest.id =%s" % (warehouse_id.id)
        else:
            wahouse_id_sql = "AND 1=1"
        now_date = datetime.strftime(
            datetime.now(pytz.timezone("UTC")), '%Y-%m-%d')
        vals = {'now_date': now_date, 'first_stage_day': first_stage_day, 'wahouse_id_sql': wahouse_id_sql,
                'second_stage_day': second_stage_day, 'third_stage_day': third_stage_day}

        self.env.cr.execute('''
            select
                stage_goods_date.warehouse_dest_id as warehouse_id,
                stage_goods_date.goods_id as goods_id,
                stage_goods_date.attribute_id as attribute_id,
                NULL as latest_move_date,
                NULL as latest_move_qty,
                COALESCE(sum(stage_goods_date.first_stage),0) as first_stage_day_qty,
                COALESCE(sum(stage_goods_date.second_stage),0) as second_stage_day_qty,
                COALESCE(sum(stage_goods_date.third_stage),0) as third_stage_day_qty,
                COALESCE(sum(stage_goods_date.four_stage),0) as four_stage_day_qty,
                sum(stage_goods_date.subtotal) as subtotal
                from  (select
                          CASE
                              when ('%(now_date)s' -line.date<=%(first_stage_day)d) then
                                  sum(line.qty_remaining)
                              end as first_stage,
                          CASE
                              when ('%(now_date)s'-line.date>%(first_stage_day)d and '%(now_date)s' -line.date<=%(second_stage_day)d) then
                                  sum(line.qty_remaining)
                              end as second_stage,
                          CASE
                              when ('%(now_date)s' -line.date>%(second_stage_day)d AND '%(now_date)s'-line.date<=%(third_stage_day)d) then
                                  sum(line.qty_remaining)
                              end as third_stage,
                          CASE
                              when ('%(now_date)s'-line.date > %(third_stage_day)d) then
                                  sum(line.qty_remaining)
                              end as four_stage,
                          line.goods_id as goods_id,
                          line.attribute_id as attribute_id,

                          line.warehouse_dest_id as warehouse_dest_id,
                          sum(line.qty_remaining) as subtotal
                      FROM wh_move_line line
                      LEFT JOIN warehouse wh_dest ON line.warehouse_dest_id = wh_dest.id
                      LEFT JOIN warehouse wh ON line.warehouse_id = wh.id
                      where line.state = 'done'
                        %(wahouse_id_sql)s
                      AND  wh_dest.type='stock'
                      GROUP BY line.warehouse_dest_id,line.goods_id,line.attribute_id,line.date) as stage_goods_date
              GROUP BY  stage_goods_date.warehouse_dest_id,stage_goods_date.goods_id,stage_goods_date.attribute_id
        ''' % vals)
        return self.env.cr.dictfetchall()

    
    def open_non_active_report(self):
        """

        :return:
         返回生成好的 库龄报表 记录的tree视图返回，让用户可以直接看到结果
        """
        data_vals_list = self.get_warehouse_goods_stage_data(self.warehouse_id, self.first_stage_day,
                                                             self.second_stage_day, self.third_stage_day)
        non_active_id_list = []
        for vals in data_vals_list:
            if vals.get('subtotal', 0) != 0:
                # 更新最后发货日期和最后发货数量
                latest_move_line = self.env['wh.move.line'].search([
                    ('state', '=', 'done'),
                    ('goods_id', '=', vals.get('goods_id')),
                    ('attribute_id', '=', vals.get('attribute_id')),
                    ('warehouse_id.type', '=', 'stock'),
                    ('warehouse_dest_id.type', '=', 'customer')], order='write_date DESC', limit=1)
                if latest_move_line:
                    vals['latest_move_date'] = latest_move_line.write_date
                    vals['latest_move_qty'] = latest_move_line.goods_qty

                active_row = self.env['non.active.report'].create(vals)
                non_active_id_list.append(active_row.id)

        view = self.env.ref('warehouse.non_active_report_tree')

        return {
            'name': '库龄报表',
            'view_mode': 'tree',
            'views': [(view.id, 'tree')],
            'res_model': 'non.active.report',
            'type': 'ir.actions.act_window',
            'target': 'main',
            'domain': [('id', 'in', non_active_id_list)],
            'limit': 65535,
            'context': {'first_stage_day': self.first_stage_day,
                        'second_stage_day': self.second_stage_day, 'third_stage_day': self.third_stage_day}
        }
