(function () {
  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function formatLocal(date) {
    return (
      pad(date.getDate()) +
      "/" +
      pad(date.getMonth() + 1) +
      "/" +
      date.getFullYear() +
      " - " +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }

  function applyLocalTimes(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("[data-local-datetime]").forEach(function (node) {
      const iso = node.getAttribute("datetime");
      if (!iso) return;
      const date = new Date(iso);
      if (isNaN(date.getTime())) return;
      node.textContent = formatLocal(date);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyLocalTimes(document);
  });

  document.body.addEventListener("htmx:afterSettle", function (event) {
    applyLocalTimes(event.target);
  });
})();
