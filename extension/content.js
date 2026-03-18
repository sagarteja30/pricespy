const API_URL = "https://web-production-21127.up.railway.app"

console.log("PriceSpy: script loaded")

function getUserId() {
  let uid = localStorage.getItem("pricespy_uid")
  if (!uid) {
    uid = "user_" + Math.random().toString(36).substr(2, 9) + Date.now()
    localStorage.setItem("pricespy_uid", uid)
  }
  return uid
}

const USER_ID = getUserId()

function isProductPage() {
  const url = window.location.href
  const result = (
    url.includes("/dp/") ||
    url.includes("/gp/product/") ||
    url.includes("/gp/aw/d/") ||
    url.includes("flipkart.com/p/") ||
    document.getElementById("productTitle") !== null ||
    document.querySelector(".a-price-whole") !== null
  )
  console.log("PriceSpy: is product page?", result)
  return result
}

function getPriceFromPage() {
  const el = document.querySelector(".a-price-whole")
  if (el) {
    const text = el.innerText || el.textContent
    const cleaned = text.replace(/[₹,.\s]/g, "").trim()
    const price = parseFloat(cleaned)
    console.log("PriceSpy: price found:", price)
    if (price > 0) return price
  }
  return null
}

function getTitleFromPage() {
  const el = document.getElementById("productTitle")
  return el ? el.innerText.trim().slice(0, 80) : "Unknown Product"
}

function createWidget(data) {
  console.log("PriceSpy: creating widget:", data)
  const existing = document.getElementById("pricespy-widget")
  if (existing) existing.remove()

  const color = data.recommendation === "WAIT" ? "#16a34a" : "#dc2626"
  const arrow = data.recommendation === "WAIT" ? "↓" : "↑"

  const widget = document.createElement("div")
  widget.id = "pricespy-widget"
  widget.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 280px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    z-index: 99999;
    font-family: -apple-system, sans-serif;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12);
  `

  widget.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <span style="font-weight:600;font-size:15px">PriceSpy AI</span>
      <button onclick="this.parentElement.parentElement.remove()"
        style="background:none;border:none;cursor:pointer;font-size:18px;color:#9ca3af">x</button>
    </div>
    <div style="font-size:24px;font-weight:700;color:${color};margin-bottom:4px">
      ${arrow} ${data.recommendation}
    </div>
    <div style="font-size:13px;color:#6b7280;margin-bottom:12px">${data.reason}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
      <div style="background:#f9fafb;padding:8px;border-radius:8px;text-align:center">
        <div style="font-size:11px;color:#9ca3af">Current</div>
        <div style="font-size:15px;font-weight:600">Rs.${data.current_price}</div>
      </div>
      <div style="background:#f9fafb;padding:8px;border-radius:8px;text-align:center">
        <div style="font-size:11px;color:#9ca3af">In 14 days</div>
        <div style="font-size:15px;font-weight:600;color:${color}">
          Rs.${data.predicted_price}
        </div>
      </div>
    </div>
    <div style="background:#f0fdf4;padding:8px;border-radius:8px;margin-bottom:12px">
      <div style="font-size:12px;color:#16a34a">
        30-day low: Rs.${data.best_price_30d}
      </div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
      <span style="font-size:12px;color:#9ca3af">Confidence: ${data.confidence}%</span>
      <span style="font-size:12px;color:#9ca3af">${data.days_tracked} days tracked</span>
    </div>
  `

  const tag = "sagarteja30-21"
  const cleanUrl = window.location.href.split("?")[0]
  const affiliateUrl = cleanUrl + "?tag=" + tag
  const btn = document.createElement("a")
  btn.href = affiliateUrl
  btn.target = "_blank"
  btn.style.cssText = `
    display:block;
    margin-top:12px;
    background:#ff9900;
    color:white;
    text-align:center;
    padding:10px;
    border-radius:8px;
    text-decoration:none;
    font-weight:600;
    font-size:14px;
  `
  btn.textContent = "Buy now via PriceSpy"
  widget.appendChild(btn)
  document.body.appendChild(widget)
  console.log("PriceSpy: widget added to page")
}

function keepWidgetAlive() {
  const existing = document.getElementById("pricespy-widget")
  if (!existing && window._priceSpyData) {
    createWidget(window._priceSpyData)
  }
}

async function analyzePage() {
  console.log("PriceSpy: analyzePage called")
  if (!isProductPage()) return

  const price = getPriceFromPage()
  const title = getTitleFromPage()

  if (!price) {
    console.log("PriceSpy: no price found, stopping")
    return
  }

  try {
    console.log("PriceSpy: calling API...")
    const res = await fetch(API_URL + "/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: window.location.href,
        price: price,
        title: title,
        user_id: USER_ID
      })
    })
    console.log("PriceSpy: status:", res.status)
    const data = await res.json()
    console.log("PriceSpy: data:", data)

    window._priceSpyData = data
    createWidget(data)
    setInterval(keepWidgetAlive, 1000)

  } catch (err) {
    console.log("PriceSpy: ERROR:", err)
  }
}

setTimeout(analyzePage, 2000)
setTimeout(analyzePage, 5000)