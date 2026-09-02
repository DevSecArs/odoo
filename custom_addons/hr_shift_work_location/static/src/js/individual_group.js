/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { RelationalModel } from "@web/model/relational_model/relational_model";

const SHIFT_MODELS = new Set([
    "hr.shift.planning.shift",
    "hr.shift.planning.line",
]);

patch(RelationalModel.prototype, {
    async _loadGroupedList(config) {
        const opensIndividualGroup =
            SHIFT_MODELS.has(config.resModel) &&
            config.groupBy[0]?.split(":")[0] === "template_id";
        const individualGroupWasLoaded = Object.hasOwn(
            config.groups || {},
            false
        );
        const result = await super._loadGroupedList(...arguments);
        if (!opensIndividualGroup || individualGroupWasLoaded) {
            return result;
        }

        const individualGroup = result.groups.find((group) => !group.value);
        const groupConfig = individualGroup
            ? config.groups[individualGroup.value]
            : null;
        if (!individualGroup || !groupConfig?.isFolded) {
            return result;
        }

        groupConfig.isFolded = false;
        if (individualGroup.count > 0) {
            const response = await this._loadData(groupConfig.list);
            if (config.groupBy.length > 1) {
                individualGroup.groups = response?.groups || [];
                individualGroup.length = response?.length || 0;
            } else {
                individualGroup.records = response?.records || [];
            }
        }
        return result;
    },
});
