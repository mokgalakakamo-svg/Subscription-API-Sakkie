const button = document.querySelector('#confirm-button');
const message = document.querySelector('#confirm-message');
const token = new URLSearchParams(window.location.search).get('token');

if (!token) {
  button.disabled = true;
  message.textContent = 'This confirmation link is missing its token. Please subscribe again.';
  message.classList.add('error');
}

button.addEventListener('click', async () => {
  button.disabled = true;
  message.textContent = 'Confirming your email…';
  message.className = 'message';
  try {
    const response = await fetch('/email-updates/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    message.textContent = data.message || 'Your email is confirmed and you are subscribed.';
    message.classList.add('success');
    button.hidden = true;
    window.history.replaceState({}, document.title, '/email-updates/confirm');
  } catch (error) {
    message.textContent = error.message || 'Could not confirm your email. Please try again.';
    message.classList.add('error');
    button.disabled = false;
  }
});
