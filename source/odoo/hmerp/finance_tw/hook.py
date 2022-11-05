# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def pre_init_remove_constraint(cr):
    cr.execute(
        """ALTER TABLE finance_account DROP CONSTRAINT finance_account_code;"""
        """ALTER TABLE finance_account DROP CONSTRAINT finance_account_name_uniq;"""
    )
    return True


#  ALTER TABLE table_name
# ADD CONSTRAINT constraint_name UNIQUE (column1, column2, ... column_n);
def post_init_constraint(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """ALTER TABLE finance_account ADD CONSTRAINT finance_account_code UNIQUE(code);"""
        """ALTER TABLE finance_account ADD CONSTRAINT finance_account_name_uniq UNIQUE(name);"""
    )
    return True
