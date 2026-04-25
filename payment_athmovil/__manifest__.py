# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

{
    "name": "ATH Móvil Payment Provider",
    "version": "17.0.2.0.0",
    "category": "Accounting/Payment Providers",
    "summary": "Accept ATH Móvil payments in Odoo — Puerto Rico's #1 mobile payment",
    "author": "Spark Workforce LLC",
    "website": "https://www.sparkworkforcellc.com",
    "support": "jvelez@sparkworkforcellc.com",
    "license": "LGPL-3",
    "price": 0,
    "currency": "USD",
    "description": """
ATH Móvil Payment Provider for Odoo
=====================================

Integrate ATH Móvil Business as a native payment method in Odoo 17, 18, and 19.

ATH Móvil is Puerto Rico's dominant mobile payment network, operated by EVERTEC Group, LLC.

**Features:**
- Accept ATH Móvil payments in eCommerce, Invoicing, Sales, and Customer Portal
- Webhook + polling fallback for payment confirmation
- Multi-company support (each company uses its own ATH Business credentials)
- Full and partial refund support with status tracking
- Refund analytics (partial/full/failed status, cumulative amounts)
- Payment analytics dashboard with pivot, graph, and list views
- Merchant onboarding wizard with step-by-step setup guide
- Test Connection button to verify API credentials before going live
- Automatic expiry of abandoned pending transactions (cron every 15 minutes)
- Sandbox mode using publicToken = "dummy"
- Bilingual interface (English and Spanish)

**Legal Notice:**
ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
This module is an independent integration and is not affiliated with
or endorsed by EVERTEC.

Each merchant must have their own active ATH Business account.
You must accept ATH Business Terms at https://ath.business/terminos
before using this provider.

ATH Business support: 787-773-5466
    """,
    "depends": [
        "payment",
        "website",
        "account",
        # Note: 'sale' is NOT listed here intentionally — it is an optional
        # integration. _athmovil_build_items_list() uses getattr() to safely
        # access sale_order_ids only when the sale module is installed.
    ],
    "data": [
        # Load order matters: data first, then views
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_athmovil_templates.xml",
        "views/payment_transaction_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "payment_athmovil/static/src/js/athmovil_checkout.js",
        ],
    },
    "images": [
        "static/description/icon.png",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
