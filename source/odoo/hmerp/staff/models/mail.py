
from odoo import models, api
from odoo import models, fields
from datetime import datetime


class MailMessage(models.Model):

    _inherit = 'mail.message'

    @api.model
    def staff_birthday_message(self):
        '''员工生日当天，whole company 会收到祝福信息'''
        newid = []
        staff_obj = self.env["staff"]

        for staff in staff_obj.search([]):
            if not staff.birthday:
                continue
            # 获取当前月日     和    员工生日
            now = datetime.now().strftime("%m-%d")
            staff_bir = staff.birthday.strftime("%m-%d")
            if now == staff_bir:
                values = {}
                # 创建一条祝福信息
                values['subject'] = "生日快乐！"
                values['model'] = "mail.channel"
                values['body'] = staff.name + "，祝你生日快乐!"
                values['res_id'] = 1
                newid.append(self.create(values))
        return newid
