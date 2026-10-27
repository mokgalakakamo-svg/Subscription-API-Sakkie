const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

function formatPrice(plan) {
  const amount = (plan.amount_minor ?? 0) / 100;
  if (!amount) return '<span class="price-amount">Free</span>';
  const formatted = new Intl.NumberFormat('en-ZA', { style: 'currency', currency: plan.currency || 'ZAR', maximumFractionDigits: 0 }).format(amount);
  return `<span class="price-amount">${escapeHtml(formatted.replace(/\s/g, ''))}</span><span class="price-period">/ ${escapeHtml(plan.billing_interval || 'month')}</span>`;
}

async function loadPlans() {
  const grid = $('#plan-grid');
  try {
    const response = await fetch('/plans');
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    const plans = data.plans || [];
    if (!plans.length) {
      grid.innerHTML = '<div class="loading-card">No plans are available right now.</div>';
      return;
    }
    grid.innerHTML = plans.map((plan, index) => {
      const featured = plan.code === 'professional' || (index === 1 && !plans.some((item) => item.code === 'professional'));
      return `<article class="plan-card${featured ? ' featured' : ''}">${featured ? '<span class="popular-tag">MOST POPULAR</span>' : ''}<h3 class="plan-name">${escapeHtml(plan.name)}</h3><p class="plan-desc">${escapeHtml(plan.description)}</p><div class="plan-price">${formatPrice(plan)}</div></article>`;
    }).join('');
  } catch (error) {
    grid.innerHTML = `<div class="loading-card">Could not load plans. ${escapeHtml(error.message)}</div>`;
  }
}

loadPlans();
