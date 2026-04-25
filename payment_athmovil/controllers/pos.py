# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AthMovilPosController(http.Controller):
    """POS endpoints for ATH Móvil QR code payments."""

    @http.route(
        "/pos/athmovil/create_ticket",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def pos_create_ticket(self, provider_id, amount, order_reference):
        """Create an ATH Móvil payment ticket for a POS order.

        Returns the ecommerceId and QR URL for display on the customer screen.
        """
        provider = request.env["payment.provider"].browse(provider_id)
        if not provider.exists() or provider.code != "athmovil":
            return {"error": "Invalid provider"}

        payload = {
            "publicToken": provider.athmovil_public_token,
            "total": amount,
            "subtotal": amount,
            "tax": 0.0,
            "metadata1": order_reference,
            "metadata2": provider.company_id.name,
            "items": [],
        }

        try:
            result = provider._athmovil_make_request("payment", payload, "POST")
        except Exception as exc:
            _logger.error("ATH Móvil POS: ticket creation failed: %s", exc)
            return {"error": str(exc)}

        ecommerce_id = result.get("ecommerceId", "")
        if not ecommerce_id:
            return {"error": "No ecommerceId returned"}

        base_url = provider.get_base_url()
        return {
            "ecommerce_id": ecommerce_id,
            "qr_url": "%s/payment/athmovil/qr/%s" % (base_url, ecommerce_id),
        }

    @http.route(
        "/pos/athmovil/check_payment",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def pos_check_payment(self, provider_id, ecommerce_id):
        """Poll ATH Móvil for payment status (called from POS JS)."""
        provider = request.env["payment.provider"].browse(provider_id)
        if not provider.exists() or provider.code != "athmovil":
            return {"status": "ERROR"}

        try:
            result = provider._athmovil_make_request(
                "business/findPayment",
                payload={
                    "publicToken": provider.athmovil_public_token,
                    "ecommerceId": ecommerce_id,
                },
                method="POST",
            )
            data = result.get("data", result)
            return {"status": data.get("ecommerceStatus", "OPEN")}
        except Exception:
            return {"status": "ERROR"}
