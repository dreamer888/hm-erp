# -*- coding: utf-8 -*-
###############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today Julius Network Solutions SARL <contact@julius.fr>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import copy
from odoo import api, models, fields, SUPERUSER_ID, _


class ir_model(models.Model):
    _inherit = 'ir.model'

    object_merger_model = fields.Boolean('Object Merger', default=False,
                                         help='If checked, by default the Object '
                                         'Merger configuration will get this '
                                         'module in the list')


class object_merger_settings(models.TransientModel):
    _name = 'object.merger.settings'
    _inherit = 'res.config.settings'
    _description = '对象合并配置'

    def _get_default_object_merger_models(self):
        return self.env.get('ir.model').\
            search([('object_merger_model', '=', True)])

    models_ids = fields.Many2many('ir.model',
                                  'object_merger_settings_model_rel',
                                  'object_merger_id', 'model_id', 'Models',
                                  domain=[('transient', '=', False)])

    _defaults = {
                 'models_ids': _get_default_object_merger_models,
                 }

    def update_field(self, vals):
        ## Init ##
        model_ids = []
        model_obj = self.env.get('ir.model')
        action_obj = self.env.get('ir.actions.act_window')
        field_obj = self.env.get('ir.model.fields')
        ## Process ##
        if not vals or not vals.get('models_ids', False):
            return False
        elif vals.get('models_ids') or model_ids[0][2]:
            model_ids = vals.get('models_ids')
            if isinstance(model_ids[0], (list)):
                model_ids = model_ids[0][2]
        # Unlink Previous Actions
        unlink_ids = action_obj.search([('res_model' , '=', 'object.merger')
                    ])
        for unlink_id in unlink_ids:
            unlink_id.unlink()
        # Put all models which were selected before back to not an object_merger
        model_not_merge_ids = model_obj.search([
                    ('id', 'not in', model_ids),
                    ('object_merger_model', '=', True),
                ])
        model_not_merge_ids.write({'object_merger_model' : False})
        
        # Put all models which are selected to be an object_merger
        model_obj.browse(model_ids).write({'object_merger_model' : True})
          
        ### Create New Fields ###
        object_merger_ids = model_obj.search([
                    ('model', '=', 'object.merger')
                ]).ids
        read_datas = model_obj.browse(model_ids).read(['id', 'model','name','object_merger_model'])
        for model in read_datas:
            field_name = 'x_' + model['model'].replace('.','_') + '_id'
            act_id = action_obj.create({
                 'name': "%s " % model['name'] + _("Merger"),
                 'type': 'ir.actions.act_window',
                 'res_model': 'object.merger',
                 'binding_model_id': model['id'],
                 'binding_view_types':'list',
                 'context': "{'field_to_read':'%s'}" % field_name,
                 'view_mode':'form',
                 'target': 'new',
            }).id
            field_name = 'x_' + model['model'].replace('.','_') + '_id'
            if not field_obj.search( [
                ('name', '=', field_name),
                ('model', '=', 'object.merger')]):
                field_data = {
                    'model': 'object.merger',
                    'model_id': object_merger_ids and object_merger_ids[0] or False,
                    'name': field_name,
                    'relation': model['model'],
                    'field_description': "%s " % model['name'] + _('To keep'),
                    'state': 'manual',
                    'ttype': 'many2one',
                }
                field_obj.sudo().create(field_data)
        return True
    
    @api.model
    def create(self,vals):
        """ create method """
        vals2 = copy.deepcopy(vals)
        result = super(object_merger_settings, self).create(vals2)
        ## Fields Process ##
        self.update_field(vals)
        return result
    
    def install(self):
#       Initialization of the configuration
        """ install method """
        for vals in self.read([]):
            result = self.update_field(vals)
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
