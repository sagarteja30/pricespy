const API_URL = "http://127.0.0.1:8000"

function isProductPage() {
  return (
    window.location.href.includes("/dp/") ||
    window.location.href.includes("flipkart.com/p/")
  )
}

function createWidget(data) {
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

    <div style="display:flex;align-items:center;justify-content:space-between">
      <span style="font-size:12px;color:#9ca3af">Confidence: ${data.confidence}%</span>
      <span style="font-size:12px;color:#9ca3af">${data.days_tracked} days tracked</span>
    </div>
  `

  document.body.appendChild(widget)
}

async function analyzePage() {
  if (!isProductPage()) return

  try {
    const res = await fetch(API_URL + "/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: window.location.href })
    })
    const data = await res.json()
    if (!data.error) createWidget(data)
  } catch (err) {
    console.log("PriceSpy error:", err)
  }
}

setTimeout(analyzePage, 2000)

