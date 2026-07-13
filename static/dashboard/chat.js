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

function isNearMessageBottom() {
  const messages = document.querySelector("#messages");
  if (!messages) {
    return false;
  }
  return messages.scrollHeight - messages.scrollTop - messages.clientHeight < 80;
}

function scrollMessagesIfNearBottom(wasNearBottom) {
  if (wasNearBottom) {
    scrollMessagesToBottom();
  }
}

function removeReadyDocumentProcessActions(root = document) {
  root.querySelectorAll('[data-document-status][data-document-has-text="true"]').forEach((status) => {
    const documentId = status.dataset.documentId;
    if (!documentId) {
      return;
    }

    document
      .querySelectorAll(`[data-document-process-form][data-document-id="${CSS.escape(documentId)}"]`)
      .forEach((form) => form.remove());
  });
}

function appendOptimisticMessage(content, optimisticId) {
  const messages = document.querySelector("#messages");
  if (!messages || !content.trim()) {
    return;
  }

  const emptyState = messages.querySelector(".empty-state");
  const emptyStateHtml = emptyState?.outerHTML || "";
  if (emptyState) {
    emptyState.remove();
  }

  messages.insertAdjacentHTML(
    "beforeend",
    `
        <article class="message user optimistic" data-optimistic-id="${escapeHtml(optimisticId)}">
            <div class="message-role">user</div>
            <div class="message-bubble"><p>${escapeHtml(content).replace(/\n/g, "<br>")}</p></div>
        </article>
        <article class="message assistant pending" data-optimistic-id="${escapeHtml(optimisticId)}">
            <div class="message-role">assistant</div>
            <div class="message-bubble"><p>Thinking...</p></div>
        </article>
        `,
  );
  scrollMessagesToBottom();

  return emptyStateHtml;
}

function removeOptimisticMessage(optimisticId) {
  if (!optimisticId) {
    return;
  }

  document
    .querySelectorAll(`[data-optimistic-id="${CSS.escape(optimisticId)}"]`)
    .forEach((message) => message.remove());
}

function renderMessageProgress(message, events, state) {
  const bubble = message.querySelector(".message-bubble");
  if (!bubble) {
    return;
  }

  if (state.content) {
    bubble.innerHTML = `
      <div class="rich-text streaming">${renderParagraphs(state.content)}</div>
      ${renderMessageActivity(events)}
    `;
    return;
  }

  const rows = events.slice(-4).map((event) => {
    const status = event.event || "started";
    const icon = status.includes("completed") || status === "completed" ? "✓" :
      status.includes("failed") || status === "failed" ? "!" :
      status.includes("started") || status === "started" || status === "queued" ? "●" : "○";
    return `<li class="message-progress-row message-progress-${escapeHtml(status)}"><span>${icon}</span><span>${escapeHtml(event.message || status.replace(/_/g, " "))}</span></li>`;
  }).join("");

  bubble.innerHTML = `
    <div class="message-progress">
      <div class="message-progress-header">
        <strong>${escapeHtml(state.title || "Generating response...")}</strong>
      </div>
      <ul>${rows || "<li><span>●</span><span>Message queued</span></li>"}</ul>
      ${state.error ? `<p class="message-progress-error">${escapeHtml(state.error)}</p>` : ""}
    </div>
  `;
}

function renderParagraphs(content) {
  return (content || "")
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function renderMessageActivity(events) {
  const latest = [...events].reverse().find((event) => event.event !== "token");
  if (!latest || latest.event === "completed") {
    return "";
  }
  return `<div class="message-stream-status">${escapeHtml(latest.message || latest.event.replace(/_/g, " "))}</div>`;
}

function renderMessageFinal(message, state) {
  const bubble = message.querySelector(".message-bubble");
  if (!bubble) {
    return;
  }
  message.classList.remove("pending");
  if (state.error) {
    bubble.innerHTML = `
      <div class="message-progress">
        <strong>Message failed</strong>
        <p class="message-progress-error">${escapeHtml(state.error)}</p>
      </div>
    `;
    return;
  }

  if (state.renderedHtml) {
    bubble.innerHTML = state.renderedHtml;
    return;
  }

  const output = (state.content || "").trim();
  bubble.innerHTML = `
    <div class="rich-text">${renderParagraphs(output)}</div>
    ${renderMessageSources(state.sources)}
  `;
}

function renderMessageSources(sources) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return "";
  }

  return `
    <div class="sources">
      <strong>Sources</strong>
      ${sources.map((source) => `<span>${escapeHtml(source.document_name || "Document")} · ${escapeHtml(String(source.matches || 0))} matches</span>`).join("")}
    </div>
  `;
}

function parseSseFrames(buffer, onEvent) {
  let boundary = buffer.indexOf("\n\n");
  while (boundary !== -1) {
    const frame = buffer.slice(0, boundary);
    buffer = buffer.slice(boundary + 2);
    const lines = frame.split("\n");
    let eventName = "message";
    const dataLines = [];
    lines.forEach((line) => {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    });
    if (dataLines.length) {
      try {
        const payload = JSON.parse(dataLines.join("\n"));
        onEvent({ event: payload.event || eventName, ...payload });
      } catch (error) {
        onEvent({ event: "malformed", message: "Skipped a malformed message event." });
      }
    }
    boundary = buffer.indexOf("\n\n");
  }
  return buffer;
}

async function startMessageStream(form, content) {
  if (form.dataset.messageStreaming === "true") {
    return;
  }

  const optimisticId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  form.dataset.messageStreaming = "true";
  form.dataset.pendingContent = content;
  form.dataset.optimisticId = optimisticId;
  const emptyStateHtml = appendOptimisticMessage(content, optimisticId);
  if (emptyStateHtml) {
    form.dataset.emptyStateHtml = emptyStateHtml;
  }

  const pendingMessage = document.querySelector(`.message.assistant.pending[data-optimistic-id="${CSS.escape(optimisticId)}"]`);
  const state = { title: "Generating response...", content: "", sources: [], error: "" };
  const events = [];
  renderMessageProgress(pendingMessage, events, state);

  const textarea = form.querySelector('textarea[name="content"]');
  const agentName = form.querySelector('select[name="agent_name"]')?.value;
  const button = form.querySelector('button[type="submit"]');
  const stopButton = form.querySelector("[data-message-stop]");
  const abortController = new AbortController();
  if (textarea) {
    textarea.value = "";
  }
  form._messageAbortController = abortController;
  if (stopButton) {
    stopButton.hidden = false;
    stopButton.disabled = false;
  }
  window.DashboardLoadingButtons?.setLoading(button, button?.dataset.loadingLabel || "Sending...");

  const body = new FormData();
  body.append("content", content);
  if (agentName) {
    body.append("agent_name", agentName);
  }
  const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value;

  try {
    let receivedEvent = false;
    const response = await fetch(form.dataset.messageStreamUrl, {
      method: "POST",
      headers: csrf ? { "X-CSRFToken": csrf } : {},
      body,
      signal: abortController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Message stream failed with status ${response.status}.`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let done = false;

    while (!done) {
      const result = await reader.read();
      done = result.done;
      buffer += decoder.decode(result.value || new Uint8Array(), { stream: !done });
      buffer = parseSseFrames(buffer, (event) => {
        if (abortController.signal.aborted) {
          return;
        }
        receivedEvent = true;
        const wasNearBottom = isNearMessageBottom();
        if (event.content) {
          state.content = event.content;
        }
        if (event.delta) {
          state.content += event.delta;
        }
        if (event.sources) {
          state.sources = event.sources;
        }
        if (event.rendered_html) {
          state.renderedHtml = event.rendered_html;
        }
        if (event.error) {
          state.error = event.error;
        }
        events.push(event);
        if (["completed", "failed", "cancelled"].includes(event.event)) {
          if (event.event !== "completed") {
            state.error = state.error || event.message || "Message did not complete.";
          }
          renderMessageFinal(pendingMessage, state);
        } else {
          renderMessageProgress(pendingMessage, events, state);
        }
        scrollMessagesIfNearBottom(wasNearBottom);
      });
    }
  } catch (error) {
    if (abortController.signal.aborted) {
      state.error = "Message generation stopped.";
      renderMessageFinal(pendingMessage, state);
      return;
    }
    if (!events.length) {
      if (textarea) {
        textarea.value = content;
      }
      removeOptimisticMessage(optimisticId);
      HTMLFormElement.prototype.submit.call(form);
      return;
    }
    state.error = error.message || "Message stream disconnected.";
    renderMessageFinal(pendingMessage, state);
  } finally {
    window.DashboardLoadingButtons?.restore(button);
    if (stopButton) {
      stopButton.hidden = true;
      stopButton.disabled = false;
    }
    delete form._messageAbortController;
    delete form.dataset.messageStreaming;
    delete form.dataset.pendingContent;
    delete form.dataset.optimisticId;
    delete form.dataset.emptyStateHtml;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  scrollMessagesToBottom();
  removeReadyDocumentProcessActions();

  document.querySelectorAll(".flash").forEach((flash) => {
    window.setTimeout(() => {
      flash.remove();
    }, 5000);
  });

  document.querySelectorAll("[data-chat-composer]").forEach((form) => {
    const textarea = form.querySelector('textarea[name="content"]');
    const stopButton = form.querySelector("[data-message-stop]");
    if (!textarea) {
      return;
    }

    stopButton?.addEventListener("click", () => {
      if (form.dataset.messageStreaming === "true" && form._messageAbortController) {
        stopButton.disabled = true;
        form._messageAbortController.abort();
      }
    });

    form.addEventListener("submit", (event) => {
      if (!form.dataset.messageStreamUrl) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      const content = textarea.value.trim();
      if (content) {
        startMessageStream(form, content);
      }
    }, true);

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
    const fileList = form.querySelector("[data-file-list]");
    const status = form.querySelector("[data-file-status]");
    const button = form.querySelector("[data-upload-button]");

    const updateUploadState = () => {
      const files = Array.from(input.files);
      if (files.length > 0) {
        fileList.innerHTML = files
          .map((file) => `<li>${escapeHtml(file.name)}</li>`)
          .join("");
        fileList.hidden = false;
        status.textContent = files.length === 1 ? "Upload selected file" : `Upload ${files.length} selected files`;
        status.classList.add("ready");
        button.disabled = false;
      } else {
        fileList.innerHTML = "";
        fileList.hidden = true;
        status.textContent = "No file chosen";
        status.classList.remove("ready");
        button.disabled = true;
      }
    };

    input.addEventListener("change", updateUploadState);
    updateUploadState();
  });

});

document.body.addEventListener("htmx:configRequest", (event) => {
  const form = event.detail.elt.closest("[data-chat-composer]");
  if (!form) {
    return;
  }
  if (form.dataset.messageStreamUrl) {
    return;
  }

  const textarea = form.querySelector('textarea[name="content"]');
  if (!textarea) {
    return;
  }

  const content = textarea.value;
  const optimisticId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  form.dataset.pendingContent = content;
  form.dataset.optimisticId = optimisticId;

  const emptyStateHtml = appendOptimisticMessage(content, optimisticId);
  if (emptyStateHtml) {
    form.dataset.emptyStateHtml = emptyStateHtml;
  } else {
    delete form.dataset.emptyStateHtml;
  }
  textarea.value = "";

  const button = form.querySelector('button[type="submit"]');
  window.DashboardLoadingButtons?.setLoading(button, button?.dataset.loadingLabel || "Sending...");
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target && event.detail.target.id === "messages") {
    scrollMessagesToBottom();
    document
      .querySelectorAll("[data-chat-composer] button[data-loading-active]")
      .forEach((button) => window.DashboardLoadingButtons?.restore(button));

    document.querySelectorAll("[data-chat-composer]").forEach((form) => {
      delete form.dataset.pendingContent;
      delete form.dataset.optimisticId;
      delete form.dataset.emptyStateHtml;
    });
  }

  removeReadyDocumentProcessActions();
});

document.body.addEventListener("htmx:afterRequest", (event) => {
  const form = event.detail.elt.closest("[data-chat-composer]");
  if (!form || event.detail.successful) {
    return;
  }

  const button = form.querySelector("button[data-loading-active]");
  window.DashboardLoadingButtons?.restore(button);

  const textarea = form.querySelector('textarea[name="content"]');
  if (textarea && form.dataset.pendingContent) {
    textarea.value = form.dataset.pendingContent;
    textarea.focus();
  }

  removeOptimisticMessage(form.dataset.optimisticId);
  if (form.dataset.emptyStateHtml) {
    const messages = document.querySelector("#messages");
    messages?.insertAdjacentHTML("beforeend", form.dataset.emptyStateHtml);
  }

  delete form.dataset.pendingContent;
  delete form.dataset.optimisticId;
  delete form.dataset.emptyStateHtml;
});
