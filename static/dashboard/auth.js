document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-password-toggle]");
  if (!toggle) {
    return;
  }

  const field = toggle.closest(".password-field");
  const input = field ? field.querySelector("input") : null;
  if (!input) {
    return;
  }

  const shouldShow = input.type === "password";
  input.type = shouldShow ? "text" : "password";
  toggle.setAttribute(
    "aria-label",
    shouldShow ? "Hide password" : "Show password",
  );
  toggle.setAttribute("aria-pressed", String(shouldShow));
});

(() => {
  const refreshUrl = document.body?.dataset.authRefreshUrl;
  if (!refreshUrl) {
    return;
  }

  const loginUrl = document.body.dataset.authLoginUrl || "/login/";
  const csrfToken = () => {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  };

  const refreshSession = async () => {
    const response = await fetch(refreshUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    if (response.status === 401) {
      window.location.href = loginUrl;
      return null;
    }

    if (!response.ok) {
      return null;
    }

    return response.json();
  };

  const scheduleRefresh = (expiresInSeconds) => {
    const expiresIn = Number.parseInt(expiresInSeconds, 10) || 1800;
    const refreshIn = Math.max(60, expiresIn - 120) * 1000;

    window.setTimeout(async () => {
      const payload = await refreshSession();
      scheduleRefresh(payload?.expires_in || expiresIn);
    }, refreshIn);
  };

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshSession();
    }
  });

  scheduleRefresh(document.body.dataset.authRefreshSeconds);
})();
