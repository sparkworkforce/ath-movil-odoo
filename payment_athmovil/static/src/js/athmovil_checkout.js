/**
 * ATH Móvil Payment Checkout — Frontend Module
 *
 * ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
 * This module is an independent integration and is not affiliated with
 * or endorsed by EVERTEC.
 *
 * Feature 3: Smarter checkout UX
 * - No blocking banner — info is inline in the template
 * - Button shows loading state on click
 * - Polling fallback if webhook hasn't fired
 */

const POLL_INTERVAL_MS = 5000;
const POLL_MAX_MS = 600000;

document.addEventListener("DOMContentLoaded", () => {
    const dataEl = document.getElementById("o_athmovil_data");
    if (!dataEl) return;
    initAthMovilCheckout(dataEl);
});

function initAthMovilCheckout(dataEl) {
    const config = readConfig(dataEl);
    initAthMovilModal(config);
}

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

function safeParseJSON(str, fallback) {
    try { return str ? JSON.parse(str) : fallback; }
    catch (_) { return fallback; }
}

function initAthMovilModal(config) {
    if (typeof ATHM_Checkout === "undefined") {
        console.error("ATH Móvil: ATHM_Checkout not loaded from CDN.");
        redirectTo(config.statusUrl);
        return;
    }

    // Show button loading state on click
    const btn = document.getElementById("ATHMovil_Checkout_Button");
    if (btn) {
        btn.addEventListener("click", () => {
            const label = btn.querySelector(".o_athmovil_btn_label");
            const loading = btn.querySelector(".o_athmovil_btn_loading");
            if (label) label.classList.add("d-none");
            if (loading) loading.classList.remove("d-none");
            btn.disabled = true;

            const loadingEl = document.getElementById("o_athmovil_loading");
            if (loadingEl) loadingEl.classList.remove("d-none");
        });
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

async function onCompletedPayment(response, config) {
    try {
        const result = await postJSON(config.returnUrl, {
            ecommerce_id: config.ecommerceId,
        });
        redirectTo(result.redirect_url || config.statusUrl);
    } catch (err) {
        console.error("ATH Móvil: error confirming payment:", err);
        startPolling(config);
    }
}

function onCancelledPayment(response, config) {
    redirectTo(config.statusUrl);
}

function onExpiredPayment(response, config) {
    redirectTo(config.statusUrl);
}

function startPolling(config) {
    const startTime = Date.now();
    const poll = async () => {
        if (Date.now() - startTime >= POLL_MAX_MS) {
            redirectTo(config.statusUrl);
            return;
        }
        try {
            const url = `${config.checkStatusUrl}?ecommerce_id=${encodeURIComponent(config.ecommerceId)}`;
            const data = await (await fetch(url)).json();
            if (data.redirect_url && (data.status === "COMPLETED" || data.status === "CANCELLED" || data.status === "EXPIRED")) {
                redirectTo(data.redirect_url);
                return;
            }
        } catch (err) {
            console.warn("ATH Móvil polling failed, retrying:", err);
        }
        setTimeout(poll, POLL_INTERVAL_MS);
    };
    setTimeout(poll, POLL_INTERVAL_MS);
}

async function postJSON(url, data) {
    const csrfToken = (typeof odoo !== "undefined" && odoo.csrf_token) || "";
    const target = csrfToken ? `${url}?csrf_token=${encodeURIComponent(csrfToken)}` : url;
    const r = await fetch(target, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status} from ${url}`);
    return r.json();
}

function redirectTo(url) {
    window.location.href = url || "/payment/status";
}
