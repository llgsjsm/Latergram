
      function onCaptchaVerified(token) {
        captchaToken = token;
        console.log("Captcha verified:", token);
      }

      function resetCaptcha() {
        if (captchaWidgetId !== null) {
          grecaptcha.reset(captchaWidgetId);
        }
      }
      function resetCaptchaOnError() {
        if (typeof grecaptcha !== "undefined" && captchaWidgetId !== null) {
          grecaptcha.reset(captchaWidgetId);
          captchaToken = null;
        }
      }
      function hideApprovedCaptcha() {
        const captchaContainer = document.getElementById("captcha-container");
        if (captchaContainer) {
          captchaContainer.classList.add("d-none");
        }
      }

function showCaptcha() {
  const container = document.getElementById("captcha-container");
  if (container) {
    container.classList.remove("d-none"); // show it
    if (typeof grecaptcha !== 'undefined') {
      // Render only if not already rendered
      if (!window.captchaWidgetId) {
        window.captchaWidgetId = grecaptcha.render('g-recaptcha', {
          sitekey: '6LdiSG8rAAAAAJKJYfIl48jO3lg',
          callback: onCaptchaVerified,
        });
      }
    }
  }
}