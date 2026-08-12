# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, exceptions, _
from datetime import datetime
import re
import pymorphy2
import base64 # Для работы с base64, если 'img' это байты

# Старые константы и функции, связанные с numeral, удалены,
# так как их функциональность теперь обеспечивается res.currency.amount_to_text.

class Partner_Bank(models.Model):
    _inherit = 'res.partner.bank'
    bank_corr_acc = fields.Char('Кор.счет')

class Company(models.Model):
    _inherit = 'res.company'

    inn = fields.Char(related='partner_id.inn', readonly=False)
    kpp = fields.Char(related='partner_id.kpp', readonly=False)
    okpo = fields.Char(related='partner_id.okpo', readonly=False)
    chief_id = fields.Many2one('res.users', 'Имя директора')
    stamp = fields.Binary("Stamp")

class Partner(models.Model):
    _inherit = 'res.partner'
    ogrn = fields.Char('ОГРН')
    okpo = fields.Char('ОКПО')
    inn = fields.Char('ИНН')
    kpp = fields.Char('KPP')
    passport = fields.Char('Паспорт')


class Report_contract_customer(models.Model):
    _inherit = 'partner.contract.customer'

    def img(self, img, type='png', width=0, height=0):
        # Предполагаем, что `img` уже является строкой base64.
        # Если `img` - это bytes, то используйте img.decode('ascii') или img.decode('utf-8')
        if width:
            width_attr = "width='%spx'" % (width)
        else:
            width_attr = " "
        if height:
            height_attr = "height='%spx'" % (height)
        else:
            height_attr = " "
        
        return "<img %s %s src='data:image/%s;base64,%s' />" % (
            width_attr,
            height_attr,
            type,
            img # Изменено: предполагается, что img уже строка base64
        )

    def numer(self, name):
        if name:
            numeration = re.findall(r'\d+$', name)
            if numeration: return numeration[0]
        return ''

    def ru_date(self, date):
        # Используйте стандартные методы Odoo или datetime для форматирования даты
        if date:
            # Преобразование строки даты в объект datetime
            date_obj = fields.Date.from_string(date) if isinstance(date, str) else date
            # Форматирование даты
            # Для более сложных русских склонений месяцев может потребоваться PyBabel или аналогичная библиотека
            # В данном примере используется простой подход, который может быть не идеален для всех склонений
            month_names = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                           'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
            return f'"{date_obj.day:02d}" {month_names[date_obj.month - 1]} {date_obj.year} года'
        return ''

    def ru_date2(self, date):
        if date:
            # Преобразование строки даты в объект datetime
            date_obj = fields.Datetime.from_string(date) if isinstance(date, str) else date
            month_names = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                           'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
            return f'{date_obj.day:02d} {month_names[date_obj.month - 1]} {date_obj.year} г.'
        return ''

    def in_words(self, number, currency_code='RUB'):
        """Преобразует число в слова, используя стандартный метод Odoo."""
        if not isinstance(number, (int, float)):
            return ""
        currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        if not currency:
            # Можно выбросить исключение или вернуть пустую строку в зависимости от требований
            return _("Currency '%s' not found to convert amount to text.", currency_code)
        return currency.amount_to_text(number)

    def rubles(self, amount, currency_code='RUB'):
        """Преобразует сумму в рубли и копейки прописью, используя стандартный метод Odoo."""
        if not isinstance(amount, (int, float)):
            return ""
        currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        if not currency:
            # Можно выбросить исключение или вернуть пустую строку
            return _("Currency '%s' not found to convert amount to text.", currency_code)
        
        # Метод amount_to_text в res.currency уже возвращает полный текст с рублями и копейками
        return currency.amount_to_text(amount)


    def initials(self, fio):
        if fio:
            parts = fio.split()
            if not parts:
                return ''
            
            result = [parts[0]]
            for part in parts[1:]:
                result.append(part[0:1] + '.')
            return ' '.join(result).strip()
        return ''

    def address(self, partner):
        repr_parts = []
        if partner.zip: repr_parts.append(partner.zip)
        if partner.city: repr_parts.append(partner.city)
        if partner.street: repr_parts.append(partner.street)
        if partner.street2: repr_parts.append(partner.street2)
        return ', '.join(repr_parts)

    def address_delivery(self, partner):
        if partner:
            # Используем search_count, чтобы убедиться в наличии, затем search для получения объекта
            addr = self.env['res.partner'].search([('parent_id', '=', partner.id), ('type', '=', 'delivery')], limit=1)
            repr_parts = []
            if addr:
                if addr.zip: repr_parts.append(addr.zip)
                if addr.city: repr_parts.append(addr.city)
                if addr.street: repr_parts.append(addr.street)
                if addr.street2: repr_parts.append(addr.street2)
                return ', '.join(repr_parts)
        return '' # Возвращаем пустую строку, если партнер или адрес доставки не найден

    def get_function_print(self, function):
        morph = pymorphy2.MorphAnalyzer()
        if function:
            f = morph.parse(function)[0]
            # Убедитесь, что 'gent' является правильной формой склонения
            f = f.inflect({'gent'})
            if f:
                return f.word.title()
        return ''

    def get_function_partnerip(self, partner):
        director = self.env['res.partner'].search([('parent_id', '=', partner.id), ('type', '=', 'director')], limit=1)
        if director and director.function:
            return director.function
        return ''

    def get_function_partner(self, partner):
        res = []
        morph = pymorphy2.MorphAnalyzer()
        if partner:
            director = self.env['res.partner'].search([('parent_id', '=', partner.id), ('type', '=', 'director')], limit=1)
            if director and director.function:
                list_f = str(director.function).split(' ')
                for func in list_f:
                    f = morph.parse(func)[0]
                    f_inflected = f.inflect({'gent'})
                    if f_inflected:
                        res.append(f_inflected.word)
                return ' '.join(res)
        return ''

    def get_function_partner1(self, partner):
        if partner:
            # Handle both partner object and partner ID
            if isinstance(partner, int):
                partner_obj = self.env['res.partner'].browse(partner)
            else:
                partner_obj = partner
            
            director = self.env['res.partner'].search([('parent_id', '=', partner_obj.id), ('type', '=', 'director')], limit=1)
            if director and director.function:
                return director.function
        return ''

    def get_date_text(self, date):
        month_list = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября',
                      'ноября', 'декабря']
        if date:
            # Проверяем тип date, если это datetime объект, используем его напрямую
            date_obj = date
            if isinstance(date, str):
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    # Если формат даты другой, добавьте соответствующую обработку
                    return ''
            
            return f'"{date_obj.day:02d}" {month_list[date_obj.month - 1]} {date_obj.year} г.'
        return ''

    def get_bank(self, partner):
        repr_parts = []
        bank = None
        if partner.bank_ids:
            bank = partner.bank_ids[0]
        elif partner.parent_id and partner.parent_id.bank_ids: # Проверка на наличие parent_id
            bank = partner.parent_id.bank_ids[0]
            
        if bank:
            if bank.bank_name: repr_parts.append(bank.bank_name)
            if bank.acc_number: repr_parts.append(u"Р/счет " + bank.acc_number)
            if bank.bank_bic: repr_parts.append(u"БИК " + bank.bank_bic)
            # Проверьте, существует ли поле bank_corr_acc в res.partner.bank
            # (это пользовательское поле, которое вы добавили)
            if bank.bank_corr_acc: repr_parts.append(u"к/с " + bank.bank_corr_acc)
        return '<br/>'.join(repr_parts)