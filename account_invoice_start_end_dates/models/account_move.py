# Copyright 2019-2021 Akretion France (https://akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        for move in self:
            for line in move.line_ids:
                if (
                    line.product_id
                    and line.must_have_dates
                    and (not line.start_date or not line.end_date)
                ):
                    raise UserError(
                        self.env._(
                            "Missing Start Date and End Date for invoice "
                            "line with Product '%(product_name)s' which has the "
                            "property 'Must Have Start/End Dates'.",
                            product_name=line.product_id.display_name,
                        )
                    )
        return super()._post(soft=soft)
