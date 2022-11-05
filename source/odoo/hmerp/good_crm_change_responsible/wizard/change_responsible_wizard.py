from odoo import models, fields
from odoo.exceptions import UserError


class ChangeResponsibleWizard(models.TransientModel):
    _name = 'change.responsible.wizard'
    _description = '批量修改客户负责人'

    new_user_id = fields.Many2one('res.users', string='新负责人', required=True)
    partners = fields.Text('客户清单', help="每行一个客户名称", required=True)

    def do_change(self, partner_ids, new_user_id):
        # 修改客户的负责人
        self.env['partner'].browse(partner_ids).write(
            {'responsible_id': new_user_id})
        # 修改客户相关商机的负责人
        opps = self.env['opportunity'].search(
            [('partner_id', 'in', partner_ids)])
        opps.write({'user_id': new_user_id})

    def button_ok(self):
        partner_name_list = self.partners.split('\n')
        partner_ids = []
        for n in partner_name_list:
            if not n:   # 空行
                continue
            p = self.env['partner'].search([
                ('name', '=', n),
                ('c_category_id', '!=', False),
            ])
            if p:
                partner_ids.append(p.id)
            else:
                raise UserError('未找到客户 %s' % n)
        if not partner_ids:
            raise UserError('清单中无有效客户')
        message = '%d 个客户及其商机的的负责人员将被更新为 %s' % (
                                len(partner_ids), self.new_user_id.name)
        return self.env[self._name].with_context(
                    {'active_model': self._name}
                    ).open_dialog('do_change', {
                        'message': message,
                        'args': [partner_ids, self.new_user_id.id],
                    })
