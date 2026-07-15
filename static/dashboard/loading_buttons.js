(() => {
  const escapeHtml = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");

  const setLoading = (button, label = "Loading...") => {
    if (!button || button.dataset.loadingActive === "true") {
      return;
    }

    button.dataset.originalHtml = button.innerHTML;
    button.dataset.loadingActive = "true";
    button.disabled = true;
    button.classList.add("is-loading");
    button.setAttribute("aria-busy", "true");
    button.innerHTML = `<span class="button-spinner" aria-hidden="true"></span><span>${escapeHtml(label)}</span>`;
  };

  const restore = (button) => {
    if (!button || button.dataset.loadingActive !== "true") {
      return;
    }

    button.innerHTML = button.dataset.originalHtml || button.textContent;
    delete button.dataset.originalHtml;
    delete button.dataset.loadingActive;
    button.disabled = false;
    button.classList.remove("is-loading");
    button.removeAttribute("aria-busy");
  };

  const initializeLoadingForms = () => {
    document.addEventListener("submit", (event) => {
      const form = event.target.closest("[data-loading-form]");
      if (!form || !form.checkValidity()) {
        return;
      }

      if (form.dataset.confirmMessage && !window.confirm(form.dataset.confirmMessage)) {
        event.preventDefault();
        return;
      }

      const submitter =
        event.submitter ||
        form.querySelector('button[type="submit"], input[type="submit"]');
      if (!submitter || submitter.disabled) {
        return;
      }

      setLoading(submitter, submitter.dataset.loadingLabel || "Loading...");
    });
  };

  window.DashboardLoadingButtons = {
    setLoading,
    restore,
  };

  document.addEventListener("DOMContentLoaded", initializeLoadingForms);
})();
