/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { KanbanHeader } from "@web/views/kanban/kanban_header";

patch(KanbanHeader.prototype, {
    _getEmptyGroupLabel(fieldName) {
        const resModel =
            this.props.list.resModel || this.props.list.model?.root?.resModel;
        if (
            fieldName === "template_id" &&
            ["hr.shift.planning.shift", "hr.shift.planning.line"].includes(resModel)
        ) {
            return _t("Individual");
        }

        return super._getEmptyGroupLabel(fieldName);
    },
});
