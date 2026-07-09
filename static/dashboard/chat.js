function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function scrollMessagesToBottom() {
  const messages = document.querySelector("#messages");
  if (messages) {
    messages.scrollTop = messages.scrollHeight;
  }
}

function appendOptimisticMessage(content) {
  const messages = document.querySelector("#messages");
  if (!messages || !content.trim()) {
    return;
  }

  const emptyState = messages.querySelector(".empty-state");
  if (emptyState) {
    emptyState.remove();
  }

  messages.insertAdjacentHTML(
    "beforeend",
    `
        <article class="message user optimistic">
            <div class="message-role">user</div>
            <div class="message-bubble"><p>${escapeHtml(content).replace(/\n/g, "<br>")}</p></div>
        </article>
        <article class="message assistant pending">
            <div class="message-role">assistant</div>
            <div class="message-bubble"><p>Thinking...</p></div>
        </article>
        `,
  );
  scrollMessagesToBottom();
}

document.addEventListener("DOMContentLoaded", () => {
  scrollMessagesToBottom();

  document.querySelectorAll(".flash").forEach((flash) => {
    window.setTimeout(() => {
      flash.remove();
    }, 5000);
  });

  document.querySelectorAll("[data-chat-composer]").forEach((form) => {
    const textarea = form.querySelector('textarea[name="content"]');
    if (!textarea) {
      return;
    }

    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (textarea.value.trim()) {
          form.requestSubmit();
        }
      }
    });
  });

  document.querySelectorAll("[data-upload-form]").forEach((form) => {
    const input = form.querySelector("[data-file-input]");
    const fileName = form.querySelector("[data-file-name]");
    const status = form.querySelector("[data-file-status]");
    const button = form.querySelector("[data-upload-button]");

    const updateUploadState = () => {
      if (input.files.length > 0) {
        fileName.textContent = input.files[0].name;
        fileName.hidden = false;
        status.textContent = "Upload selected file";
        status.classList.add("ready");
        button.disabled = false;
      } else {
        fileName.textContent = "";
        fileName.hidden = true;
        status.textContent = "No file chosen";
        status.classList.remove("ready");
        button.disabled = true;
      }
    };

    input.addEventListener("change", updateUploadState);
    updateUploadState();
  });

  document.querySelectorAll("[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"]');
      if (!button || button.disabled) {
        return;
      }

      const label = button.dataset.loadingLabel || "Loading...";
      button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.classList.add("is-loading");
      button.innerHTML = `<span class="button-spinner" aria-hidden="true"></span><span>${escapeHtml(label)}</span>`;
    });
  });
});

document.body.addEventListener("htmx:configRequest", (event) => {
  const form = event.detail.elt.closest("[data-chat-composer]");
  if (!form) {
    return;
  }

  const textarea = form.querySelector('textarea[name="content"]');
  if (!textarea) {
    return;
  }

  const content = textarea.value;
  appendOptimisticMessage(content);
  textarea.value = "";
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target && event.detail.target.id === "messages") {
    scrollMessagesToBottom();
  }
});
