
function onCaptchaVerified(token) {
  captchaToken = token;
  console.log("Captcha verified:", token);
}

function resetCaptcha() {
  if (typeof grecaptcha !== "undefined") {
    grecaptcha.reset();
    captchaToken = null;
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
