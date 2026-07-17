/**
 * auth.js
 * Client-side validation and interactive UX for Auth pages (Login, Register, Change Password)
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Password Visibility Toggle ──────────────────────────────────────────
    const setupPasswordToggles = () => {
        const toggleButtons = document.querySelectorAll('.password-toggle');
        toggleButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const input = button.parentElement.querySelector('input');
                if (input) {
                    if (input.type === 'password') {
                        input.type = 'text';
                        button.innerHTML = '<i class="far fa-eye-slash"></i>';
                    } else {
                        input.type = 'password';
                        button.innerHTML = '<i class="far fa-eye"></i>';
                    }
                }
            });
        });
    };

    // ── Dynamic Form Field Validations ──────────────────────────────────────
    const registerForm = document.querySelector('form[action*="register"]');
    const loginForm = document.querySelector('form[action*="login"]');
    const changePasswordForm = document.querySelector('form[action*="change-password"]');

    // Create an alert display helper
    const showAlert = (form, message, type = 'error') => {
        // Remove existing alerts first
        const existingAlerts = form.querySelectorAll('.alert');
        existingAlerts.forEach(a => a.remove());

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} mb-3 fade-in`;
        alertDiv.style.animation = 'slideDown 0.3s ease-out forwards';
        alertDiv.innerHTML = message;
        form.insertBefore(alertDiv, form.firstChild);

        // Auto scroll to top of form if needed
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    // ── Email Regex ─────────────────────────────────────────────────────────
    const isValidEmail = (email) => {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    };

    // ── Password Complexity ──────────────────────────────────────────────────
    const checkPasswordStrength = (password) => {
        const rules = {
            length: password.length >= 8,
            lowercase: /[a-z]/.test(password),
            uppercase: /[A-Z]/.test(password),
            number: /\d/.test(password)
        };

        const score = Object.values(rules).filter(Boolean).length;
        return { rules, score };
    };

    // ── Register Form Validation ─────────────────────────────────────────────
    if (registerForm) {
        const firstNameInput = registerForm.querySelector('input[name="first_name"]');
        const lastNameInput = registerForm.querySelector('input[name="last_name"]');
        const emailInput = registerForm.querySelector('input[name="email"]');
        const passwordInput = registerForm.querySelector('input[name="password"]');
        const confirmPasswordInput = registerForm.querySelector('input[name="confirm_password"]');
        const phoneInput = registerForm.querySelector('input[name="phone"]');

        // Create password feedback element dynamically
        if (passwordInput) {
            const feedbackContainer = document.createElement('div');
            feedbackContainer.className = 'password-strength-feedback mt-2 text-left';
            feedbackContainer.style.fontSize = '0.8rem';
            feedbackContainer.style.color = '#64748b';
            feedbackContainer.innerHTML = `
                <div class="strength-bar-container" style="height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; margin-bottom: 8px;">
                    <div class="strength-bar" style="width: 0%; height: 100%; transition: all 0.3s ease; background: #ef4444;"></div>
                </div>
                <div class="strength-text font-weight-500 mb-1">Password Strength</div>
                <ul style="list-style: none; padding-left: 0; margin-bottom: 0;">
                    <li class="rule-len"><i class="far fa-circle mr-1"></i> Min 8 characters</li>
                    <li class="rule-upper"><i class="far fa-circle mr-1"></i> At least one uppercase letter</li>
                    <li class="rule-lower"><i class="far fa-circle mr-1"></i> At least one lowercase letter</li>
                    <li class="rule-num"><i class="far fa-circle mr-1"></i> At least one number</li>
                </ul>
            `;
            passwordInput.parentElement.parentElement.appendChild(feedbackContainer);

            const strengthBar = feedbackContainer.querySelector('.strength-bar');
            const strengthText = feedbackContainer.querySelector('.strength-text');
            const ruleLen = feedbackContainer.querySelector('.rule-len');
            const ruleUpper = feedbackContainer.querySelector('.rule-upper');
            const ruleLower = feedbackContainer.querySelector('.rule-lower');
            const ruleNum = feedbackContainer.querySelector('.rule-num');

            passwordInput.addEventListener('input', (e) => {
                const val = e.target.value;
                if (!val) {
                    strengthBar.style.width = '0%';
                    strengthText.textContent = 'Password Strength';
                    strengthText.style.color = '#64748b';
                    return;
                }

                const { rules, score } = checkPasswordStrength(val);
                
                // Update checks UI
                const updateRule = (element, met) => {
                    if (met) {
                        element.style.color = '#10b981';
                        element.querySelector('i').className = 'fas fa-check-circle mr-1';
                    } else {
                        element.style.color = '#64748b';
                        element.querySelector('i').className = 'far fa-circle mr-1';
                    }
                };

                updateRule(ruleLen, rules.length);
                updateRule(ruleUpper, rules.uppercase);
                updateRule(ruleLower, rules.lowercase);
                updateRule(ruleNum, rules.number);

                // Update bar colors
                const percentages = ['0%', '25%', '50%', '75%', '100%'];
                const colors = ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#10b981'];
                const labels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Excellent'];

                strengthBar.style.width = percentages[score];
                strengthBar.style.background = colors[score];
                strengthText.textContent = `Password Strength: ${labels[score]}`;
                strengthText.style.color = colors[score];
            });
        }

        registerForm.addEventListener('submit', (e) => {
            const firstName = firstNameInput.value.trim();
            const lastName = lastNameInput.value.trim();
            const email = emailInput.value.trim();
            const password = passwordInput.value;
            const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : '';
            const phone = phoneInput ? phoneInput.value.trim() : '';

            // Basic checks
            if (!firstName || !lastName || !email || !password || !confirmPassword) {
                e.preventDefault();
                showAlert(registerForm, 'Please fill in all required fields.');
                return;
            }

            if (password !== confirmPassword) {
                e.preventDefault();
                showAlert(registerForm, 'Passwords do not match.');
                return;
            }

            if (!isValidEmail(email)) {
                e.preventDefault();
                showAlert(registerForm, 'Please enter a valid email address.');
                return;
            }

            const { score } = checkPasswordStrength(password);
            if (score < 4) {
                e.preventDefault();
                showAlert(registerForm, 'Please meet all password requirements before submitting.');
                return;
            }

            if (phone && !/^\+?[0-9\s\-()]{7,20}$/.test(phone)) {
                e.preventDefault();
                showAlert(registerForm, 'Please enter a valid phone number.');
                return;
            }
        });
    }

    // ── Login Form Validation ────────────────────────────────────────────────
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            const email = loginForm.querySelector('input[name="email"]').value.trim();
            const password = loginForm.querySelector('input[name="password"]').value;

            if (!email || !password) {
                e.preventDefault();
                showAlert(loginForm, 'Please enter both your email and password.');
                return;
            }

            if (!isValidEmail(email)) {
                e.preventDefault();
                showAlert(loginForm, 'Please enter a valid email address.');
                return;
            }
        });
    }

    // ── Change Password Validation ───────────────────────────────────────────
    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', (e) => {
            const currentPw = changePasswordForm.querySelector('input[name="current_password"]').value;
            const newPw = changePasswordForm.querySelector('input[name="new_password"]').value;
            const confirmPw = changePasswordForm.querySelector('input[name="confirm_password"]').value;

            if (!currentPw || !newPw || !confirmPw) {
                e.preventDefault();
                showAlert(changePasswordForm, 'All fields are required.');
                return;
            }

            if (newPw !== confirmPw) {
                e.preventDefault();
                showAlert(changePasswordForm, 'New passwords do not match.');
                return;
            }

            const { score } = checkPasswordStrength(newPw);
            if (score < 4) {
                e.preventDefault();
                showAlert(changePasswordForm, 'New password is not strong enough. Ensure it has at least 8 characters, an uppercase letter, a lowercase letter, and a number.');
                return;
            }
        });
    }

    // Initialize password visibility switches
    setupPasswordToggles();
});
