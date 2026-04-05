/**
 * ATH Móvil Payment Checkout — Frontend Module
 *
 * ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
 * This module is an independent integration and is not affiliated with
 * or endorsed by EVERTEC.
 *
 * Responsibilities:
 * 1. Show a dismissible pre-checkout banner (5 seconds) informing the
 *    customer that the ATH Móvil app is required (RF-04, Gap 4)
 * 2. Initialize the ATHM_Checkout modal with data from the server
 * 3. Handle all three ATH Móvil callbacks:
 *    - onCompletedPayment: POST to /return, wait for redirect URL, redirect
 *    - onCancelledPayment: redirect to /payment/status
 *    - onExpiredPayment:   redirect to /payment/status
 * 4. Polling fallback: if webhook hasn't fired, poll /check_status every 5s
 *    for up to 600 seconds (matching ATH Móvil's modal timeout)
 *
 * This file is registered as an ES module in __manifest__.py under assets.
 * It runs after athmovil_base.js (loaded via <script> in the QWeb template).
 *
 * Translations: uses _t() from @web/core/l10n/translation for all
 * user-visible strings so they can be translated via es.po.
 */

import { _t } from "@web/core/l10n/translation";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Polling interval in milliseconds (5 seconds) */
const POLL_INTERVAL_MS = 5000;

/** Maximum polling duration in milliseconds (600 seconds = ATH modal timeout) */
const POLL_MAX_MS = 600000;

/** Duration to show the pre-checkout banner before opening the modal (ms) */
const BANNER_DURATION_MS = 5000;

// ---------------------------------------------------------------------------
// Entry point — runs when the DOM is ready
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const dataEl = document.getElementById("o_athmovil_data");
    if (!dataEl) {
        // Template not present on this page — nothing to do
        return;
    }
    initAthMovilCheckout(dataEl);
});

// ---------------------------------------------------------------------------
// Main initialization
// ---------------------------------------------------------------------------

/**
 * Initialize the ATH Móvil checkout flow.
 * Shows the pre-checkout banner, then opens the ATHM_Checkout modal.
 *
 * @param {HTMLElement} dataEl - The hidden data container element from the QWeb template
 */
async function initAthMovilCheckout(dataEl) {
    const config = readConfig(dataEl);

    // Show the pre-checkout banner for BANNER_DURATION_MS before opening modal
    await showPreCheckoutBanner(config);

    // Initialize the ATH Móvil modal
    initAthMovilModal(config);
}

// ---------------------------------------------------------------------------
// Config reader
// ---------------------------------------------------------------------------

/**
 * Read payment configuration from the hidden data container element.
 * Values are set by the QWeb template via t-att-data-* attributes.
 *
 * @param {HTMLElement} dataEl
 * @returns {Object} config
 */
function readConfig(dataEl) {
    return {
        publicToken:    dataEl.dataset.publicToken    || "",
        amount:         parseFloat(dataEl.dataset.amount)    || 0,
        subtotal:       parseFloat(dataEl.dataset.subtotal)  || 0,
        tax:            parseFloat(dataEl.dataset.tax)       || 0,
        metadata1:      dataEl.dataset.metadata1      || "",
        metadata2:      dataEl.dataset.metadata2      || "",
        ecommerceId:    dataEl.dataset.ecommerceId    || "",
        items:          safeParseJSON(dataEl.dataset.items, []),
        returnUrl:      dataEl.dataset.returnUrl      || "/payment/athmovil/return",
        checkStatusUrl: dataEl.dataset.checkStatusUrl || "/payment/athmovil/check_status",
        statusUrl:      dataEl.dataset.statusUrl      || "/payment/status",
    };
}

/**
 * Safely parse a JSON string, returning fallback on error.
 *
 * @param {string} str
 * @param {*} fallback
 * @returns {*}
 */
function safeParseJSON(str, fallback) {
    try {
        return str ? JSON.parse(str) : fallback;
    } catch (_) {
        return fallback;
    }
}

// ---------------------------------------------------------------------------
// Pre-checkout banner (Gap 4 — RF-04)
// ---------------------------------------------------------------------------

/**
 * Display a dismissible info banner informing the customer that the ATH Móvil
 * app is required. The banner auto-dismisses after BANNER_DURATION_MS.
 *
 * @param {Object} config
 * @returns {Promise<void>} resolves when the banner is dismissed or times out
 */
function showPreCheckoutBanner(config) {
    return new Promise((resolve) => {
        // Create banner element
        const banner = document.createElement("div");
        banner.id = "o_athmovil_precheckout_banner";
        banner.setAttribute("role", "alert");
        banner.setAttribute("data-testid", "athmovil-precheckout-banner");
        banner.className = "alert alert-warning alert-dismissible fade show";
        banner.style.cssText = "position:fixed;top:1rem;left:50%;transform:translateX(-50%);z-index:9999;min-width:320px;max-width:600px;";
        banner.innerHTML = `
            <strong>${_t("ATH Móvil Payment")}</strong><br>
            ${_t("You will need the ATH Móvil app on your phone to approve this payment. The payment request will expire in 10 minutes.")}<br>
            <small>
                ${_t("Download:")}
                <a href="https://apps.apple.com/app/ath-movil/id658539297"
                   target="_blank" rel="noopener noreferrer">${_t("App Store")}</a>
                |
                <a href="https://play.google.com/store/apps/details?id=com.evertec.athmovil.android"
                   target="_blank" rel="noopener noreferrer">${_t("Google Play")}</a>
            </small>
            <button type="button"
                    class="btn-close"
                    aria-label="${_t("Close")}"
                    data-testid="athmovil-banner-close">
            </button>
        `;

        document.body.appendChild(banner);

        // Dismiss handler
        const dismiss = () => {
            banner.remove();
            resolve();
        };

        // Close button dismisses immediately
        banner.querySelector(".btn-close").addEventListener("click", dismiss);

        // Auto-dismiss after BANNER_DURATION_MS
        setTimeout(dismiss, BANNER_DURATION_MS);
    });
}

// ---------------------------------------------------------------------------
// ATH Móvil modal initialization
// ---------------------------------------------------------------------------

/**
 * Initialize the ATHM_Checkout object and open the ATH Móvil payment modal.
 * ATHM_Checkout is provided by athmovil_base.js loaded from the CDN.
 *
 * @param {Object} config
 */
function initAthMovilModal(config) {
    // Show loading spinner while modal initializes
    const loadingEl = document.getElementById("o_athmovil_loading");
    if (loadingEl) {
        loadingEl.classList.remove("d-none");
    }

    // Guard: ATHM_Checkout must be available from the CDN script
    if (typeof ATHM_Checkout === "undefined") {
        console.error("ATH Móvil: ATHM_Checkout is not defined. CDN script may have failed to load.");
        redirectTo(config.statusUrl);
        return;
    }
    // eslint-disable-next-line no-undef
    ATHM_Checkout.init({
        env: config.publicToken === "dummy" ? "sandbox" : "production",
        publicToken: config.publicToken,
        timeout: 600,
        total: config.amount,
        subtotal: config.subtotal,
        tax: config.tax,
        metadata1: config.metadata1,
        metadata2: config.metadata2,
        items: config.items,

        onCompletedPayment: (response) => onCompletedPayment(response, config),
        onCancelledPayment: (response) => onCancelledPayment(response, config),
        onExpiredPayment:   (response) => onExpiredPayment(response, config),
    });
}

// ---------------------------------------------------------------------------
// Payment callbacks
// ---------------------------------------------------------------------------

/**
 * Called by ATH Móvil when the customer approves the payment in the app.
 * POSTs to /payment/athmovil/return and waits for the server to confirm
 * before redirecting — ensures the customer only sees the success page
 * after server-side confirmation (RF-04, Q3 decision: Option A).
 *
 * @param {Object} response - ATH Móvil callback response
 * @param {Object} config
 */
async function onCompletedPayment(response, config) {
    try {
        const result = await postJSON(config.returnUrl, {
            ecommerce_id: config.ecommerceId,
        });
        redirectTo(result.redirect_url || config.statusUrl);
    } catch (err) {
        console.error("ATH Móvil: error confirming payment with server:", err);
        // Fall back to polling if the /return call fails
        startPolling(config);
    }
}

/**
 * Called by ATH Móvil when the customer cancels the payment.
 *
 * @param {Object} response
 * @param {Object} config
 */
function onCancelledPayment(response, config) {
    redirectTo(config.statusUrl);
}

/**
 * Called by ATH Móvil when the payment modal times out (600s).
 *
 * @param {Object} response
 * @param {Object} config
 */
function onExpiredPayment(response, config) {
    redirectTo(config.statusUrl);
}

// ---------------------------------------------------------------------------
// Polling fallback
// ---------------------------------------------------------------------------

/**
 * Poll /payment/athmovil/check_status every POLL_INTERVAL_MS milliseconds
 * as a fallback when the webhook has not yet confirmed the payment.
 * Stops after POLL_MAX_MS (600 seconds) to match ATH Móvil's modal timeout.
 *
 * This is the ONLY polling mechanism — server-side polling is prohibited
 * as it would block Odoo worker processes (RNF-08).
 *
 * @param {Object} config
 */
function startPolling(config) {
    const startTime = Date.now();

    const poll = async () => {
        // Stop polling if we've exceeded the maximum duration
        if (Date.now() - startTime >= POLL_MAX_MS) {
            redirectTo(config.statusUrl);
            return;
        }

        try {
            const url = `${config.checkStatusUrl}?ecommerce_id=${encodeURIComponent(config.ecommerceId)}`;
            const response = await fetch(url, { method: "GET" });
            const data = await response.json();

            if (data.status === "COMPLETED" && data.redirect_url) {
                redirectTo(data.redirect_url);
                return;
            }
            if (data.status === "CANCELLED" || data.status === "EXPIRED") {
                redirectTo(data.redirect_url || config.statusUrl);
                return;
            }
            // IN_PROCESS or unknown — continue polling
        } catch (err) {
            console.warn("ATH Móvil polling: request failed, retrying:", err);
        }

        setTimeout(poll, POLL_INTERVAL_MS);
    };

    // Start first poll after one interval
    setTimeout(poll, POLL_INTERVAL_MS);
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/**
 * POST JSON data to a URL and return the parsed response.
 *
 * @param {string} url
 * @param {Object} data
 * @returns {Promise<Object>}
 */
async function postJSON(url, data) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status} from ${url}`);
    }
    return response.json();
}

/**
 * Redirect the browser to the given URL.
 *
 * @param {string} url
 */
function redirectTo(url) {
    window.location.href = url || "/payment/status";
}
