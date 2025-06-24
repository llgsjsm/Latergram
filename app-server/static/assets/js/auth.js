// Password field toggle
const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("toggle-password");
const toggleIcon = document.getElementById("toggle-icon");

if (togglePassword) {
    togglePassword.addEventListener("click", function () {
        const type = passwordInput.getAttribute("type") === "password" ? "text" : "password";
        passwordInput.setAttribute("type", type);
        toggleIcon.classList.toggle("fa-eye");
        toggleIcon.classList.toggle("fa-eye-slash");
    });
}

// Confirm password field toggle
const confirmPasswordInput = document.getElementById("confirmpassword");
const toggleConfirmPassword = document.getElementById("toggle-confirm-password");
const toggleConfirmIcon = document.getElementById("toggle-confirm-icon");

if (toggleConfirmPassword) {
    toggleConfirmPassword.addEventListener("click", function () {
        const type = confirmPasswordInput.getAttribute("type") === "password" ? "text" : "password";
        confirmPasswordInput.setAttribute("type", type);
        toggleConfirmIcon.classList.toggle("fa-eye");
        toggleConfirmIcon.classList.toggle("fa-eye-slash");
    });
}

// Automatically hide flash messages after 5 seconds
const flashMessages = document.querySelectorAll(".alert");
if (flashMessages) {
    setTimeout(() => {
        flashMessages.forEach(function (message) {
            message.style.display = "none";
        });
    }, 5000); // 5000 milliseconds = 5 seconds
} 