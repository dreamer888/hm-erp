from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    partner_address_id = fields.Many2one('partner.address', '业务伙伴联系人')

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        '''
        避免内部单据选择用户时选到业务伙伴的门户用户
        '''
        if args is None:
            args = []
        # 如果要选外部用户，就传context
        if not self.env.context.get('share'):
            args.append(('share', '=', False))
        else:
            args.append(('share', '=', True))
        return super(ResUsers, self).name_search(
            name=name, args=args, operator=operator, limit=limit)
