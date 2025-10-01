document.addEventListener('DOMContentLoaded', function() {
    const dlg = document.getElementById('contactDialog');
    const openBtn = document.getElementById('openDialog');
    const closeBtn = document.getElementById('closeDialog');
    const form = document.getElementById('contactForm');
    let lastActive = null;


    function resetValidation() {
        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            field.setCustomValidity('');
            field.setAttribute('aria-invalid', 'false');
            field.style.borderColor = '';
        });
    }

    function validateField(field) {
        field.setCustomValidity('');
        field.setAttribute('aria-invalid', 'false');
        field.style.borderColor = '';

        if (!field.willValidate) return true;

        if (!field.required && !field.value.trim()) {
            return true;
        }

        let isValid = true;
        let message = '';

        if (field.validity.valueMissing) {
            message = getRequiredMessage(field);
            isValid = false;
        } else if (field.validity.typeMismatch) {
            message = getTypeMismatchMessage(field);
            isValid = false;
        } else if (field.validity.tooShort) {
            message = getTooShortMessage(field);
            isValid = false;
        } else if (field.validity.patternMismatch) {
            message = getPatternMismatchMessage(field);
            isValid = false;
        }

        if (!isValid) {
            field.setCustomValidity(message);
            field.setAttribute('aria-invalid', 'true');
            field.style.borderColor = 'var(--color-danger)';
        } else {
            field.style.borderColor = 'var(--color-accent)';
        }

        return isValid;
    }

    function getRequiredMessage(field) {
        const messages = {
            name: 'Пожалуйста, введите ваше имя',
            email: 'Пожалуйста, введите email адрес',
            phone: 'Пожалуйста, введите номер телефона',
            topic: 'Пожалуйста, выберите тему обращения',
            message: 'Пожалуйста, введите ваше сообщение'
        };
        return messages[field.name] || 'Это поле обязательно для заполнения';
    }

    function getTypeMismatchMessage(field) {
        if (field.type === 'email') {
            return 'Пожалуйста, введите корректный email адрес (например: name@example.com)';
        }
        return 'Неверный формат данных';
    }

    function getTooShortMessage(field) {
        if (field.name === 'name') {
            return 'Имя должно содержать минимум 2 символа';
        }
        return `Минимальная длина: ${field.minLength} символов`;
    }

    function getPatternMismatchMessage(field) {
        if (field.name === 'phone') {
            return 'Пожалуйста, введите телефон в формате: +7 (900) 000-00-00';
        }
        return 'Неверный формат данных';
    }

    openBtn?.addEventListener('click', () => {
        lastActive = document.activeElement;
        resetValidation();
        dlg.showModal();
        
        dlg.style.position = 'fixed';
        dlg.style.top = '50%';
        dlg.style.left = '50%';
        dlg.style.transform = 'translate(-50%, -50%)';
        dlg.style.margin = '0';
        
        
        setTimeout(() => {
            const firstField = dlg.querySelector('input, select, textarea');
            if (firstField) {
                firstField.focus();
            }
        }, 100);
    });

    closeBtn?.addEventListener('click', () => {
        dlg.close('cancel');
        resetValidation();
    });

    dlg?.addEventListener('click', (e) => {
        if (e.target === dlg) {
            dlg.close('cancel');
            resetValidation();
        }
    });

    form?.addEventListener('input', function(e) {
        const field = e.target;
        validateField(field);
    });

    form?.addEventListener('blur', function(e) {
        const field = e.target;
        if (field.willValidate) {
            validateField(field);
        }
    }, true);

    form?.addEventListener('submit', (e) => {
        e.preventDefault();
        
        resetValidation();

        const fields = form.querySelectorAll('input, select, textarea');
        let isValid = true;
        let firstInvalidField = null;

        fields.forEach(field => {
            if (field.willValidate && !validateField(field)) {
                isValid = false;
                if (!firstInvalidField) {
                    firstInvalidField = field;
                }
            }
        });

        if (!isValid) {
            if (firstInvalidField) {
                firstInvalidField.focus();
            }
    
            form.reportValidity();
            return;
        }

 
        showSuccessMessage();
    });

    function showSuccessMessage() {
        const successMsg = document.createElement('div');
        successMsg.className = 'success-message';
        successMsg.innerHTML = `
            <div style="text-align: center; padding: var(--space-4);">
                <div style="font-size: 3rem; margin-bottom: var(--space-3);">✅</div>
                <h3 style="margin: 0 0 var(--space-2) 0; color: var(--color-accent);">Сообщение отправлено!</h3>
                <p style="margin: 0; color: var(--color-fg-alt);">Спасибо за ваше обращение. Мы свяжемся с вами в ближайшее время.</p>
            </div>
        `;
        successMsg.setAttribute('role', 'alert');
        successMsg.setAttribute('aria-live', 'polite');
        
        const formElement = form;
        formElement.style.display = 'none';
        
        const dialogContent = dlg.querySelector('.dialog-content');
        const existingSuccess = dialogContent.querySelector('.success-message');
        if (existingSuccess) {
            existingSuccess.remove();
        }
        dialogContent.appendChild(successMsg);
        
        setTimeout(() => {
            formElement.reset();
            formElement.style.display = 'block';
            successMsg.remove();
            dlg.close('success');
            resetValidation();

            if (lastActive) {
                lastActive.focus();
            }
        }, 3000);
    }

    const phone = document.getElementById('phone');
    phone?.addEventListener('input', function() {
        let value = this.value.replace(/\D/g, '');
        
        if (value.startsWith('7') || value.startsWith('8')) {
            value = value.substring(1);
        }
        
        if (value.length > 0) {
            let formattedValue = '+7 (';
            
            if (value.length > 0) {
                formattedValue += value.substring(0, 3);
            }
            if (value.length >= 4) {
                formattedValue += ') ' + value.substring(3, 6);
            }
            if (value.length >= 7) {
                formattedValue += '-' + value.substring(6, 8);
            }
            if (value.length >= 9) {
                formattedValue += '-' + value.substring(8, 10);
            }
            
            this.value = formattedValue;
        }
        
        validateField(this);
    });

    const email = document.getElementById('email');
    email?.addEventListener('blur', function() {
        if (this.value.trim()) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(this.value)) {
                this.setCustomValidity('Пожалуйста, введите корректный email адрес');
                this.setAttribute('aria-invalid', 'true');
                this.style.borderColor = 'var(--color-danger)';
            } else {
                this.setCustomValidity('');
                this.setAttribute('aria-invalid', 'false');
                this.style.borderColor = 'var(--color-accent)';
            }
        }
    });

    const name = document.getElementById('name');
    name?.addEventListener('blur', function() {
        if (this.value.trim() && this.value.trim().length < 2) {
            this.setCustomValidity('Имя должно содержать минимум 2 символа');
            this.setAttribute('aria-invalid', 'true');
            this.style.borderColor = 'var(--color-danger)';
        } else if (this.value.trim()) {
            this.setCustomValidity('');
            this.setAttribute('aria-invalid', 'false');
            this.style.borderColor = 'var(--color-accent)';
        }
    });

    dlg?.addEventListener('close', () => {
        lastActive?.focus();
    });

    dlg?.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            dlg.close('cancel');
            resetValidation();
        }
    });
});