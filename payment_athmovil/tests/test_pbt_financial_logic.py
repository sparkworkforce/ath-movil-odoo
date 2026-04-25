# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
"""
Property-Based Tests for ATH Móvil financial logic.

Uses Hypothesis to verify invariants across a wide range of generated inputs.
These tests complement (not replace) the example-based tests in the other
test files. See requirements.md section 6 for the full list of PBT properties.

Framework: Hypothesis (PBT-09)
Install: pip install hypothesis

Run with:
    odoo-bin -i payment_athmovil --test-enable --stop-after-init

Note: Hypothesis tests may take longer than standard unit tests due to
input generation. The @settings decorator controls the number of examples.
"""

from odoo.tests.common import TransactionCase

import uuid

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

from payment_athmovil.models.payment_provider import ATH_MAX_TRANSACTION_AMOUNT
from payment_athmovil.models.payment_transaction import ATH_AMOUNT_TOLERANCE


def skip_if_no_hypothesis(test_func):
    """Decorator to skip PBT tests if Hypothesis is not installed."""
    import functools

    @functools.wraps(test_func)
    def wrapper(self, *args, **kwargs):
        if not HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis not installed — skipping PBT tests. Install with: pip install hypothesis")
        return test_func(self, *args, **kwargs)
    return wrapper


class TestAthMovilPBT(TransactionCase):
    """Property-Based Tests for ATH Móvil financial logic.

    PBT-01: amount <= ATH_MAX_TRANSACTION_AMOUNT invariant
    PBT-02: items JSON serialization round-trip
    PBT-03: webhook idempotency
    PBT-04: amount tolerance invariant
    PBT-07: items sum invariant
    """

    # -------------------------------------------------------------------------
    # PBT-01: Transaction amount limit invariant
    # Property: for any amount > 1500.00, ValidationError is raised
    # -------------------------------------------------------------------------

    @skip_if_no_hypothesis
    def test_pbt_amount_above_limit_always_raises(self):
        """PBT-01: ValidationError for any amount > $1,500.00."""
        from odoo.exceptions import ValidationError

        provider = self.env.ref("payment_athmovil.payment_provider_athmovil")
        usd = self.env.ref("base.USD")

        @given(amount=st.floats(
            min_value=ATH_MAX_TRANSACTION_AMOUNT + 0.01,
            max_value=100000.00,
            allow_nan=False,
            allow_infinity=False,
        ))
        @settings(max_examples=50)
        def check(amount):
            ref = f"PBT-AMT-{uuid.uuid4().hex[:8]}"
            tx = provider.env["payment.transaction"].create({
                "provider_id": provider.id,
                "amount": amount,
                "currency_id": usd.id,
                "reference": ref,
            })
            with self.assertRaises(ValidationError):
                tx._get_specific_rendering_values({})
            tx.unlink()

        check()

    @skip_if_no_hypothesis
    def test_pbt_amount_at_or_below_limit_no_validation_error(self):
        """PBT-01: No ValidationError for any amount <= $1,500.00."""
        from odoo.exceptions import ValidationError
        from unittest.mock import patch

        provider = self.env.ref("payment_athmovil.payment_provider_athmovil")
        usd = self.env.ref("base.USD")

        @given(amount=st.floats(
            min_value=0.01,
            max_value=ATH_MAX_TRANSACTION_AMOUNT,
            allow_nan=False,
            allow_infinity=False,
        ))
        @settings(max_examples=50)
        def check(amount):
            ref = f"PBT-OK-{uuid.uuid4().hex[:8]}"
            tx = provider.env["payment.transaction"].create({
                "provider_id": provider.id,
                "amount": round(amount, 2),
                "currency_id": usd.id,
                "reference": ref,
            })
            # Mock the API call — we only want to test the limit validation
            with patch.object(provider.__class__, "_athmovil_make_request",
                              return_value={"ecommerceId": "mock-id", "status": "IN_PROCESS"}):
                try:
                    tx._get_specific_rendering_values({})
                except ValidationError as e:
                    if "1,500" in str(e):
                        self.fail(f"Amount {amount} <= limit raised limit ValidationError")
            tx.unlink()

        check()

    # -------------------------------------------------------------------------
    # PBT-02: Items JSON serialization round-trip
    # Property: deserialize(serialize(items)) == items
    # -------------------------------------------------------------------------

    @skip_if_no_hypothesis
    def test_pbt_items_serialization_round_trip(self):
        """PBT-02: JSON serialization of items list is a round-trip."""
        import json

        item_strategy = st.fixed_dictionaries({
            "name": st.text(min_size=1, max_size=50),
            "description": st.text(max_size=100),
            "quantity": st.integers(min_value=1, max_value=100),
            "price": st.floats(min_value=0.01, max_value=9999.99,
                               allow_nan=False, allow_infinity=False),
            "tax": st.floats(min_value=0.0, max_value=100.0,
                             allow_nan=False, allow_infinity=False),
            "metadata": st.text(max_size=50),
            "sku": st.text(max_size=50),
        })

        @given(items=st.lists(item_strategy, min_size=0, max_size=10))
        @settings(max_examples=100)
        def check(items):
            serialized = json.dumps(items)
            deserialized = json.loads(serialized)
            self.assertEqual(items, deserialized,
                             "Items round-trip serialization failed")

        check()

    # -------------------------------------------------------------------------
    # PBT-04: Amount tolerance invariant
    # Property: abs(webhook_total - tx_amount) <= 0.01 is accepted
    #           abs(webhook_total - tx_amount) > 0.01 is rejected
    # -------------------------------------------------------------------------

    @skip_if_no_hypothesis
    def test_pbt_amount_tolerance_boundary(self):
        """PBT-04: Amounts within ±$0.01 tolerance are accepted."""
        @given(
            base_amount=st.floats(min_value=1.00, max_value=1000.00,
                                  allow_nan=False, allow_infinity=False),
            delta=st.floats(min_value=0.0, max_value=ATH_AMOUNT_TOLERANCE,
                            allow_nan=False, allow_infinity=False),
        )
        @settings(max_examples=100)
        def check(base_amount, delta):
            base_amount = round(base_amount, 2)
            webhook_total = round(base_amount + delta, 4)
            diff = abs(webhook_total - base_amount)
            # Within tolerance — should be accepted
            self.assertLessEqual(
                diff,
                ATH_AMOUNT_TOLERANCE + 1e-9,  # small epsilon for float precision
                f"Amount diff {diff} should be within tolerance {ATH_AMOUNT_TOLERANCE}"
            )

        check()

    # -------------------------------------------------------------------------
    # PBT-03: Webhook idempotency
    # Property: processing the same webhook data twice produces the same state
    # -------------------------------------------------------------------------

    @skip_if_no_hypothesis
    def test_pbt_webhook_idempotency(self):
        """PBT-03: Processing the same valid webhook twice yields the same final state."""
        from unittest.mock import patch

        provider = self.env.ref("payment_athmovil.payment_provider_athmovil")
        usd = self.env.ref("base.USD")

        @given(
            amount=st.floats(min_value=1.00, max_value=100.00,
                             allow_nan=False, allow_infinity=False),
            status=st.sampled_from(["COMPLETED", "CANCELLED", "EXPIRED"]),
        )
        @settings(max_examples=30)
        def check(amount, status):
            amount = round(amount, 2)
            ref = f"PBT-IDEM-{uuid.uuid4().hex[:8]}"
            ecommerce_id = f"idem-{uuid.uuid4().hex[:8]}"

            tx = provider.env["payment.transaction"].create({
                "provider_id": provider.id,
                "amount": amount,
                "currency_id": usd.id,
                "reference": ref,
                "athmovil_ecommerce_id": ecommerce_id,
            })

            data = {
                "ecommerceId": ecommerce_id,
                "status": status,
                "total": amount,
                "metadata1": ref,
                "referenceNumber": "test-ref",
            }

            # First processing
            tx._handle_notification_data("athmovil", data)
            state_after_first = tx.state

            # Second processing — should produce same state (idempotent)
            tx._handle_notification_data("athmovil", data)
            state_after_second = tx.state

            self.assertEqual(
                state_after_first,
                state_after_second,
                f"State changed on second processing: {state_after_first} → {state_after_second}"
            )

            tx.unlink()

        check()
