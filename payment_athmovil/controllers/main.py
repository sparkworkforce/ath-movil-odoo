# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

import logging
import pprint

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AthMovilController(http.Controller):
    """HTTP controller for ATH Móvil payment provider.

    Handles three routes:
    - POST /payment/athmovil/webhook   — receives payment confirmations from ATH Móvil
    - POST /payment/athmovil/return    — receives callback from frontend after modal completes
    - GET  /payment/athmovil/check_status — polling endpoint for frontend JS fallback
    """

    _webhook_url = "/payment/athmovil/webhook"
    _return_url = "/payment/athmovil/return"
    _check_status_url = "/payment/athmovil/check_status"

    # -------------------------------------------------------------------------
    # Route 1: Webhook — ATH Móvil → Odoo server
    # -------------------------------------------------------------------------

    @http.route(
        _webhook_url,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def athmovil_webhook(self):
        """Receive and process payment status notifications from ATH Móvil.

        ATH Móvil calls this endpoint when a payment is COMPLETED, CANCELLED,
        or EXPIRED. This controller is the entry point for all server-side
        payment confirmations.

        Security layers applied in order:
        1. JSON parse validation — reject malformed payloads immediately
        2. Required fields validation — reject incomplete payloads
        3. IDEMPOTENCY CHECK — if already processed, return 200 without re-processing
        4. Transaction lookup — find tx by metadata1 (Odoo reference)
        5. Delegate to _handle_feedback_data() which performs:
           - CROSS-INTEGRITY CHECK (ecommerceId vs stored value)
           - Amount verification (±$0.01 tolerance)
           - State transition (_set_done / _set_canceled)

        Note: ATH Móvil Business API does NOT provide HMAC signatures or webhook
        secrets. Integrity is verified via the checks above, not via signature.

        Uses type="http" (not type="json") so we can return real HTTP 400 status
        codes on validation failures. type="json" routes in Odoo always return
        200 regardless of the response content.

        Returns HTTP 200 on success (including idempotent re-delivery).
        Returns HTTP 400 on validation failure (logged, no exception raised to
        prevent Odoo from crashing on malformed external input).
        """
        # --- Step 1: Parse JSON body manually (required for type="http" routes) ---
        try:
            data = request.get_json_data()
        except Exception:
            data = None

        if not data:
            _logger.warning("ATH Móvil webhook: received empty or non-JSON payload.")
            return request.make_json_response(
                {"error": "Empty payload"}, status=400
            )

        _logger.info(
            "ATH Móvil webhook received:\n%s", pprint.pformat(data)
        )

        # --- Step 2: Validate required fields ---
        required_fields = {"ecommerceId", "status", "total", "metadata1"}
        missing = required_fields - set(data.keys())
        if missing:
            _logger.warning(
                "ATH Móvil webhook: missing required fields %s. Payload: %s",
                missing,
                data,
            )
            return request.make_json_response(
                {"error": f"Missing fields: {missing}"}, status=400
            )

        ecommerce_id = data["ecommerceId"]
        metadata1 = data["metadata1"]

        # --- Step 3: IDEMPOTENCY CHECK ---
        # If this ecommerceId has already been processed to a final state
        # (done or cancel), return 200 immediately without re-processing.
        # This handles duplicate webhook deliveries from ATH Móvil.
        # Note: this check is intentionally in the CONTROLLER, not in
        # _handle_feedback_data(), because idempotency is a transport-layer
        # concern. The model method performs the CROSS-INTEGRITY CHECK instead.
        existing_tx = request.env["payment.transaction"].sudo().search(
            [("athmovil_ecommerce_id", "=", ecommerce_id)], limit=1
        )
        if existing_tx and existing_tx.state in ("done", "cancel"):
            _logger.info(
                "ATH Móvil webhook: ecommerceId %s already processed "
                "(tx %s, state: %s) — returning 200 without re-processing.",
                ecommerce_id,
                existing_tx.reference,
                existing_tx.state,
            )
            return request.make_json_response({"status": "already_processed"})

        # --- Step 4: Find transaction by metadata1 (Odoo reference) ---
        tx = request.env["payment.transaction"].sudo().search(
            [("reference", "=", metadata1), ("provider_code", "=", "athmovil")],
            limit=1,
        )
        if not tx:
            _logger.warning(
                "ATH Móvil webhook: no transaction found for metadata1=%s "
                "(ecommerceId=%s).",
                metadata1,
                ecommerce_id,
            )
            return request.make_json_response(
                {"error": "Transaction not found"}, status=400
            )

        # --- Step 5: Delegate to model for CROSS-INTEGRITY CHECK + state update ---
        # _handle_feedback_data() will:
        # - Verify data['ecommerceId'] == tx.athmovil_ecommerce_id (spoofing prevention)
        # - Verify amount within ±$0.01 tolerance
        # - Call _set_done() or _set_canceled() as appropriate
        try:
            tx._handle_feedback_data("athmovil", data)
        except Exception as exc:
            # Do NOT re-raise — prevents Odoo from returning a 500 to ATH Móvil,
            # which could cause ATH Móvil to retry the webhook indefinitely.
            _logger.error(
                "ATH Móvil webhook: error processing tx %s: %s",
                tx.reference,
                exc,
            )
            return request.make_json_response(
                {"error": "Processing error"}, status=400
            )

        return request.make_json_response({"status": "ok"})

    # -------------------------------------------------------------------------
    # Route 2: Return — Frontend JS → Odoo server (after onCompletedPayment)
    # -------------------------------------------------------------------------

    @http.route(
        _return_url,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def athmovil_return(self):
        """Handle the frontend callback after the ATH Móvil modal completes.

        Called by athmovil_checkout.js from the onCompletedPayment callback.
        The JS waits for this response before redirecting the customer to the
        success page — this ensures the customer only sees the success page
        after server-side confirmation.

        Uses type="http" to allow returning real HTTP 400 status codes.

        Expects JSON body: {"ecommerce_id": "<ecommerceId>"}
        Returns JSON: {"redirect_url": "<odoo_success_url>"}
        """
        try:
            data = request.get_json_data() or {}
        except Exception:
            data = {}
        ecommerce_id = data.get("ecommerce_id")

        if not ecommerce_id:
            _logger.warning("ATH Móvil return: missing ecommerce_id in request.")
            return request.make_json_response(
                {"error": "Missing ecommerce_id"}, status=400
            )

        tx = request.env["payment.transaction"].sudo().search(
            [
                ("athmovil_ecommerce_id", "=", ecommerce_id),
                ("provider_code", "=", "athmovil"),
            ],
            limit=1,
        )
        if not tx:
            _logger.warning(
                "ATH Móvil return: no transaction found for ecommerceId=%s",
                ecommerce_id,
            )
            return request.make_json_response(
                {"error": "Transaction not found"}, status=400
            )

        # Build the redirect URL based on transaction state.
        # _get_landing_route() does not exist in Odoo 17/18 payment.transaction.
        # Use the standard /payment/status route which Odoo's payment framework
        # uses as the universal landing page after any payment attempt.
        redirect_url = "/payment/status"

        _logger.info(
            "ATH Móvil return: tx %s (state: %s) → redirect to %s",
            tx.reference,
            tx.state,
            redirect_url,
        )

        return request.make_json_response({"redirect_url": redirect_url})

    # -------------------------------------------------------------------------
    # Route 3: Check Status — Frontend JS polling fallback
    # -------------------------------------------------------------------------

    @http.route(
        _check_status_url,
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def athmovil_check_status(self, ecommerce_id=None, **kwargs):
        """Polling endpoint for the frontend JS fallback mechanism.

        Called by athmovil_checkout.js every 5 seconds (up to 600s) when the
        webhook has not yet triggered the onCompletedPayment callback.

        This endpoint calls GET /findPayment on the ATH Móvil API and returns
        the current status to the frontend. The JS uses this to decide whether
        to redirect the customer or continue polling.

        Query param: ecommerce_id=<ecommerceId>
        Returns JSON: {"status": "<ATH_STATUS>", "redirect_url": "<url_or_null>"}
        """
        if not ecommerce_id:
            return request.make_json_response(
                {"error": "Missing ecommerce_id"}, status=400
            )

        tx = request.env["payment.transaction"].sudo().search(
            [
                ("athmovil_ecommerce_id", "=", ecommerce_id),
                ("provider_code", "=", "athmovil"),
            ],
            limit=1,
        )
        if not tx:
            return request.make_json_response(
                {"error": "Transaction not found"}, status=400
            )

        # If the transaction is already in a final state (set by webhook),
        # return immediately without calling ATH Móvil API.
        if tx.state == "done":
            return request.make_json_response(
                {"status": "COMPLETED", "redirect_url": "/payment/status"}
            )
        if tx.state == "cancel":
            return request.make_json_response(
                {"status": "CANCELLED", "redirect_url": "/payment/status"}
            )

        # Transaction still pending — query ATH Móvil for real-time status.
        # GET /findPayment is idempotent and safe to call repeatedly.
        try:
            result = tx.provider_id._athmovil_make_request(
                "findPayment",
                payload={"ecommerceId": ecommerce_id},
                method="GET",
            )
            ath_status = result.get("status", "IN_PROCESS")
        except Exception as exc:
            _logger.warning(
                "ATH Móvil check_status: could not reach ATH API for "
                "ecommerceId=%s: %s",
                ecommerce_id,
                exc,
            )
            # Return IN_PROCESS so the JS continues polling rather than
            # showing an error to the customer prematurely.
            return request.make_json_response(
                {"status": "IN_PROCESS", "redirect_url": None}
            )

        redirect_url = None
        if ath_status == "COMPLETED":
            redirect_url = "/payment/status"
        elif ath_status in ("CANCELLED", "EXPIRED"):
            redirect_url = "/payment/status"

        return request.make_json_response(
            {"status": ath_status, "redirect_url": redirect_url}
        )
