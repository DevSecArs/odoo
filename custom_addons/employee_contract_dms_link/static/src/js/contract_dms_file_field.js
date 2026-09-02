/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import {
    Many2OneField,
    many2OneField,
    m2oTupleFromData,
} from "@web/views/fields/many2one/many2one_field";
import { useSelectCreate } from "@web/views/fields/relational_utils";


export class ContractDmsFileField extends Many2OneField {
    static template = "employee_contract_dms_link.ContractDmsFileField";

    setup() {
        super.setup();
        this.selectCreate = useSelectCreate({
            resModel: this.relation,
            activeActions: { create: false, link: false },
            onSelected: async (resIds) => {
                const [record] = await this.orm.read(
                    this.relation,
                    [resIds[0]],
                    ["display_name"],
                    { context: this.context }
                );
                await this.updateRecord(m2oTupleFromData(record));
            },
            onCreateEdit: () => {},
        });
    }

    openSelector() {
        this.selectCreate({
            domain: this.getDomain(),
            context: this.context,
            title: _t("Select Contract Document"),
        });
    }
}

export const contractDmsFileField = {
    ...many2OneField,
    component: ContractDmsFileField,
};

registry.category("fields").add("contract_dms_file_selector", contractDmsFileField);
