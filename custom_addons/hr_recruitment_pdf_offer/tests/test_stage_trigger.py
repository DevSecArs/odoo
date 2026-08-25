from .common import OfferPdfCase


class TestOfferPdfStageTrigger(OfferPdfCase):
    def test_stage_change_creates_one_activity_without_sending_email(self):
        template, _document = self.create_template_with_document()
        stage = self.env['hr.recruitment.stage'].create({
            'name': 'Offer',
            'offer_mail_template_id': template.id,
        })
        applicant = self.env['hr.applicant'].create({
            'candidate_id': self.env['hr.candidate'].create({
                'partner_name': 'Candidate', 'email_from': 'candidate@example.test',
            }).id,
            'company_id': self.env.company.id,
        })
        applicant.stage_id = stage
        self.assertTrue(applicant.offer_pdf_activity_id)
        self.assertFalse(self.env['mail.mail'].search([('res_id', '=', applicant.id), ('model', '=', 'hr.applicant')]))
        applicant.stage_id = stage
        self.assertEqual(len(applicant.activity_ids.filtered(lambda activity: activity.id == applicant.offer_pdf_activity_id.id)), 1)
