from odoo import http
from odoo.http import request
from datetime import datetime, date
import urllib.parse


class ActRevise(http.Controller):

    @http.route(['/my/act_revise/<string:act>'], type='http', auth="public", website=True)
    def print_report(self, act):
        # act параметр содержит имя файла из URL (обычно "a" для сокращенного доступа)
        partner = request.env.user.partner_id.parent_id.id
        partner_name = request.env.user.partner_id.parent_id.name
        if not partner:
            partner = request.env.user.partner_id.id
            partner_name = request.env.user.partner_id.name
        company = request.env.user.company_id.id
        company_name = request.env.user.company_id.name
        today = date.today()
        d1 = today.strftime("%d.%m.%y")

        wizard_data = {
            "target_move": "posted",
            "hide_account_at_0": True,
            "foreign_currency": True,
            "company_id": company,
            "partner_id": partner,
            "show_cost_center": True,
            "centralize": True
        }
        wizard_record = request.env['general.ledger.act_revise.wizard'].sudo().create(wizard_data)

        action = request.env.ref('l10n_ru_act_rev.action_general_ledger_wizard').read()[0]
        action['res_id'] = wizard_record.id
        action['context'] = dict(request.env.context)
        return request.redirect('/web#action=' + str(action['id']) + '&id=' + str(wizard_record.id) + '&view_type=form')

    @http.route(['/my/act_revise_contact/<string:act>'], type='http', auth="public", website=True)
    def print_report_contact(self, act, date_to, date_from, target_move, company, partner):
        # act параметр содержит имя файла из URL, но не используется в текущей реализации
        # так как мы генерируем имя файла на основе предпочтений русской локализации
        partner_id = int(partner) or 'default_partner_value'
        company_id = int(company)
        wizard_data = {"date_to": date_to,
                       "date_from": date_from,
                       "target_move": target_move,
                       "hide_account_at_0": True,
                       "foreign_currency": True,
                       "company_id": company_id,
                       "partner_id": partner_id,
                       "show_cost_center": True,
                       "centralize": True}
        t = request.env['general.ledger.act_revise.wizard'].sudo().create(wizard_data)
        data = t._prepare_report_general_ledger()
        
        # Генерируем правильное имя файла
        partner_obj = request.env['res.partner'].sudo().browse(partner_id)
        company_obj = request.env['res.company'].sudo().browse(company_id)
        
        # Используем имя партнера для файла
        partner_name = partner_obj.parent_id.name if partner_obj.parent_id else partner_obj.name
        # Очищаем имя от недопустимых символов для имени файла
        partner_name_clean = ''.join(c for c in partner_name if c.isalnum() or c in (' ', '-', '_')).strip()
        
        # Форматируем дату
        date_from_formatted = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d-%m-%Y')
        date_to_formatted = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d-%m-%Y')
        
        # Создаем имя файла на русском языке согласно предпочтениям пользователя
        filename = f"Акт сверки {partner_name_clean} {date_from_formatted} - {date_to_formatted}.pdf"
        
        # Кодируем имя файла для корректного отображения русских символов
        filename_encoded = urllib.parse.quote(filename.encode('utf-8'))
        
        pdf, _ = request.env['ir.actions.report']._render_qweb_pdf(
            'l10n_ru_act_rev.action_print_report_general_ledger_qweb', res_ids=t.id, data=data)
            
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'), 
            ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{filename_encoded}')
        ]
        return request.make_response(pdf, headers=pdfhttpheaders)