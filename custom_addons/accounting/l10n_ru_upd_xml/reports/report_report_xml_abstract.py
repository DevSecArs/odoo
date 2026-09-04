# License AGPL-3.0 or later (https://www.gnuorg/licenses/agpl.html).

from base64 import b64decode
from xml.dom import minidom

from lxml import etree

from odoo import api, models,SUPERUSER_ID
from odoo.exceptions import ValidationError


class ReportXmlAbstract(models.AbstractModel):
    _name = "report.upd_xml.abstract"
    _description = "Abstract XML Report"

    @api.model
    def generate_report(self, ir_report, docids, data=None):
        data = data or {}
        data.setdefault("report_type", "text")
        data = ir_report._get_rendering_context(ir_report, docids, data)

        result_bin = ir_report._render_template(ir_report.report_name, data)

        parsed_result_bin = minidom.parseString(result_bin)
        result = parsed_result_bin.toprettyxml(indent="    ")

        # remove empty lines
        utf8 = "UTF-8"
        cp1251="WINDOWS-1251"
        result = "\n".join(
            line for line in result.splitlines() if line and not line.isspace()
        ).encode('utf8')

        content = etree.tostring(
            etree.fromstring(result),
            encoding=ir_report.xml_encoding or cp1251,
            xml_declaration=True,
            pretty_print=True,
        )
        return content, "xml"

    @api.model
    def _get_report_values(self, docids, data=None):
        return data or {}

        # if not data:
        #     data = {}
        # return data.decode('cp1251')
