const form = document.querySelector('#subscribe-form');
const message = document.querySelector('#form-message');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = form.querySelector('button');
  button.disabled = true;
  message.textContent = 'Submitting…';
  message.className = 'message';
  try {
    const response = await fetch('/email-updates/subscriptions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: form.elements.email.value }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    message.textContent = data.message || 'Check your inbox for a confirmation link to finish subscribing.';
    message.classList.add('success');
    form.reset();
  } catch (error) {
    message.textContent = error.message || 'Could not save your subscription. Please try again.';
    message.classList.add('error');
  } finally {
    button.disabled = false;
  }
});
