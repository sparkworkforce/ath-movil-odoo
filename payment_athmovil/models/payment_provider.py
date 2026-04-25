# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

import logging
import requests

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Maximum transaction amount allowed by ATH Móvil Business per transaction (USD).
# Source: ATH Móvil Business documentation — daily limit per business account.
# Update this constant if ATH Móvil changes their limits.
# FUTURE: Consider making this a configurable field on payment.provider so
# merchants can adjust it without a module release if ATH Móvil changes limits.
ATH_MAX_TRANSACTION_AMOUNT = 1500.00

# Base URL for the ATH Móvil Business eCommerce API.
# All endpoints are relative to this base URL.
ATH_API_BASE_URL = "https://payments.athmovil.com/api/business-transaction/ecommerce"

# VERSION_COMPATIBILITY:
# If upgrading to Odoo 19, verify the payment.provider model API against:
#   addons/payment_demo/models/payment_provider.py
# in the Odoo 19 source tree before making changes to this file.
# Use hasattr() guards rather than hardcoded version checks.


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    # The provider code used throughout Odoo's payment framework to identify
    # this provider. Must match the value in payment_provider_data.xml.
    code = fields.Selection(
        selection_add=[("athmovil", "ATH Móvil")],
        ondelete={"athmovil": "set default"},
    )

    # Public token identifies the merchant's ATH Business account.
    # Required when this provider is active — enforced via @api.constrains below
    # and via required= attribute in the view XML.
    # We do NOT use required_if_provider= because it is not a standard ORM attribute.
    athmovil_public_token = fields.Char(
        string="ATH Móvil Public Token",
        required=False,
    )

    # Private token authenticates API requests on behalf of the merchant.
    # SECURITY: groups="base.group_system" restricts field access at the ORM level.
    # Without this, any user with JSON-RPC access could read the token via
    # fields_get() or read() calls — the view's password=True alone is insufficient.
    athmovil_private_token = fields.Char(
        string="ATH Móvil Private Token",
        groups="base.group_system",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains("athmovil_public_token", "code")
    def _check_athmovil_public_token(self):
        """Enforce that public token is set whenever ATH Móvil is the active provider.

        We use @api.constrains instead of required_if_provider= because the latter
        is not a standard Odoo ORM attribute and would be silently ignored.
        The view XML also sets required="code == 'athmovil'" for UI-side validation.
        """
        for provider in self:
            if provider.code == "athmovil" and not provider.athmovil_public_token:
                raise ValidationError(
                    _(
                        "ATH Móvil Public Token is required when using "
                        "ATH Móvil as payment provider."
                    )
                )

    # -------------------------------------------------------------------------
    # Override: payment.provider base methods
    # -------------------------------------------------------------------------

    def _get_supported_currencies(self):
        """ATH Móvil only supports USD transactions.

        Puerto Rico uses USD as its currency. ATH Móvil Business does not
        support other currencies at this time.
        """
        supported = super()._get_supported_currencies()
        if self.code == "athmovil":
            supported = supported.filtered(lambda c: c.name == "USD")
        return supported

    def _get_validation_amount(self):
        """Return 0 to disable tokenization flow.

        ATH Móvil does not support card tokenization — each payment requires
        active approval from the customer in the ATH Móvil app.
        Returning 0 skips the validation charge that Odoo uses for tokenization.
        """
        if self.code == "athmovil":
            return 0.0
        return super()._get_validation_amount()

    def _get_redirect_form_view(self, is_validation=False):
        """Return the QWeb template used to render the ATH Móvil payment form.

        Odoo's payment framework calls this method to get the template ID
        for rendering the payment redirect form.

        ATH Móvil does not support tokenization (_get_validation_amount returns 0),
        so is_validation should never be True for this provider.
        """
        if self.code == "athmovil":
            if is_validation:
                # ATH Móvil does not support tokenization — this should never happen
                _logger.debug(
                    "ATH Móvil: _get_redirect_form_view called with is_validation=True "
                    "but ATH Móvil does not support tokenization."
                )
            return self.env.ref("payment_athmovil.redirect_form")
        return super()._get_redirect_form_view(is_validation)

    # -------------------------------------------------------------------------
    # Test Connection (Feature 1 — Merchant onboarding)
    # -------------------------------------------------------------------------

    def action_athmovil_test_connection(self):
        """Test ATH Móvil API credentials by calling findPayment with a dummy ID.

        A successful HTTP connection (even with 'not found' error) proves
        credentials are valid and the network path works.
        """
        self.ensure_one()
        if not self.athmovil_public_token or not self.athmovil_private_token:
            raise ValidationError(
                _("Please enter both Public Token and Private Token before testing.")
            )
        try:
            self._athmovil_make_request(
                "business/findPayment",
                payload={
                    "publicToken": self.athmovil_public_token,
                    "ecommerceId": "test-connection-00000000",
                },
                method="POST",
            )
        except ValidationError as exc:
            error_msg = str(exc)
            if "did not respond" in error_msg or "Could not connect" in error_msg:
                raise
            # API error like "transaction not found" = credentials work

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection Successful"),
                "message": _(
                    "ATH Móvil API is reachable and your credentials are valid."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    # -------------------------------------------------------------------------
    # ATH Móvil API helpers
    # -------------------------------------------------------------------------

    def _athmovil_get_api_url(self, endpoint):
        """Build the full URL for an ATH Móvil API endpoint.

        :param endpoint: str — one of 'payment', 'refund', 'cancelPayment',
                         'findPayment'
        :return: str — full HTTPS URL
        """
        return f"{ATH_API_BASE_URL}/{endpoint}"

    def _athmovil_make_request(self, endpoint, payload=None, method="POST"):
        """Execute an authenticated HTTP request to the ATH Móvil Business API.

        RETRY POLICY (important — do not change without careful consideration):
        - POST /payment   → NO automatic retries. Retrying can create duplicate
                            tickets if the first request succeeded but the
                            response was lost in transit.
        - POST /refund    → NO automatic retries. Same duplicate risk.
        - POST /cancelPayment → NO automatic retries.
        - GET /findPayment → MAY be retried externally (idempotent by nature).

        On 5xx errors: log the error and raise ValidationError with a
        user-friendly message. Let Odoo handle the transaction state.

        :param endpoint: str — API endpoint name
        :param payload: dict | None — request body (None for GET requests)
        :param method: str — 'POST' or 'GET'
        :return: dict — parsed JSON response from ATH Móvil
        :raises ValidationError: on any API error or network failure
        """
        self.ensure_one()
        url = self._athmovil_get_api_url(endpoint)
        headers = {
            # SECURITY: private token is never logged — only used in the
            # Authorization header. The groups= field restriction prevents
            # it from appearing in ORM read() responses for non-admin users.
            "Authorization": f"Bearer {self.athmovil_private_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.request(
                method,
                url,
                # For GET requests, pass payload as query params (not JSON body).
                # For POST requests, pass payload as JSON body.
                params=payload if method == "GET" else None,
                json=payload if method == "POST" else None,
                headers=headers,
                timeout=30,  # 30s timeout per call; ATH modal timeout is 600s
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            _logger.error(
                "ATH Móvil API timeout on %s %s after 30s", method, endpoint
            )
            raise ValidationError(
                _("ATH Móvil API did not respond in time. Please try again.")
            )
        except requests.exceptions.HTTPError as exc:
            _logger.error(
                "ATH Móvil API HTTP error on %s %s: %s — %s",
                method,
                endpoint,
                exc.response.status_code,
                exc.response.text[:500],  # Truncated for security
            )
            raise ValidationError(
                _("ATH Móvil API returned an error. Please try again or contact support.")
            )
        except requests.exceptions.RequestException as exc:
            _logger.error(
                "ATH Móvil API connection error on %s %s: %s", method, endpoint, exc
            )
            raise ValidationError(
                _("Could not connect to ATH Móvil API. Please check your internet connection.")
            )

    # -------------------------------------------------------------------------
    # Scheduled action (ir.cron)
    # -------------------------------------------------------------------------

    def _athmovil_expire_pending_transactions(self):
        """Cancel ATH Móvil transactions that have been pending for over 15 minutes.

        This handles the case where a customer opens the ATH Móvil payment modal
        but then closes the browser tab without approving or cancelling. In that
        scenario:
        - The JS polling loop stops (no browser to run it)
        - The 600s ATH timeout never fires a callback
        - The transaction stays in 'pending' state indefinitely

        IMPORTANT: Before cancelling, we verify the real status with ATH Móvil
        via GET /findPayment. This catches the case where the payment was actually
        COMPLETED but the webhook never arrived (network failure, server downtime).

        This method is called by the ir.cron record defined in
        data/payment_provider_data.xml every 15 minutes.
        """
        cutoff = fields.Datetime.now() - timedelta(minutes=15)
        pending_txs = self.env["payment.transaction"].search(
            [
                ("provider_code", "=", "athmovil"),
                ("state", "=", "pending"),
                ("create_date", "<", cutoff),
            ]
        )

        done_count = 0
        cancelled_count = 0

        for tx in pending_txs:
            if not tx.athmovil_ecommerce_id:
                # No ticket was ever created — genuinely abandoned before payment started
                tx._set_canceled(
                    state_message=_(
                        "ATH Móvil payment expired — "
                        "payment session was never initiated."
                    )
                )
                cancelled_count += 1
                continue

            # Ticket exists — verify real status with ATH Móvil before cancelling.
            # GET /findPayment is idempotent and safe to call here.
            try:
                provider = tx.provider_id
                # Build the GET URL with query param directly in the endpoint string.
                # _athmovil_get_api_url() prepends ATH_API_BASE_URL, so we pass
                # the path segment including the query string here.
                result = provider._athmovil_make_request(
                    "business/findPayment",
                    payload={
                        "publicToken": provider.athmovil_public_token,
                        "ecommerceId": tx.athmovil_ecommerce_id,
                    },
                    method="POST",
                )
                data = result.get("data", result)
                ath_status = data.get("ecommerceStatus", "")

                if ath_status == "COMPLETED":
                    # Payment was approved in the ATH Móvil app but the webhook
                    # never reached our server. Mark as done to avoid revenue loss.
                    tx._set_done()
                    tx.message_post(
                        body=_(
                            "ATH Móvil: payment was COMPLETED in ATH Móvil app "
                            "but webhook was never received. Status recovered by cron."
                        )
                    )
                    done_count += 1
                else:
                    # IN_PROCESS or any other status — genuinely abandoned
                    tx._set_canceled(
                        state_message=_(
                            "ATH Móvil payment expired — "
                            "customer did not complete payment within 15 minutes."
                        )
                    )
                    cancelled_count += 1

            except (ValidationError, requests.exceptions.RequestException) as exc:
                # Network/API errors: cancel conservatively and log.
                # Better to cancel and let the merchant re-issue than to leave
                # the transaction in limbo indefinitely.
                _logger.warning(
                    "ATH Móvil cron: could not verify status for tx %s "
                    "(ecommerceId: %s): %s — cancelling conservatively.",
                    tx.reference,
                    tx.athmovil_ecommerce_id,
                    exc,
                )
                tx._set_canceled(
                    state_message=_(
                        "ATH Móvil payment expired — "
                        "could not verify status with ATH Móvil API."
                    )
                )
                cancelled_count += 1

        _logger.info(
            "ATH Móvil cron: processed %d pending transactions "
            "(%d recovered as done, %d cancelled).",
            len(pending_txs),
            done_count,
            cancelled_count,
        )

    # -------------------------------------------------------------------------
    # Scheduled action: Reconciliation with ATH Business reports
    # -------------------------------------------------------------------------

    def _athmovil_reconcile_transactions(self):
        """Compare Odoo transactions with ATH Móvil's transaction report.

        Calls GET /transactionReport for the last 24 hours and flags
        discrepancies: payments in ATH but not in Odoo, or amount mismatches.
        """
        from datetime import datetime, timedelta

        providers = self.env["payment.provider"].search(
            [("code", "=", "athmovil"), ("state", "in", ("enabled", "test"))]
        )
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        today = datetime.now().strftime("%Y-%m-%d 23:59:59")

        for provider in providers:
            try:
                result = provider._athmovil_make_request(
                    "transactionReport",
                    payload={
                        "publicToken": provider.athmovil_public_token,
                        "fromDate": yesterday,
                        "toDate": today,
                    },
                    method="POST",
                )
            except Exception as exc:
                _logger.warning(
                    "ATH Móvil reconciliation: could not fetch report for %s: %s",
                    provider.name,
                    exc,
                )
                continue

            ath_transactions = result if isinstance(result, list) else []
            for ath_tx in ath_transactions:
                ref_number = ath_tx.get("referenceNumber", "")
                ath_total = float(ath_tx.get("total", 0))
                ath_status = ath_tx.get("status", "")
                metadata1 = ath_tx.get("metadata1", "")

                if ath_status != "COMPLETED":
                    continue

                odoo_tx = self.env["payment.transaction"].search(
                    [
                        ("reference", "=", metadata1),
                        ("provider_code", "=", "athmovil"),
                        ("provider_id", "=", provider.id),
                    ],
                    limit=1,
                )

                if not odoo_tx:
                    _logger.warning(
                        "ATH Móvil reconciliation: COMPLETED payment in ATH "
                        "(ref: %s, $%.2f) has no matching Odoo transaction.",
                        ref_number,
                        ath_total,
                    )
                    continue

                if odoo_tx.state != "done":
                    odoo_tx.message_post(
                        body=_(
                            "⚠️ ATH Móvil reconciliation: payment is COMPLETED "
                            "in ATH Business (ref: %s, $%.2f) but Odoo state "
                            "is '%s'. Please investigate."
                        )
                        % (ref_number, ath_total, odoo_tx.state)
                    )

                if abs(ath_total - odoo_tx.amount) > 0.01:
                    odoo_tx.message_post(
                        body=_(
                            "⚠️ ATH Móvil reconciliation: amount mismatch. "
                            "ATH reports $%.2f but Odoo has $%.2f."
                        )
                        % (ath_total, odoo_tx.amount)
                    )

        _logger.info("ATH Móvil reconciliation completed for %d providers.", len(providers))
