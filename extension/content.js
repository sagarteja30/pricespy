(function() {
  'use strict';

  const API_URLS = [
    "https://web-production-21127.up.railway.app",
    "https://pricespy-api.onrender.com",
    window.location.origin
  ];

  let currentApiUrl = API_URLS[0];
  let analysisDone = false;

  function getUserId() {
    let uid = localStorage.getItem("pricespy_uid");
    if (!uid) {
      uid = "user_" + Math.random().toString(36).substr(2, 9) + Date.now();
      localStorage.setItem("pricespy_uid", uid);
    }
    return uid;
  }

  const USER_ID = getUserId();

  function isProductPage() {
    const url = window.location.href;
    return (
      url.includes("/dp/") ||
      url.includes("/gp/product/") ||
      url.includes("/gp/aw/d/") ||
      url.includes("flipkart.com/p/") ||
      document.getElementById("productTitle") !== null ||
      document.querySelector(".a-price-whole") !== null
    );
  }

  function getPriceFromPage() {
    const selectors = [
      ".a-price-whole",
      "#priceblock_ourprice",
      "#priceblock_dealprice",
      ".a-offscreen",
      "[data-a-color='price'] .a-offscreen"
    ];
    
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) {
        const text = el.innerText || el.textContent;
        const cleaned = text.replace(/[^0-9.]/g, "").trim();
        const price = parseFloat(cleaned);
        if (price > 0) {
          console.log("PriceSpy: price found:", price);
          return price;
        }
      }
    }
    
    const priceMatch = document.body.innerText.match(/₹\s*([\d,]+)/);
    if (priceMatch) {
      const price = parseFloat(priceMatch[1].replace(/,/g, ""));
      if (price > 0) {
        console.log("PriceSpy: price found from text:", price);
        return price;
      }
    }
    
    return null;
  }

  function getTitleFromPage() {
    const selectors = [
      "#productTitle",
      "#title",
      "h1.product-title-word-break",
      "[data-automation='product-title']"
    ];
    
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) {
        const text = el.innerText.trim();
        if (text.length > 5) {
          return text.slice(0, 100);
        }
      }
    }
    return "Unknown Product";
  }

  function createWidget(data) {
    const existing = document.getElementById("pricespy-widget");
    if (existing) existing.remove();

    const isWait = data.recommendation === "WAIT";
    const color = isWait ? "#16a34a" : "#dc2626";
    const arrow = isWait ? "↓" : "↑";
    const recColor = isWait ? "#dcfce7" : "#fee2e2";

    const widget = document.createElement("div");
    widget.id = "pricespy-widget";
    widget.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 300px;
      background: white;
      border-radius: 16px;
      padding: 20px;
      z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      box-shadow: 0 8px 32px rgba(0,0,0,0.15);
      animation: pricespySlideIn 0.3s ease-out;
    `;

    const changeSymbol = data.price_change >= 0 ? "+" : "";
    const changeColor = data.price_change >= 0 ? "text-red-600" : "text-green-600";

    widget.innerHTML = `
      <style>
        @keyframes pricespySlideIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      </style>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:20px">🔮</span>
          <span style="font-weight:700;font-size:16px;color:#1f2937">PriceSpy AI</span>
        </div>
        <button onclick="document.getElementById('pricespy-widget').remove()"
          style="background:none;border:none;cursor:pointer;font-size:20px;color:#9ca3af;padding:4px">×</button>
      </div>
      
      <div style="background:${recColor};padding:16px;border-radius:12px;text-align:center;margin-bottom:16px">
        <div style="font-size:32px;margin-bottom:4px">${arrow}</div>
        <div style="font-size:24px;font-weight:700;color:${color};margin-bottom:4px">
          ${data.recommendation}
        </div>
        <div style="font-size:13px;color:#4b5563">${data.reason}</div>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
        <div style="background:#f9fafb;padding:12px;border-radius:12px;text-align:center">
          <div style="font-size:11px;color:#6b7280;margin-bottom:4px">Current Price</div>
          <div style="font-size:18px;font-weight:700">₹${Number(data.current_price).toLocaleString()}</div>
        </div>
        <div style="background:#f9fafb;padding:12px;border-radius:12px;text-align:center">
          <div style="font-size:11px;color:#6b7280;margin-bottom:4px">Predicted (14 days)</div>
          <div style="font-size:18px;font-weight:700;color:${color}">
            ₹${Number(data.predicted_price).toLocaleString()}
          </div>
        </div>
      </div>
      
      <div style="font-size:13px;color:#6b7280;text-align:center;margin-bottom:12px">
        Expected change: <span class="${changeColor}" style="font-weight:600">
          ${changeSymbol}₹${Math.abs(data.price_change).toLocaleString()} (${changeSymbol}${data.pct_change}%)
        </span>
      </div>
      
      <div style="display:flex;justify-content:space-between;padding:12px;background:#f0fdf4;border-radius:8px;margin-bottom:16px">
        <div>
          <div style="font-size:10px;color:#6b7280">30-day low</div>
          <div style="font-size:14px;font-weight:600;color:#16a34a">₹${Number(data.best_price_30d).toLocaleString()}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:10px;color:#6b7280">30-day high</div>
          <div style="font-size:14px;font-weight:600;color:#dc2626">₹${Number(data.worst_price_30d).toLocaleString()}</div>
        </div>
      </div>
      
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#9ca3af;margin-bottom:16px">
        <span>Confidence: ${data.confidence}%</span>
        <span>${data.days_tracked} days tracked</span>
      </div>
      
      <a href="${window.location.href.split('?')[0]}?tag=sagarteja30-21" 
         target="_blank"
         style="display:block;background:#ff9900;color:white;text-align:center;padding:12px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">
        🛒 Buy Now on Amazon
      </a>
    `;

    document.body.appendChild(widget);
    console.log("PriceSpy: widget added");
  }

  async function tryApiCall(url, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    try {
      const res = await fetch(url + "/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      clearTimeout(timeout);
      
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch (e) {
      clearTimeout(timeout);
      console.log("PriceSpy: API not available at", url, e.message);
      return null;
    }
  }

  async function analyzePage() {
    if (analysisDone) return;
    
    console.log("PriceSpy: analyzing page...");
    
    if (!isProductPage()) {
      console.log("PriceSpy: not a product page");
      return;
    }

    const price = getPriceFromPage();
    const title = getTitleFromPage();

    if (!price) {
      console.log("PriceSpy: no price found");
      return;
    }

    analysisDone = true;
    const payload = {
      url: window.location.href,
      price: price,
      title: title,
      user_id: USER_ID
    };

    for (const apiUrl of API_URLS) {
      console.log("PriceSpy: trying API:", apiUrl);
      const data = await tryApiCall(apiUrl, payload);
      
      if (data && !data.error) {
        console.log("PriceSpy: success!", data);
        window._priceSpyData = data;
        createWidget(data);
        return;
      }
    }

    console.log("PriceSpy: no APIs available, showing local prediction");
    window._priceSpyData = {
      current_price: price,
      predicted_price: Math.round(price * 1.02),
      price_change: Math.round(price * 0.02),
      pct_change: 2.0,
      recommendation: "TRACKING",
      reason: "Connect to internet for real predictions",
      confidence: 30,
      best_price_30d: Math.round(price * 0.9),
      worst_price_30d: Math.round(price * 1.1),
      days_tracked: 1
    };
    createWidget(window._priceSpyData);
  }

  if (document.readyState === "complete") {
    setTimeout(analyzePage, 1500);
  } else {
    window.addEventListener("load", () => setTimeout(analyzePage, 1500));
  }

  const observer = new MutationObserver(() => {
    if (!analysisDone && isProductPage()) {
      setTimeout(analyzePage, 1000);
    }
  });
  
  observer.observe(document.body, { childList: true, subtree: true });

})();
