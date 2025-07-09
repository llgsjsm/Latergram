// async function csrfFetch(url, options = {}) {
//   const res = await fetch('/get-csrf-token');
//   const token = (await res.json()).csrf_token;

//   options.headers = {
//     ...options.headers,
//     'Content-Type': 'application/json',
//     'X-CSRFToken': token,
//   };

//   return fetch(url, options);
// }

async function csrfFetch(url, options = {}) {
  const res = await fetch('/get-csrf-token');
  const token = (await res.json()).csrf_token;
  const headers = {'X-CSRF-Token': token, 'X-Requested-With': 'XMLHttpRequest', ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) { if (!headers['Content-Type']) { headers['Content-Type'] = 'application/json';  } }
  return fetch(url, { ...options, headers });
}
