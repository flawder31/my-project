document.addEventListener('DOMContentLoaded', function() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);

    document.querySelectorAll('.card, .gallery-item, .hero h1, .hero p').forEach(el => {
        el.classList.add('fade-in');
        observer.observe(el);
    });

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const target = document.querySelector(targetId);
            if (target) {
                const offsetTop = target.offsetTop - 80;
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    const orderForm = document.getElementById('orderForm');
    const orderModal = document.getElementById('orderModal');

    if (orderForm) {
        orderForm.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();

            if (this.checkValidity()) {
                const modal = bootstrap.Modal.getInstance(orderModal);
                modal.hide();
                this.reset();
                this.classList.remove('was-validated');
                alert('Заявка успешно отправлена! Мы свяжемся с вами в ближайшее время.');
            } else {
                this.classList.add('was-validated');
            }
        });

        orderModal.addEventListener('hidden.bs.modal', function() {
            orderForm.classList.remove('was-validated');
            orderForm.reset();
        });

        orderForm.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('input', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });

            input.addEventListener('blur', function() {
                this.classList.remove('is-valid', 'is-invalid');
            });
        });
    }

    const contactForm = document.getElementById('contactForm');

    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (this.checkValidity()) {
                this.reset();
                alert('Сообщение отправлено! Спасибо за обращение.');
            } else {
                this.reportValidity();
            }
        });
    }
});