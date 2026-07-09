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
