// Verify OTP
document.getElementById("verify-otp-btn").addEventListener("click", function () {
    const otpCode = document.getElementById("otp-code").value;
    const email = document.getElementById("otp-email").value;
    const otpType = document.getElementById("otp-type").value;

    // !!! Validate backend 
    // if (!otpCode || otpCode.length !== 6) {
    //   showMessage("Please enter a valid 6-digit code", "error");
    //   return;
    // }

    if (otpType === "login") {
        // Try user login OTP verification first
        fetch("/verify-login-otp", {
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
                window.location.href = "/home";
            } else {
                // If user verification fails, try moderator verification
                fetch("/verify-moderator-login-otp", {
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
                        window.location.href = "/moderation";
                    } else {
                        showMessage("Invalid or expired OTP", "error");
                    }
                })
                .catch((error) => {
                    showMessage("An error occurred", "error");
                });
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    } else if (otpType === "moderator_password_reset") {
        // Moderator password reset OTP verification
        fetch("/verify-moderator-reset-otp", {
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
    } else {
        // User password reset OTP verification
        fetch("/verify-reset-otp", {
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
                showMessage(
                "Code verified. Enter your new password",
                "success"
                );
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
    if (otpType === "login") {
        // For login OTP, try user first, then moderator
        fetch("/resend-login-otp", {
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
            } else {
                // Try moderator resend
                fetch("/resend-moderator-login-otp", {
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
                    } else {
                        showMessage("Unable to resend OTP", "error");
                    }
                })
                .catch((error) => {
                    showMessage("An error occurred", "error");
                });
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    } else if (otpType === "moderator_password_reset") {
        fetch("/moderator-forgot-password", {
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
            } else {
                showMessage(data.error, "error");
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    } else {
        // User password reset
        fetch("/forgot-password", {
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
            } else {
                showMessage(data.error, "error");
            }
        })
        .catch((error) => {
            showMessage("An error occurred", "error");
        });
    }
});