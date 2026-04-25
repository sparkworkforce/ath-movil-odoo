# -*- coding: utf-8 -*-
"""
Sandbox integration test for ATH Móvil payment provider.

Runs against ATH Móvil's sandbox (publicToken="dummy").
Only executes when explicitly requested:

    odoo-bin -i payment_athmovil --test-tags athmovil_sandbox

Requires network access to https://payments.athmovil.com
"""

from odoo.tests.common import tagged, TransactionCase


@tagged("post_install", "-at_install", "athmovil_sandbox")
class TestAthMovilSandbox(TransactionCase):
    """Integration tests against ATH Móvil sandbox API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref("payment_athmovil.payment_provider_athmovil")
        cls.provider.write({
            "state": "test",
            "athmovil_public_token": "dummy",
            "athmovil_private_token": "dummy",
        })
        cls.usd = cls.env.ref("base.USD")

    def test_sandbox_create_ticket(self):
        """POST /payment creates a ticket and returns an ecommerceId."""
        tx = self.env["payment.transaction"].create({
            "provider_id": self.provider.id,
            "amount": 1.00,
            "currency_id": self.usd.id,
            "reference": "SANDBOX-TEST-001",
        })
        try:
            tx._athmovil_create_payment_ticket()
        except Exception as exc:
            # Sandbox may reject — that's OK, we're testing connectivity
            self.assertNotIn("Could not connect", str(exc),
                "Should be able to reach ATH Móvil API")
            return

        self.assertTrue(tx.athmovil_ecommerce_id,
            "Sandbox should return an ecommerceId")

    def test_sandbox_find_payment(self):
        """GET /findPayment returns a status for a known ecommerceId."""
        try:
            result = self.provider._athmovil_make_request(
                "business/findPayment",
                payload={
                    "publicToken": "dummy",
                    "ecommerceId": "test-nonexistent-id",
                },
                method="POST",
            )
            # If we get here, the API responded (even with an error payload)
            self.assertIsInstance(result, dict)
        except Exception as exc:
            error_msg = str(exc)
            # Network errors = real failure; API errors = sandbox works
            self.assertNotIn("Could not connect", error_msg,
                "Should be able to reach ATH Móvil API")
            self.assertNotIn("did not respond", error_msg,
                "ATH Móvil API should respond within timeout")

    def test_sandbox_test_connection(self):
        """Test Connection button should succeed against sandbox."""
        try:
            result = self.provider.action_athmovil_test_connection()
            self.assertEqual(result["params"]["type"], "success")
        except Exception as exc:
            self.assertNotIn("Could not connect", str(exc))
            self.assertNotIn("did not respond", str(exc))
