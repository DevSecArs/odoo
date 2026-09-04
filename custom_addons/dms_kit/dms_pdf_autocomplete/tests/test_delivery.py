from odoo.exceptions import ValidationError
from odoo.tests import new_test_user

from .common import DmsPdfAutocompleteCase


class TestPdfDelivery(DmsPdfAutocompleteCase):
    def _delivery(self, partners=None):
        wizard = self.create_wizard(partners=partners)
        wizard.action_prepare_mappings()
        wizard.action_prepare_values()
        wizard.write({'state': 'review'})
        action = wizard.action_open_delivery()
        delivery = self.env['dms.pdf.autocomplete.delivery.wizard'].browse(action['res_id'])
        return wizard, delivery

    def test_invalid_email_is_rejected(self):
        _wizard, delivery = self._delivery()
        delivery.recipient_ids.email_to = 'invalid'
        with self.assertRaises(ValidationError):
            delivery.action_send()

    def test_email_creates_one_mail_per_recipient(self):
        _wizard, delivery = self._delivery(self.partner_a | self.partner_b)
        before = self.env['mail.mail'].search_count([])
        delivery.action_send()
        self.assertEqual(self.env['mail.mail'].search_count([]) - before, 2)
        self.assertTrue(all(delivery.recipient_ids.mapped('mail_id')))
        self.assertTrue(all(row.mail_id.state == 'outgoing' for row in delivery.recipient_ids))
        self.assertTrue(all(len(row.mail_id.attachment_ids) == 1 for row in delivery.recipient_ids))

    def test_disabled_row_is_not_sent(self):
        _wizard, delivery = self._delivery(self.partner_a | self.partner_b)
        delivery.recipient_ids[0].send_enabled = False
        delivery.action_send()
        self.assertEqual(delivery.recipient_ids[0].delivery_state, 'skipped')
        self.assertEqual(delivery.recipient_ids[1].delivery_state, 'sent')

    def test_chat_requires_internal_user(self):
        _wizard, delivery = self._delivery()
        delivery.delivery_channel = 'chat'
        with self.assertRaises(ValidationError):
            delivery.action_send()

    def test_chat_posts_one_personal_message(self):
        user = new_test_user(
            self.env, login='pdf-chat-user', groups='base.group_user', name='PDF Chat User',
        )
        _wizard, delivery = self._delivery(user.partner_id)
        delivery.delivery_channel = 'chat'
        delivery.action_send()
        row = delivery.recipient_ids
        self.assertEqual(row.delivery_state, 'sent')
        self.assertTrue(row.message_id)
        self.assertEqual(len(row.message_id.attachment_ids), 1)
