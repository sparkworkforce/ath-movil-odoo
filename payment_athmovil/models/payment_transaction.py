# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

import logging
import json

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from .payment_provider import ATH_MAX_TRANSACTION_AMOUNT

_logger = logging.getLogger(__name__)

# Tolerance for floating-point amount comparison between the webhook payload
# and the stored transaction amount. ATH Móvil may round amounts differently.
ATH_AMOUNT_TOLERANCE = 0.01


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    # Stores the ecommerceId returned by ATH Móvil after POST /payment.
    # This field is the cornerstone of idempotency:
    #   - Set once when the payment ticket is created
    #   - Used by the webhook controller to detect duplicate deliveries
    #   - Used by _process_notification_data for cross-integrity verification
    #
    # SQL UNIQUE constraint (see _sql_constraints below) allows multiple NULLs —
    # this is correct PostgreSQL behavior and intentional: the field is NULL
    # until the ticket is created, and multiple transactions can be in that state.
    athmovil_ecommerce_id = fields.Char(
        string="ATH Móvil eCommerce ID",
        copy=False,
        index=True,
        readonly=True,
    )

    # Refund tracking fields (Feature 4)
    athmovil_refund_status = fields.Selection(
        [
            ("none", "No Refund"),
            ("partial", "Partially Refunded"),
            ("full", "Fully Refunded"),
            ("failed", "Refund Failed"),
        ],
        string="ATH Refund Status",
        default="none",
        copy=False,
        tracking=True,
    )
    athmovil_refunded_amount = fields.Monetary(
        string="ATH Refunded Amount",
        currency_field="currency_id",
        default=0.0,
        copy=False,
        readonly=True,
    )
    athmovil_refund_reference = fields.Char(
        string="ATH Refund Reference",
        copy=False,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            "athmovil_ecommerce_id_uniq",
            # UNIQUE in PostgreSQL allows multiple NULLs — this is intentional.
            # Only non-NULL values must be unique, which is exactly what we need:
            # each completed ticket has a unique ecommerceId, but many transactions
            # can have NULL (not yet ticketed).
            "UNIQUE(athmovil_ecommerce_id)",
            "ATH Móvil eCommerce ID must be unique.",
        ),
    ]

    # -------------------------------------------------------------------------
    # Override: payment.transaction base methods
    # -------------------------------------------------------------------------

    def _get_specific_rendering_values(self, processing_values):
        """Return ATH Móvil-specific values needed to initialize ATHM_Checkout.

        This method is called by Odoo's payment framework when rendering the
        payment form. It creates the ATH Móvil payment ticket (POST /payment)
        if one does not exist yet, then returns all values needed by the
        QWeb template and the athmovil_checkout.js frontend module.

        VERSION_COMPATIBILITY:
        - Odoo 17/18: This method returns a dict and calls super() which also
          returns a dict. The pattern below is stable.
        - Odoo 19: If the method signature changes, verify against
          addons/payment_demo/models/payment_transaction.py in the Odoo 19
          source tree. Use hasattr() guards rather than version checks.
        """
        # hasattr() guard for forward compatibility with Odoo 19+
        if hasattr(super(), "_get_specific_rendering_values"):
            res = super()._get_specific_rendering_values(processing_values)
        else:
            res = {}

        if self.provider_code != "athmovil":
            return res

        # Validate transaction amount before creating the ATH Móvil ticket.
        # This check must happen here (before any API call) to fail fast.
        if self.amount > ATH_MAX_TRANSACTION_AMOUNT:
            raise ValidationError(
                _(
                    "ATH Móvil payments are limited to $1,500.00 per transaction. "
                    "Please contact the merchant to split this payment or use an "
                    "alternative payment method."
                )
            )

        # Create the payment ticket if it hasn't been created yet.
        # athmovil_ecommerce_id is set as a side effect of this call.
        if not self.athmovil_ecommerce_id:
            self._athmovil_create_payment_ticket()

        res.update(
            {
                "public_token": self.provider_id.athmovil_public_token,
                "amount": self.amount,
                # subtotal and tax: use amount as subtotal with 0 tax unless
                # a more detailed breakdown is available from the sale order.
                "subtotal": self.amount,
                "tax": 0.0,
                # metadata1 is used by the webhook to look up this transaction.
                # It must match the reference stored in this record.
                "metadata1": self.reference,
                "metadata2": self.company_id.name,
                "items": json.dumps(self._athmovil_build_items_list()),
                "ecommerce_id": self.athmovil_ecommerce_id,
            }
        )
        return res

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the ATH Móvil transaction from notification data.

        Called by Odoo's _handle_notification_data to find the transaction
        before calling _process_notification_data on it.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "athmovil" or len(tx) == 1:
            return tx

        reference = notification_data.get("metadata1")
        tx = self.search(
            [("reference", "=", reference), ("provider_code", "=", "athmovil")],
            limit=1,
        )
        if not tx:
            raise ValidationError(
                _("ATH Móvil: No transaction found for reference %s.") % reference
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Process the ATH Móvil webhook payload and update transaction state.

        This method is called by the webhook controller (UNIT-2) AFTER the
        controller has already performed the IDEMPOTENCY CHECK (verifying that
        the ecommerceId has not already been processed to a final state).

        This method performs the CROSS-INTEGRITY CHECK: verifying that the
        ecommerceId in the webhook payload matches the ecommerceId stored on
        THIS transaction (which was found via metadata1). This prevents a
        spoofing attack where an attacker sends a valid ecommerceId paired
        with a different metadata1 to hijack another merchant's transaction.

        
        :param notification_data: dict — webhook payload from ATH Móvil
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != "athmovil":
            return

        # --- Step 1: Validate required fields are present in the payload ---
        required_fields = {"ecommerceId", "status", "total", "metadata1"}
        missing = required_fields - set(notification_data.keys())
        if missing:
            _logger.warning(
                "ATH Móvil webhook: missing required fields %s for tx %s",
                missing,
                self.reference,
            )
            raise ValidationError(
                _("ATH Móvil webhook payload is missing required fields: %s") % missing
            )

        # --- Step 2: CROSS-INTEGRITY CHECK ---
        # Verify that the ecommerceId in the webhook matches the one stored on
        # this transaction. The controller found this transaction via metadata1;
        # if an attacker crafted a webhook with a valid ecommerceId but wrong
        # metadata1, they could reach a different transaction. This check stops that.
        if notification_data["ecommerceId"] != self.athmovil_ecommerce_id:
            _logger.warning(
                "ATH Móvil webhook: ecommerceId mismatch for tx %s. "
                "Webhook: %s, Stored: %s — possible spoofing attempt.",
                self.reference,
                notification_data["ecommerceId"],
                self.athmovil_ecommerce_id,
            )
            raise ValidationError(
                _("ATH Móvil webhook ecommerceId does not match the transaction record.")
            )

        # --- Step 3: Amount verification (tolerance ±$0.01 for float rounding) ---
        try:
            webhook_total = float(notification_data.get("total", 0))
        except (ValueError, TypeError):
            raise ValidationError(
                _("ATH Móvil webhook: invalid 'total' value.")
            )
        if abs(webhook_total - self.amount) > ATH_AMOUNT_TOLERANCE:
            _logger.warning(
                "ATH Móvil webhook: amount mismatch for tx %s. "
                "Webhook total: %.2f, Transaction amount: %.2f",
                self.reference,
                webhook_total,
                self.amount,
            )
            raise ValidationError(
                _(
                    "ATH Móvil webhook amount (%.2f) does not match "
                    "transaction amount (%.2f)."
                )
                % (webhook_total, self.amount)
            )

        # --- Step 4: Update transaction state based on ATH Móvil status ---
        ath_status = notification_data.get("status", "")
        reference_number = notification_data.get("referenceNumber", "")

        if ath_status == "COMPLETED":
            self._set_done()
            # Send email receipt to customer
            try:
                template = self.env.ref(
                    "payment_athmovil.mail_template_athmovil_receipt",
                    raise_if_not_found=False,
                )
                if template and self.partner_email:
                    template.send_mail(self.id, force_send=False)
            except Exception:
                _logger.warning(
                    "ATH Móvil: could not send receipt email for tx %s",
                    self.reference,
                )
            self.message_post(
                body=_(
                    "ATH Móvil payment COMPLETED. "
                    "ATH reference: %s, eCommerceId: %s"
                )
                % (reference_number, self.athmovil_ecommerce_id)
            )
            _logger.info(
                "ATH Móvil: transaction %s marked as done. "
                "ATH reference: %s",
                self.reference,
                reference_number,
            )

        elif ath_status in ("CANCELLED", "EXPIRED"):
            self._set_canceled(
                state_message=_(
                    "ATH Móvil payment %s. eCommerceId: %s"
                )
                % (ath_status, self.athmovil_ecommerce_id)
            )
            _logger.info(
                "ATH Móvil: transaction %s cancelled/expired. Status: %s",
                self.reference,
                ath_status,
            )

        else:
            # Unknown status — log and ignore. Do not change transaction state.
            _logger.warning(
                "ATH Móvil webhook: unknown status '%s' for tx %s — ignoring.",
                ath_status,
                self.reference,
            )

    def _send_refund_request(self, amount_to_refund=None, **kwargs):
        """Send a refund request to ATH Móvil via POST /refund.

        Supports both full and partial refunds. Tracks cumulative refunded
        amount and updates refund status (partial/full/failed).

        NO automatic retries — retrying a refund can create duplicate refunds
        if the first request succeeded but the response was lost.

        :param amount_to_refund: float | None — amount to refund. Defaults to
                                 full transaction amount if None.
        :raises UserError: if the ATH Móvil API returns a refund error
        """
        self.ensure_one()

        if self.provider_code != "athmovil":
            return super()._send_refund_request(amount_to_refund=amount_to_refund, **kwargs)

        # Create child refund transaction via Odoo's standard pipeline
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund, **kwargs)

        if not self.athmovil_ecommerce_id:
            raise UserError(
                _("Cannot refund: ATH Móvil eCommerce ID is not set on this transaction.")
            )

        refund_amount = amount_to_refund if amount_to_refund is not None else self.amount
        payload = {
            "ecommerceId": self.athmovil_ecommerce_id,
            "amount": round(refund_amount, 2),
        }

        try:
            result = self.provider_id._athmovil_make_request("refund", payload, "POST")
        except ValidationError as exc:
            self.athmovil_refund_status = "failed"
            self.message_post(
                body=_("ATH Móvil refund FAILED: %s") % str(exc)
            )
            raise UserError(str(exc)) from exc  # refund_tx still returned by caller

        # Track refund
        self.athmovil_refunded_amount += refund_amount
        refund_ref = ""
        if isinstance(result, dict):
            data = result.get("data", result)
            refund_info = data.get("refund", data)
            refund_ref = refund_info.get("referenceNumber", "")
        if refund_ref:
            self.athmovil_refund_reference = refund_ref

        if self.athmovil_refunded_amount >= self.amount:
            self.athmovil_refund_status = "full"
        else:
            self.athmovil_refund_status = "partial"

        self.message_post(
            body=_(
                "ATH Móvil refund processed: $%(amount).2f. "
                "Total refunded: $%(total).2f / $%(original).2f. "
                "Reference: %(ref)s"
            ) % {
                "amount": refund_amount,
                "total": self.athmovil_refunded_amount,
                "original": self.amount,
                "ref": refund_ref or "N/A",
            }
        )
        _logger.info(
            "ATH Móvil: refund $%.2f for tx %s (eCommerceId: %s, ref: %s)",
            refund_amount,
            self.reference,
            self.athmovil_ecommerce_id,
            refund_ref,
        )
        return refund_tx

    # -------------------------------------------------------------------------
    # ATH Móvil-specific methods
    # -------------------------------------------------------------------------

    def _athmovil_create_payment_ticket(self):
        """Call POST /payment to create an ATH Móvil payment ticket.

        Stores the returned ecommerceId in athmovil_ecommerce_id.
        This field has a SQL UNIQUE constraint — if a duplicate ecommerceId
        is returned (should never happen), the write will fail at the DB level.

        Race condition protection: uses a row-level DB lock (SELECT FOR UPDATE NOWAIT)
        to prevent duplicate ticket creation from concurrent requests
        (e.g., double-click by the customer).

        NO automatic retries — see _athmovil_make_request docstring.

        :raises ValidationError: if the API call fails or returns no ecommerceId
        """
        self.ensure_one()

        # Re-read the record with a row-level lock to prevent race conditions
        # from concurrent requests (e.g., double-click). If another request
        # already created the ticket, return early.
        # NOWAIT raises LockNotAvailable if another transaction holds the lock —
        # we catch it and fall through to let the caller retry or handle gracefully.
        try:
            self.env.cr.execute(
                "SELECT athmovil_ecommerce_id FROM payment_transaction "
                "WHERE id = %s FOR UPDATE NOWAIT",
                (self.id,),
            )
        except Exception as lock_exc:
            # Narrow check: only treat lock-related errors as "being processed".
            # psycopg2 LockNotAvailable has pgcode='55P03'.
            pgcode = getattr(lock_exc, "pgcode", "")
            if pgcode == "55P03":
                raise ValidationError(
                    _("ATH Móvil payment is being processed. Please wait a moment and try again.")
                )
            raise  # Re-raise unexpected DB errors
        row = self.env.cr.fetchone()
        if row and row[0]:
            # Another concurrent request already created the ticket — use it
            self.invalidate_recordset(["athmovil_ecommerce_id"])
            return

        payload = {
            "publicToken": self.provider_id.athmovil_public_token,
            "total": self.amount,
            "subtotal": self.amount,
            "tax": 0.0,
            "metadata1": self.reference,
            "metadata2": self.company_id.name,
            "items": self._athmovil_build_items_list(),
        }

        result = self.provider_id._athmovil_make_request("payment", payload, "POST")

        ecommerce_id = result.get("ecommerceId")
        if not ecommerce_id:
            _logger.error(
                "ATH Móvil: POST /payment returned no ecommerceId for tx %s. "
                "Response: %s",
                self.reference,
                result,
            )
            raise ValidationError(
                _("ATH Móvil did not return a payment ID. Please try again.")
            )

        # Write the ecommerceId — the SQL UNIQUE constraint will catch duplicates
        self.athmovil_ecommerce_id = ecommerce_id

        self.message_post(
            body=_("ATH Móvil payment ticket created. eCommerceId: %s") % ecommerce_id
        )
        _logger.info(
            "ATH Móvil: payment ticket created for tx %s. eCommerceId: %s",
            self.reference,
            ecommerce_id,
        )

    def _athmovil_build_items_list(self):
        """Build the items list for the ATH Móvil payment payload.

        If a sale.order is linked to this transaction, build the items list
        from sale.order.line records. Otherwise return an empty list.
        ATH Móvil accepts an empty items list — it is not required.

        PBT invariant: when a sale.order exists,
            sum(item['price'] * item['quantity'] for item in items) == self.amount
        (within floating-point tolerance)

        :return: list[dict] — each dict has keys: name, description, quantity,
                 price, tax, metadata, sku
        """
        self.ensure_one()
        items = []

        # sale_order_ids is available when the transaction is linked to a sale order
        sale_orders = getattr(self, "sale_order_ids", None)
        if not sale_orders:
            return items

        for order in sale_orders:
            for line in order.order_line:
                # Skip cancelled lines and delivery/service lines with 0 qty
                if line.product_uom_qty <= 0:
                    continue
                items.append(
                    {
                        "name": line.product_id.name or line.name or "",
                        "description": line.name or "",
                        "quantity": int(line.product_uom_qty),
                        "price": round(line.price_unit, 2),
                        "tax": round(line.price_tax / line.product_uom_qty, 2)
                        if line.product_uom_qty
                        else 0.0,
                        "metadata": line.product_id.default_code or "",
                        "sku": line.product_id.default_code or "",
                    }
                )

        return items

    # -------------------------------------------------------------------------
    # QR Code Payment (Feature 4)
    # -------------------------------------------------------------------------

    def _athmovil_get_qr_url(self):
        """Return a URL that generates a QR code image for this transaction.

        The QR encodes the ATH Móvil payment link that the customer scans
        with their ATH Móvil app.
        """
        self.ensure_one()
        if not self.athmovil_ecommerce_id:
            return False
        base_url = self.provider_id.get_base_url()
        return "%s/payment/athmovil/qr/%s" % (base_url, self.athmovil_ecommerce_id)
