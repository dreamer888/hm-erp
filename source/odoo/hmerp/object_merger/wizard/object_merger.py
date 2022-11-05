# -*- coding: utf-8 -*-
###############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today Julius Network Solutions SARL <contact@julius.fr>
#    Copyright (C) 2022-Today Jeff Wang <jeff@osbzr.com>
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

from odoo import fields as old_fields
from odoo.tools import ustr
from odoo import models, fields, _, api
from odoo.exceptions import UserError


class object_merger(models.TransientModel):
    """
    Merges objects
    """
    _name = 'object.merger'
    _description = 'Merge objects'

    name = fields.Char()
    delete_if_not_active = fields.Boolean('Delete records if not active field',
                                          default=False)

    def fields_view_get(self, view_id=None, view_type='form',
                toolbar=False, submenu=False):
        res = super(object_merger, self).\
            fields_view_get(view_id, view_type,
                            toolbar=toolbar, submenu=False)
        object_ids = self.env.context.get('active_ids',[])
        active_model = self.env.context.get('active_model')
        field_name = 'x_' + (active_model and active_model.replace('.','_') or '') + '_id'
        res_fields = res['fields']
        if object_ids:
            view_part = """<label for='""" + field_name + """'/>
                    <div>
                        <field name='""" + field_name + \
                        """' required="1" domain="[(\'id\', \'in\', """ + \
                        str(object_ids) + """)]"/>
                    </div>"""
            res['arch'] = res['arch'].replace(
                    """<separator string="to_replace"/>""", view_part)
            field = self.fields_get([field_name])
            res_fields.update(field)
            res['fields'] = res_fields
            res['fields'][field_name]['domain'] = [('id', 'in', object_ids)]
            res['fields'][field_name]['required'] = True
        return res
    
    def action_merge(self):
        """
        Merges two (or more objects
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Lead to Opportunity IDs
        @param context: A standard dictionary for contextual values

        @return : {}
        """
        cr = self._cr
        active_model = self.env.context.get('active_model')
        if not active_model:
            raise UserError(_('The is no active model defined!'))
        model_env = self.env.get(active_model)
        object_ids = self.env.context.get('active_ids',[])
        field_to_read = self.env.context.get('field_to_read')
        field_list = field_to_read and [field_to_read] or []
        object = self.read(field_list)[0]
        if object and field_list and object[field_to_read]:
            object_id = object[field_to_read][0]
        else:
            raise UserError(_('Please select one value to keep'))
        cr.execute("SELECT name, model FROM ir_model_fields WHERE relation=%s "
                   "and ttype not in ('many2many', 'one2many');", (active_model, ))
        for name, model_raw in cr.fetchall():
            if hasattr(self.env.get(model_raw), '_auto'):
                if not self.env.get(model_raw)._auto:
                    continue
            if hasattr(self.env.get(model_raw), '_check_time'):
                continue
            else:
                if hasattr(self.env.get(model_raw), '_fields'):
                    model_raw_obj = self.env.get(model_raw)
                    if model_raw_obj._fields.get(name, False) and \
                            model_raw_obj._fields[name].type == 'many2one' and model_raw_obj._fields[name].store:
                        if hasattr(self.env.get(model_raw), '_table'):
                            model = self.env.get(model_raw)._table
                        else:
                            model = model_raw.replace('.', '_')
                        requete = "UPDATE %s SET %s = %s WHERE " \
                            "%s IN %s;" % (model, name, str(object_id),
                                           ustr(name), str(tuple(object_ids)))
                        cr.execute(requete)

        cr.execute("SELECT name, model FROM ir_model_fields WHERE "
                   "relation=%s AND ttype IN ('many2many');", (active_model,))
        for field, model in cr.fetchall():
            model_obj = self.env.get(model)
            field_data = model_obj._fields.get(field, False) \
                    and model_obj._fields[field].type == 'many2many' and model_obj._fields[field].store and model_obj._fields[field] or False
            if field_data:
                model_m2m, rel1, rel2 = field_data.relation, field_data.column1, field_data.column2
                requete = "UPDATE %s SET %s=%s WHERE %s " \
                    "IN %s AND %s NOT IN (SELECT DISTINCT(%s) " \
                    "FROM %s WHERE %s = %s);" % (model_m2m, rel2,
                                                 str(object_id),
                                                 ustr(rel2),
                                                 str(tuple(object_ids)),
                                                 rel1, rel1, model_m2m,
                                                 rel2, str(object_id))
                cr.execute(requete)
        cr.execute("SELECT name, model FROM ir_model_fields WHERE "
                   "name IN ('res_model', 'model');")
        for field, model in cr.fetchall():
            model_obj = self.env.get(model)
            if not model_obj:
                continue
            if field == 'model' and model_obj._fields.get('res_model', False):
                continue
            res_id = model_obj._fields.get('res_id')
            if res_id:
                requete = False
                if res_id.type == 'integer' or res_id.type == 'many2one':
                    requete = "UPDATE %s SET res_id = %s " \
                    "WHERE res_id IN %s AND " \
                    "%s = '%s';" % (model_obj._table,
                                    str(object_id),
                                    str(tuple(object_ids)),
                                    field,
                                    active_model)
                elif res_id.type == 'char':
                    requete = "UPDATE %s SET res_id = '%s' " \
                    "WHERE res_id IN %s AND " \
                    "%s = '%s';" % (model_obj._table,
                                    str(object_id),
                                    str(tuple([str(x) for x in object_ids])),
                                    field,
                                    active_model)
                if requete:
                    cr.execute(requete)
        unactive_object_ids = model_env.\
            search([
                             ('id', 'in', object_ids),
                             ('id', '<>', object_id),
                             ])
        if hasattr(model_env,'active'):
            unactive_object_ids.write(
                             {'active': False})
        else:
            read_data = self.read(['delete_if_not_active'])[0]
            if read_data['delete_if_not_active']:
                unactive_object_ids.unlink()
        cr.commit()
        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
