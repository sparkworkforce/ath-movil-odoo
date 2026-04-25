# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
"""
Unit tests for payment.transaction ATH Móvil extension.

Run with:
    odoo-bin -i payment_athmovil --test-enable --stop-after-init
"""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAthMovilTransaction(TransactionCase):
    """Tests for PaymentTransaction ATH Móvil extension."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref("payment_athmovil.payment_provider_athmovil")
        cls.usd = cls.env.ref("base.USD")

    def _make_tx(self, reference="TEST-TX-001", amount=25.00, ecommerce_id=None):
        """Helper to create a test transaction."""
        tx = self.env["payment.transaction"].create({
            "provider_id": self.provider.id,
            "amount": amount,
            "currency_id": self.usd.id,
            "reference": reference,
        })
        if ecommerce_id:
            tx.athmovil_ecommerce_id = ecommerce_id
        return tx

    # -------------------------------------------------------------------------
    # SQL UNIQUE constraint on athmovil_ecommerce_id (RF-14, BR-03)
    # -------------------------------------------------------------------------

    def test_ecommerce_id_unique_constraint(self):
        """Two transactions cannot share the same non-NULL athmovil_ecommerce_id."""
        self._make_tx("TEST-UNIQ-001", ecommerce_id="unique-id-123")
        with self.assertRaises(Exception):  # IntegrityError from PostgreSQL
            self._make_tx("TEST-UNIQ-002", ecommerce_id="unique-id-123")

    def test_ecommerce_id_null_allows_multiple(self):
        """Multiple transactions can have NULL athmovil_ecommerce_id (PostgreSQL UNIQUE allows NULLs)."""
        tx1 = self._make_tx("TEST-NULL-001")
        tx2 = self._make_tx("TEST-NULL-002")
        # Both should have NULL ecommerce_id without constraint violation
        self.assertFalse(tx1.athmovil_ecommerce_id)
        self.assertFalse(tx2.athmovil_ecommerce_id)

    # -------------------------------------------------------------------------
    # _handle_notification_data — CROSS-INTEGRITY CHECK (BR-03)
    # -------------------------------------------------------------------------

    def test_handle_feedback_cross_integrity_mismatch(self):
        """ValidationError when webhook ecommerceId doesn't match stored value."""
        tx = self._make_tx("TEST-INTEGRITY-001", ecommerce_id="real-id-abc")
        data = {
            "ecommerceId": "spoofed-id-xyz",  # Different from stored
            "status": "COMPLETED",
            "total": 25.00,
            "metadata1": "TEST-INTEGRITY-001",
        }
        with self.assertRaises(ValidationError):
            tx._handle_notification_data("athmovil", data)

    def test_handle_feedback_cross_integrity_match(self):
        """No error when ecommerceId matches stored value."""
        tx = self._make_tx("TEST-INTEGRITY-002", ecommerce_id="correct-id-abc")
        data = {
            "ecommerceId": "correct-id-abc",
            "status": "COMPLETED",
            "total": 25.00,
            "metadata1": "TEST-INTEGRITY-002",
        }
        # Should not raise ValidationError on integrity check
        # (may raise on _set_done if state transition not allowed in test)
        try:
            tx._handle_notification_data("athmovil", data)
        except ValidationError:
            self.fail("Cross-integrity check raised ValidationError unexpectedly")

    # -------------------------------------------------------------------------
    # _handle_notification_data — Amount verification (BR-04)
    # -------------------------------------------------------------------------

    def test_handle_feedback_amount_within_tolerance(self):
        """No error when webhook amount is within ±$0.01 of transaction amount."""
        tx = self._make_tx("TEST-AMT-001", amount=25.00, ecommerce_id="amt-id-001")
        data = {
            "ecommerceId": "amt-id-001",
            "status": "COMPLETED",
            "total": 25.005,  # Within $0.01 tolerance
            "metadata1": "TEST-AMT-001",
        }
        try:
            tx._handle_notification_data("athmovil", data)
        except ValidationError as e:
            if "amount" in str(e).lower():
                self.fail("Amount within tolerance raised ValidationError")

    def test_handle_feedback_amount_exceeds_tolerance(self):
        """ValidationError when webhook amount differs by more than $0.01."""
        tx = self._make_tx("TEST-AMT-002", amount=25.00, ecommerce_id="amt-id-002")
        data = {
            "ecommerceId": "amt-id-002",
            "status": "COMPLETED",
            "total": 26.00,  # $1.00 difference — exceeds tolerance
            "metadata1": "TEST-AMT-002",
        }
        with self.assertRaises(ValidationError):
            tx._handle_notification_data("athmovil", data)

    # -------------------------------------------------------------------------
    # _handle_notification_data — Missing fields (BR-09)
    # -------------------------------------------------------------------------

    def test_handle_feedback_missing_required_fields(self):
        """ValidationError when webhook payload is missing required fields."""
        tx = self._make_tx("TEST-FIELDS-001", ecommerce_id="fields-id-001")
        data = {"ecommerceId": "fields-id-001"}  # Missing status, total, metadata1
        with self.assertRaises(ValidationError):
            tx._handle_notification_data("athmovil", data)

    # -------------------------------------------------------------------------
    # _athmovil_build_items_list
    # -------------------------------------------------------------------------

    def test_build_items_empty_without_sale_order(self):
        """Returns empty list when no sale.order is linked."""
        tx = self._make_tx("TEST-ITEMS-001")
        items = tx._athmovil_build_items_list()
        self.assertEqual(items, [])
        self.assertIsInstance(items, list)

    # -------------------------------------------------------------------------
    # Refund tracking (Feature 4)
    # -------------------------------------------------------------------------

    def test_refund_status_default_is_none(self):
        """New transactions should have refund_status = 'none'."""
        tx = self._make_tx("TEST-REFUND-DEFAULT")
        self.assertEqual(tx.athmovil_refund_status, "none")
        self.assertEqual(tx.athmovil_refunded_amount, 0.0)

    def test_refund_full_sets_status(self):
        """Full refund should set status to 'full'."""
        tx = self._make_tx("TEST-REFUND-FULL", amount=50.00, ecommerce_id="refund-full-001")
        tx._set_done()

        with patch.object(
            self.provider.__class__,
            "_athmovil_make_request",
            return_value={"data": {"refund": {"referenceNumber": "REF-001"}}},
        ):
            tx._send_refund_request(amount_to_refund=50.00)

        self.assertEqual(tx.athmovil_refund_status, "full")
        self.assertEqual(tx.athmovil_refunded_amount, 50.00)
        self.assertEqual(tx.athmovil_refund_reference, "REF-001")

    def test_refund_partial_sets_status(self):
        """Partial refund should set status to 'partial'."""
        tx = self._make_tx("TEST-REFUND-PARTIAL", amount=100.00, ecommerce_id="refund-partial-001")
        tx._set_done()

        with patch.object(
            self.provider.__class__,
            "_athmovil_make_request",
            return_value={"data": {"refund": {"referenceNumber": "REF-002"}}},
        ):
            tx._send_refund_request(amount_to_refund=30.00)

        self.assertEqual(tx.athmovil_refund_status, "partial")
        self.assertEqual(tx.athmovil_refunded_amount, 30.00)

    def test_refund_failed_sets_status(self):
        """Failed refund should set status to 'failed'."""
        from odoo.exceptions import UserError

        tx = self._make_tx("TEST-REFUND-FAIL", amount=25.00, ecommerce_id="refund-fail-001")
        tx._set_done()

        with patch.object(
            self.provider.__class__,
            "_athmovil_make_request",
            side_effect=ValidationError("Refund failed"),
        ):
            with self.assertRaises(UserError):
                tx._send_refund_request(amount_to_refund=25.00)

        self.assertEqual(tx.athmovil_refund_status, "failed")

    def test_refund_no_ecommerce_id_raises(self):
        """Refund without ecommerce_id should raise UserError."""
        from odoo.exceptions import UserError

        tx = self._make_tx("TEST-REFUND-NO-ID")
        tx._set_done()

        with self.assertRaises(UserError):
            tx._send_refund_request()
