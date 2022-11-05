from odoo.exceptions import UserError
from odoo import models, fields, api


class Country(models.Model):
    _name = 'country'
    _description = '国家'

    name = fields.Char('国家名')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class CountryState(models.Model):
    _name = 'country.state'
    _description = '省/直辖市/自治区'

    country_id = fields.Many2one('country', '国家')
    name = fields.Char('名称', required=True)
    code = fields.Char('编号', required=True)
    city_ids = fields.One2many('all.city', 'province_id', '下辖市/区')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class AllCity(models.Model):
    _name = 'all.city'
    _rec_name = 'city_name'
    _description = '地级市'
    city_name = fields.Char('名称', required=True)
    country_ids = fields.One2many('all.county', 'city_id', '下辖县/市')
    province_id = fields.Many2one('country.state', '省/直辖市/自治区',
                                  required=True,
                                  domain="[('country_id.name','=','中国')]")
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class AllCounty(models.Model):
    _name = 'all.county'
    _rec_name = 'county_name'
    _description = '县/市/区'

    province_id = fields.Many2one('country.state', '省', related='city_id.province_id')
    city_id = fields.Many2one('all.city', '地级市', required=True)
    county_name = fields.Char('名称', required=True)
    description = fields.Char('描述')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)


class StateCityCounty(models.Model):
    _name = 'state.city.county'
    _description = '县'

    province_id = fields.Many2one('country.state', '省',
                                  domain="[('country_id.name','=','中国')]")
    city_id = fields.Many2one('all.city', '市')
    county_id = fields.Many2one('all.county', '区县')
    company_id = fields.Many2one(
        'res.company',
        string='公司',
        change_default=True,
        default=lambda self: self.env.company)

    @api.onchange('province_id')
    def onchange_province(self):
        # 为地址填写时方便，当选定省时 ，市区的列表里面只有所选省的
        if self.province_id:
            domain_dict = {'city_id': [
                ('province_id', '=', self.province_id.id)]}
            if self.city_id:
                if self.city_id.province_id == self.province_id:
                    if self.county_id:
                        if self.county_id.city_id == self.city_id:
                            domain_dict = {}
                        else:
                            self.county_id = False
                else:
                    self.city_id = False
        else:
            self.city_id = False
            self.county_id = False
            domain_dict = {'city_id': [], 'county_id': []}
        return {'domain': domain_dict}

    @api.onchange('city_id')
    def onchange_city(self):
        # 为地址填写时方便，当选定市时 ，县区的列表里面只有所选市的
        if self.city_id:
            domain_dict = {'county_id': [('city_id', '=', self.city_id.id)]}
            province = self.city_id.province_id
            if not self.province_id:
                if self.county_id:
                    if self.county_id.city_id != self.city_id:
                        self.county_id = False
                        self.province_id = province
                else:
                    self.province_id = province
            else:
                domain_dict.update(
                    {'city_id': [('province_id', '=', province.id)]})
                if self.county_id:
                    if self.county_id.city_id == self.city_id:
                        if province != self.province_id:
                            self.province_id = province
                    else:
                        if province != self.province_id:
                            self.province_id = province
                            self.county_id = False
                        else:
                            self.county_id = False
                else:
                    if province != self.province_id:
                        self.province_id = province
        else:
            self.county_id = False
            domain_dict = {'county_id': []}
        return {'domain': domain_dict}

    @api.onchange('county_id')
    def onchange_county(self):
        # 选定了一个区县，自动填充其所属的省和市
        if self.county_id and self.county_id.city_id and self.county_id.city_id.province_id:
            city_obj = self.county_id.city_id
            self.city_id = city_obj
            self.province_id = city_obj.province_id
            return {'domain': {'county_id': [('city_id', '=', city_obj.id)]}}


class PartnerAddress(models.Model):
    _name = 'partner.address'
    _inherit = "state.city.county"
    _description = '联系人地址'
    _order = 'address_func'
    _rec_name = 'contact'

    partner_id = fields.Many2one('partner', '业务伙伴')
    contact = fields.Char('联系人', required=True)
    mobile = fields.Char('手机')
    phone = fields.Char('座机')
    qq = fields.Char('QQ')
    email = fields.Char('邮箱')
    town = fields.Char('乡镇')
    detail_address = fields.Char('详细地址')
    is_default_add = fields.Boolean('默认收货人')
    department = fields.Char('部门')
    job = fields.Char('职务')
    supervisor_id = fields.Many2one('partner.address','上级',domain="[('partner_id','=',partner_id)]")
    gone = fields.Boolean('已离职')
    note = fields.Text('备注')
    address_func = fields.Many2one('core.value', '联系人类型',
                            ondelete='restrict',
                            domain=[('type', '=', 'address_func')],
                            context={'type': 'address_func'})
        
    def name_get(self):
        res = []
        for adds in self:
            add_str = '%s%s%s%s%s' % (
                                      adds.province_id and adds.province_id.name or '',
                                      adds.city_id and adds.city_id.city_name or '',
                                      adds.county_id and adds.county_id.county_name or '',
                                      adds.town or '',
                                      adds.detail_address or '')
            res.append((adds.id, add_str))
        return res

class Partner(models.Model):
    _inherit = 'partner'

    def _put_info_to_partner(self, child):
        self.contact = child.contact
        self.mobile = child.mobile
        self.phone = child.phone
        self.qq = child.qq
        address = '%s%s%s%s%s' % (child.province_id and child.province_id.name or '',
                                  child.city_id and child.city_id.city_name or '',
                                  child.county_id and child.county_id.county_name or '',
                                  child.town or '',
                                  child.detail_address or '')
        self.address = address

    @api.depends('child_ids.is_default_add', 'child_ids.province_id', 'child_ids.city_id', 'child_ids.county_id', 'child_ids.town', 'child_ids.detail_address')
    def _compute_partner_address(selfs):
        '''如果业务伙伴地址中有默认地址，则显示在业务伙伴列表上'''
        for self in selfs:
            self.contact = self.mobile = self.phone = self.qq = self.address = ""
            for child in self.child_ids:
                if child.is_default_add:  # 如果有默认地址取默认地址
                    self._put_info_to_partner(child)

            # 如果没有默认地址取第一个联系人的
            if not any([child.is_default_add for child in self.child_ids]):
                partners_add = self.env['partner.address'].search(
                    [('partner_id', '=', self.id)], order='id')
                child = partners_add and partners_add[0] or False
                if child:
                    self._put_info_to_partner(child)

    child_ids = fields.One2many('partner.address', 'partner_id', '业务伙伴地址')
    contact = fields.Char(
        '联系人', compute='_compute_partner_address', store=True)
    mobile = fields.Char('手机', compute='_compute_partner_address', store=True)
    phone = fields.Char('座机', compute='_compute_partner_address', store=True)
    qq = fields.Char('QQ', compute='_compute_partner_address', store=True)
    address = fields.Char(
        '送货地址', compute='_compute_partner_address', store=True)
