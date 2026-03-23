document.addEventListener('DOMContentLoaded', function () {

  // Language toggle
  var toggle = document.getElementById('lang-toggle');
  toggle.addEventListener('click', function (e) {
    e.preventDefault();
    var body = document.body;
    if (body.classList.contains('lang-en')) {
      body.classList.replace('lang-en', 'lang-ko');
      toggle.textContent = 'English';
    } else {
      body.classList.replace('lang-ko', 'lang-en');
      toggle.textContent = '한국어';
    }
  });

  // Contact form
  var form = document.getElementById('contact-form');
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var status = document.getElementById('form-status');

    if (form.elements['honeypot'].value) return; // spam, silent ignore

    var apiUrl = form.getAttribute('data-api');
    if (!apiUrl) {
      status.textContent = 'Message sent! (demo mode)';
      return;
    }

    var payload = {
      name: form.elements['name'].value,
      email: form.elements['email'].value,
      message: form.elements['message'].value
    };

    fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) { status.textContent = r.ok ? 'Message sent!' : 'Error — please try again.'; })
      .catch(function () { status.textContent = 'Error — please try again.'; });
  });

});
