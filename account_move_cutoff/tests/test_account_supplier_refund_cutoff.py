# Copyright 2023 Foodles (https://www.foodles.co/)
# @author: Pierre Verkest <pierreverkest84@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import date

from freezegun import freeze_time

from odoo.tests import tagged

from .common import CommonAccountCutoffBaseCAse


@tagged("-at_install", "post_install")
class TestSupplierRefundCutoff(CommonAccountCutoffBaseCAse):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_expense = cls.env["account.account"].search(
            [
                (
                    "user_type_id",
                    "=",
                    cls.env.ref("account.data_account_type_expenses").id,
                )
            ],
            limit=1,
        )
        cls.account_expense.deferred_accrual_account_id = cls.account_cutoff
        cls.purchase_journal = cls.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1
        )

        cls.refund = cls._create_invoice(
            journal=cls.purchase_journal,
            move_type="in_refund",
            account=cls.account_expense,
        )

    def test_ensure_refund_without_start_end_date_are_postable(self):
        self.refund.line_ids.product_id.must_have_dates = False
        self.refund.line_ids.write({"start_date": False, "end_date": False})
        self.refund.action_post()
        self.assertEqual(self.refund.state, "posted")

    def test_account_refund_cutoff_equals(self):
        self.refund.line_ids.cutoff_method = "equal"
        with freeze_time("2023-01-15"):
            self.refund.action_post()
        self.assertEqual(self.refund.cutoff_move_count, 4)

    def test_account_refund_cutoff_monthly_factor_prorata(self):
        self.refund.line_ids.cutoff_method = "monthly_prorata_temporis"

        with freeze_time("2023-01-15"):
            self.refund.action_post()

        self.assertEqual(self.refund.cutoff_move_count, 4)

        cutoff_move = self.refund.cutoff_entry_ids.filtered(
            lambda move, move_date=date(2023, 1, 15): move.date == move_date
        )

        self.assertEqual(cutoff_move.journal_id, self.miscellaneous_journal)
        self.assertEqual(
            cutoff_move.ref,
            f"Advance expense recognition of {self.refund.name} (01 2023)",
        )
        self.assertAccountMoveLines(
            cutoff_move,
            [
                (
                    lambda ml: ml.debit > 0,
                    {
                        "account_id": self.account_expense,
                        "credit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                    },
                ),
                (
                    lambda ml: ml.credit > 0,
                    {
                        "account_id": self.account_cutoff,
                        "debit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case A" in ml.name,
                    {
                        "debit": 3420.68,
                        "analytic_account_id": self.analytic,
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 3, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case B" in ml.name,
                    {
                        "debit": 80.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 3, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case C" in ml.name,
                    {
                        "debit": 60.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 3, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case D" in ml.name,
                    {
                        "debit": 130.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case F" in ml.name,
                    {
                        "debit": 259.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case G" in ml.name,
                    {
                        "debit": 255.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 5, 1),
                        "end_date": date(2023, 5, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case I" in ml.name,
                    {
                        "debit": 1508.19,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 3, 15),
                    },
                ),
            ],
        )
        self.assertAlmostEqual(
            sum(
                cutoff_move.line_ids.filtered(lambda ml: ml.credit > 0).mapped("credit")
            ),
            5712.87,
            2,
        )

        deferred_feb_move = self.refund.cutoff_entry_ids.filtered(
            lambda move, move_date=date(2023, 2, 1): move.date == move_date
        )
        self.assertEqual(deferred_feb_move.journal_id, self.miscellaneous_journal)
        self.assertEqual(
            deferred_feb_move.ref,
            f"Advance expense adjustment of {self.refund.name} (01 2023)",
        )
        self.assertAccountMoveLines(
            deferred_feb_move,
            [
                (
                    lambda ml: ml.credit > 0,
                    {
                        "account_id": self.account_expense,
                        "debit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                    },
                ),
                (
                    lambda ml: ml.debit > 0,
                    {
                        "account_id": self.account_cutoff,
                        "credit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case A" in ml.name,
                    {
                        "credit": 1710.34,
                        "analytic_account_id": self.analytic,
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case B" in ml.name,
                    {
                        "credit": 40.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case C" in ml.name,
                    {
                        "credit": 30.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case D" in ml.name,
                    {
                        "credit": 130.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case F" in ml.name,
                    {
                        "credit": 259.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case I" in ml.name,
                    {
                        "credit": 1016.39,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 2, 1),
                        "end_date": date(2023, 2, 28),
                    },
                ),
            ],
        )
        self.assertAlmostEqual(
            sum(
                deferred_feb_move.line_ids.filtered(lambda ml: ml.debit > 0).mapped(
                    "debit"
                )
            ),
            3185.73,
            2,
        )

        deferred_mar_move = self.refund.cutoff_entry_ids.filtered(
            lambda move, move_date=date(2023, 3, 1): move.date == move_date
        )
        self.assertEqual(deferred_mar_move.journal_id, self.miscellaneous_journal)
        self.assertEqual(
            deferred_mar_move.ref,
            f"Advance expense adjustment of {self.refund.name} (01 2023)",
        )
        self.assertAccountMoveLines(
            deferred_mar_move,
            [
                (
                    lambda ml: ml.credit > 0,
                    {
                        "account_id": self.account_expense,
                        "debit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                    },
                ),
                (
                    lambda ml: ml.debit > 0,
                    {
                        "account_id": self.account_cutoff,
                        "credit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case A" in ml.name,
                    {
                        "credit": 1710.34,
                        "analytic_account_id": self.analytic,
                        "start_date": date(2023, 3, 1),
                        "end_date": date(2023, 3, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case B" in ml.name,
                    {
                        "credit": 40.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 3, 1),
                        "end_date": date(2023, 3, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case C" in ml.name,
                    {
                        "credit": 30.0,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 3, 1),
                        "end_date": date(2023, 3, 31),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case I" in ml.name,
                    {
                        "credit": 491.80,
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                        "start_date": date(2023, 3, 1),
                        "end_date": date(2023, 3, 15),
                    },
                ),
            ],
        )
        self.assertAlmostEqual(
            sum(
                deferred_mar_move.line_ids.filtered(lambda ml: ml.debit > 0).mapped(
                    "debit"
                )
            ),
            2272.14,
            2,
        )

        deferred_may_move = self.refund.cutoff_entry_ids.filtered(
            lambda move, move_date=date(2023, 5, 1): move.date == move_date
        )
        self.assertEqual(deferred_may_move.journal_id, self.miscellaneous_journal)
        self.assertEqual(
            deferred_may_move.ref,
            f"Advance expense adjustment of {self.refund.name} (01 2023)",
        )
        self.assertAccountMoveLines(
            deferred_may_move,
            [
                (
                    lambda ml: ml.credit > 0,
                    {
                        "account_id": self.account_expense,
                        "debit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                    },
                ),
                (
                    lambda ml: ml.debit > 0,
                    {
                        "account_id": self.account_cutoff,
                        "credit": 0.0,
                        "partner_id": self.env.ref("base.res_partner_2"),
                        "analytic_account_id": self.env[
                            "account.analytic.account"
                        ].browse(),
                    },
                ),
                (
                    lambda ml, account=self.account_expense: ml.account_id == account
                    and "Case G" in ml.name,
                    {
                        "credit": 255.00,
                        "start_date": date(2023, 5, 1),
                        "end_date": date(2023, 5, 31),
                    },
                ),
            ],
        )
        self.assertAlmostEqual(
            sum(
                deferred_may_move.line_ids.filtered(lambda ml: ml.debit > 0).mapped(
                    "debit"
                )
            ),
            255.0,
            2,
        )
