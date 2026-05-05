document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const confirmMessage = form.dataset.confirm;
            if (confirmMessage && !window.confirm(confirmMessage)) {
                event.preventDefault();
                return;
            }

            const button = form.querySelector("button[type='submit']");
            if (!button || button.dataset.noDisable === "true") {
                return;
            }

            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Working...";

            window.setTimeout(() => {
                button.disabled = false;
                button.textContent = originalText;
            }, 4000);
        });
    });
});
