# -*- coding: utf-8 -*-
from odoo import api, fields, models


class hire_applicant(models.Model):
    _inherit = "hire.applicant"

    survey_id = fields.Many2one('survey.survey', related='job_id.survey_id', string="问卷")
    response_id = fields.Many2one('survey.user_input', "负责人", ondelete="set null")

    def action_start_survey(self):
        '''开始面试'''
        self.ensure_one()
        # create a response and link it to this applicant
        if not self.response_id:
            response = self.env['survey.user_input'].create({'survey_id': self.survey_id.id})
            self.response_id = response.id
        else:
            response = self.response_id
        # grab the token of the response and start surveying
        return self.survey_id.with_context(survey_token=response.token).action_start_survey()
