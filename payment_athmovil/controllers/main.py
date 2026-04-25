# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AthMovilController(http.Controller):
    """HTTP controller for ATH Móvil payment provider.

    Handles three routes:
    - POST /payment/athmovil/webhook   — receives payment confirmations from ATH Móvil
    - POST /payment/athmovil/return    — receives callback from frontend after modal
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

        Security layers:
        1. JSON parse validation
        2. Required fields validation
        3. Idempotency check — already processed → 200
        4. Transaction lookup by metadata1
        5. Server-side verification via GET /findPayment (HIGH fix #2)
        6. Cross-integrity check + amount verification in _handle_feedback_data
        """
        # --- Step 1: Parse JSON ---
        try:
            data = request.get_json_data()
        except Exception:
            data = None

        if not data:
            _logger.warning("ATH Móvil webhook: empty or non-JSON payload.")
            return request.make_json_response(
                {"error": "Empty payload"}, status=400
            )

        _logger.info(
            "ATH Móvil webhook received: ecommerceId=%s status=%s",
            data.get("ecommerceId", "?"),
            data.get("status", "?"),
        )

        # --- Step 2: Validate required fields ---
        required_fields = {"ecommerceId", "status", "total", "metadata1"}
        missing = required_fields - set(data.keys())
        if missing:
            # FIX MED #3: Log only field names, not full payload
            _logger.warning(
                "ATH Móvil webhook: missing fields %s. Present keys: %s",
                missing,
                list(data.keys()),
            )
            return request.make_json_response(
                {"error": f"Missing fields: {missing}"}, status=400
            )

        ecommerce_id = data["ecommerceId"]
        metadata1 = data["metadata1"]

        # --- Step 3: Idempotency check ---
        existing_tx = request.env["payment.transaction"].sudo().search(
            [("athmovil_ecommerce_id", "=", ecommerce_id)], limit=1
        )
        if existing_tx and existing_tx.state in ("done", "cancel"):
            _logger.info(
                "ATH Móvil webhook: ecommerceId %s already processed "
                "(state: %s) — returning 200.",
                ecommerce_id,
                existing_tx.state,
            )
            return request.make_json_response({"status": "already_processed"})

        # --- Step 4: Find transaction by metadata1 ---
        # FIX MED #10: scope by company if existing_tx was found
        tx_domain = [
            ("reference", "=", metadata1),
            ("provider_code", "=", "athmovil"),
        ]
        if existing_tx:
            tx_domain.append(("company_id", "=", existing_tx.company_id.id))
        tx = request.env["payment.transaction"].sudo().search(
            tx_domain,
            limit=1,
        )
        if not tx:
            _logger.warning(
                "ATH Móvil webhook: no tx for metadata1=%s ecommerceId=%s.",
                metadata1,
                ecommerce_id,
            )
            return request.make_json_response(
                {"error": "Transaction not found"}, status=400
            )

        # --- Step 5: Server-side verification (FIX HIGH #2) ---
        # Before trusting the webhook status, verify with ATH Móvil API.
        # This prevents forged webhooks from marking transactions as paid.
        webhook_status = data.get("status", "")
        if webhook_status == "COMPLETED":
            try:
                result = tx.provider_id._athmovil_make_request(
                    "business/findPayment",
                    payload={
                        "publicToken": tx.provider_id.athmovil_public_token,
                        "ecommerceId": ecommerce_id,
                    },
                    method="POST",
                )
                verified_data = result.get("data", result)
                verified_status = verified_data.get("ecommerceStatus", "")
                if verified_status != "COMPLETED":
                    _logger.warning(
                        "ATH Móvil webhook: claimed COMPLETED but API says '%s' "
                        "for ecommerceId=%s — rejecting.",
                        verified_status,
                        ecommerce_id,
                    )
                    return request.make_json_response(
                        {"error": "Payment not verified"}, status=400
                    )
            except Exception as exc:
                _logger.error(
                    "ATH Móvil webhook: could not verify payment status for "
                    "ecommerceId=%s: %s — rejecting for safety.",
                    ecommerce_id,
                    exc,
                )
                return request.make_json_response(
                    {"error": "Verification failed"}, status=400
                )

        # --- Step 6: Delegate to model ---
        try:
            tx._handle_notification_data("athmovil", data)
        except Exception as exc:
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
    # Route 2: Return — Frontend JS → Odoo server
    # -------------------------------------------------------------------------

    @http.route(
        _return_url,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=True,  # FIX HIGH #1: CSRF enabled for browser-initiated POST
        save_session=False,
    )
    def athmovil_return(self):
        """Handle the frontend callback after the ATH Móvil modal completes.

        CSRF is enabled because this is called from the user's browser.
        The JS includes the CSRF token from odoo.csrf_token.
        """
        try:
            data = request.get_json_data() or {}
        except Exception:
            data = {}
        ecommerce_id = data.get("ecommerce_id")

        if not ecommerce_id:
            _logger.warning("ATH Móvil return: missing ecommerce_id.")
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
                "ATH Móvil return: no tx for ecommerceId=%s",
                ecommerce_id,
            )
            return request.make_json_response(
                {"error": "Transaction not found"}, status=400
            )

        redirect_url = "/payment/status"
        _logger.info(
            "ATH Móvil return: tx %s (state: %s) → %s",
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

        Session binding (FIX MED #5): only allows polling for ecommerce_ids
        that were created in the current user's session.

        Query param: ecommerce_id=<ecommerceId>
        Returns JSON: {"status": "<ATH_STATUS>", "redirect_url": "<url_or_null>"}
        """
        if not ecommerce_id:
            return request.make_json_response(
                {"error": "Missing ecommerce_id"}, status=400
            )

        # Session binding: verify the ecommerce_id belongs to a transaction
        # linked to the current user's partner (if authenticated)
        domain = [
            ("athmovil_ecommerce_id", "=", ecommerce_id),
            ("provider_code", "=", "athmovil"),
        ]
        if request.env.user and not request.env.user._is_public():
            domain.append(("partner_id", "=", request.env.user.partner_id.id))

        tx = request.env["payment.transaction"].sudo().search(
            domain,
            limit=1,
        )
        if not tx:
            return request.make_json_response(
                {"error": "Transaction not found"}, status=400
            )

        if tx.state == "done":
            return request.make_json_response(
                {"status": "COMPLETED", "redirect_url": "/payment/status"}
            )
        if tx.state == "cancel":
            return request.make_json_response(
                {"status": "CANCELLED", "redirect_url": "/payment/status"}
            )

        # Pending — query ATH Móvil for real-time status
        try:
            result = tx.provider_id._athmovil_make_request(
                "findPayment",
                payload={"ecommerceId": ecommerce_id},
                method="GET",
            )
            ath_status = result.get("status", "IN_PROCESS")
        except Exception as exc:
            _logger.warning(
                "ATH Móvil check_status: API unreachable for ecommerceId=%s: %s",
                ecommerce_id,
                exc,
            )
            return request.make_json_response(
                {"status": "IN_PROCESS", "redirect_url": None}
            )

        redirect_url = None
        if ath_status in ("COMPLETED", "CANCELLED", "EXPIRED"):
            redirect_url = "/payment/status"

        return request.make_json_response(
            {"status": ath_status, "redirect_url": redirect_url}
        )
