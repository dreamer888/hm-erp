from odoo import models, fields, api
from odoo.exceptions import UserError


class PartnerAddress(models.Model):
    _inherit = 'partner.address'

    user_id = fields.Many2one('res.users', string='对应用户')

    def create_portal_user(self):
        """
        创建门户用户
        """
        if self.user_id:
            raise UserError('该联系人已存在门户用户')
        if not self.contact or not self.mobile:
            raise UserError('请输入联系人的名字和手机号')
        values = {
            'name': self.contact,
            'login': self.mobile,
            'partner_address_id': self.id,
            'company_id': self.env.company.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        }
        user = self.env['res.users'].sudo().create(values)
        user.partner_id.signup_prepare()
        portal_url = user.partner_id.with_context(
            signup_force_type_in_url='reset', lang=user.lang
            )._get_signup_url_for_action()[user.partner_id.id]
        self.partner_id.message_post(body='登录用户 %s 创建成功。<br>请将下面链接发送给业务伙伴联系人修改密码 %s' %
                                        (user.name, portal_url))
        self.user_id = user.id
        return user
