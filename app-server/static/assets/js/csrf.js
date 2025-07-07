async function csrfFetch(url, options = {}) {
  const res = await fetch('/get-csrf-token');
  const token = (await res.json()).csrf_token;

  options.headers = {
    ...options.headers,
    'Content-Type': 'application/json',
    'X-CSRFToken': token,
  };

  return fetch(url, options);
}