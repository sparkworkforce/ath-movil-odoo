# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
"""
Integration tests for the ATH Móvil webhook controller.

Tests the IDEMPOTENCY CHECK (controller layer) and basic routing behavior.
The CROSS-INTEGRITY CHECK is tested in test_payment_transaction.py.

Run with:
    odoo-bin -i payment_athmovil --test-enable --stop-after-init
"""

import json

from odoo.tests.common import HttpCase


class TestAthMovilWebhookController(HttpCase):
    """Tests for AthMovilController webhook route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref("payment_athmovil.payment_provider_athmovil")
        cls.usd = cls.env.ref("base.USD")

    def _post_webhook(self, data):
        """Helper to POST to the webhook endpoint."""
        return self.url_open(
            "/payment/athmovil/webhook",
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )

    # -------------------------------------------------------------------------
    # Missing fields → 400
    # -------------------------------------------------------------------------

    def test_webhook_missing_fields_returns_400(self):
        """Webhook with missing required fields must return HTTP 400."""
        response = self._post_webhook({"ecommerceId": "test-id"})
        self.assertEqual(response.status_code, 400)

    def test_webhook_empty_body_returns_400(self):
        """Empty webhook body must return HTTP 400."""
        response = self.url_open(
            "/payment/athmovil/webhook",
            data=b"",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # Unknown transaction → 400
    # -------------------------------------------------------------------------

    def test_webhook_unknown_transaction_returns_400(self):
        """Webhook for non-existent transaction must return HTTP 400."""
        data = {
            "ecommerceId": "nonexistent-id-xyz",
            "status": "COMPLETED",
            "total": 25.00,
            "metadata1": "NONEXISTENT-REF-999",
        }
        response = self._post_webhook(data)
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # IDEMPOTENCY CHECK — already processed → 200 without reprocessing
    # -------------------------------------------------------------------------

    def test_webhook_idempotency_already_done(self):
        """Webhook for already-done transaction must return 200 without reprocessing."""
        # Create a transaction in 'done' state with a known ecommerceId
        tx = self.env["payment.transaction"].create({
            "provider_id": self.provider.id,
            "amount": 25.00,
            "currency_id": self.usd.id,
            "reference": "TEST-IDEM-DONE-001",
            "athmovil_ecommerce_id": "idem-done-id-001",
        })
        tx._set_done()

        data = {
            "ecommerceId": "idem-done-id-001",
            "status": "COMPLETED",
            "total": 25.00,
            "metadata1": "TEST-IDEM-DONE-001",
        }
        response = self._post_webhook(data)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "already_processed")
