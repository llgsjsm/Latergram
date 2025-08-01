// Verify OTP
document.getElementById("verify-otp-btn").addEventListener("click", function () {
    const otpCode = document.getElementById("otp-code").value;
    const email = document.getElementById("otp-email").value;
    const otpType = document.getElementById("otp-type").value;

    if (otpType === "password_reset") {
        // Moderator password reset OTP verification
        csrfFetch("/verify-reset-otp", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email: email,
                otp_code: otpCode,
            }),
        })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                showSection("reset-password");
                showMessage("Code verified. Enter your new password",
                "success"
                );
            } else {
                showMessage(data.error, "error");
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    } else if (otpType === "register") {
        // Registration OTP verification
        csrfFetch("/verify-register-otp", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email: email,
                otp_code: otpCode,
            }),
        })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                window.location.href = data.redirect;
            } else {
                // false
                showMessage(data.error, "error", "otp-container");
                if (!data.error.includes("OTP")) {
                    setTimeout(() => {
                        window.location.href = "/register";
                    }, 4000); // 4 Secs
                }

                
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    } else {
        // Try user login OTP verification first
        csrfFetch("/verify-login-otp", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email: email,
                otp_code: otpCode,
            }),
        })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                window.location.href = data.redirect;
            } else {
                showMessage(data.error, "error");
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    }

});

// Resend OTP
document.getElementById("resend-otp").addEventListener("click", function (e) {
    e.preventDefault();
    const email = document.getElementById("otp-email").value;
    const otpType = document.getElementById("otp-type").value;

    if (otpType === "password_reset") {
        csrfFetch("/forgot-password", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email: email,
            }),
        })
        
        .then((response) => response.json())
        .then((data) => {
            if (data.success) 
            {
                document.getElementById("otp-email").value = email;
                showMessage("An OTP has been sent.", "success");
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    } else {
        csrfFetch("/resend-login-otp", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email: email,
            }),
        })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                showMessage("New code sent to your email", "success");
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    }

});