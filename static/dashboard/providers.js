(() => {
  const providerScrollStorageKey = "dashboard:providers:scrollTop";

  const providerDefaults = {
    ollama: {
      baseUrl: "http://ollama.ai-platform.internal:11434",
      chatModels: ["gemma2:2b", "llama3.2:3b", "mistral:7b", "qwen2.5:7b"],
      embeddingModels: ["nomic-embed-text"],
    },
    gemini: {
      baseUrl: "https://generativelanguage.googleapis.com/v1beta",
      chatModels: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
      embeddingModels: ["text-embedding-004"],
    },
    openrouter: {
      baseUrl: "https://openrouter.ai/api/v1",
      chatModels: [
        "openai/gpt-4o-mini",
        "google/gemini-flash-1.5",
        "anthropic/claude-3.5-haiku",
        "meta-llama/llama-3.1-8b-instruct",
      ],
      embeddingModels: ["openai/text-embedding-3-small"],
    },
    groq: {
      baseUrl: "https://api.groq.com/openai/v1",
      chatModels: [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
      ],
      embeddingModels: [],
    },
  };

  const replaceSuggestions = (input, models) => {
    if (!input?.list) {
      return;
    }

    input.list.innerHTML = "";

    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      input.list.append(option);
    });
  };

  const initializeProviderForm = (form) => {
    const kind = form.dataset.providerForm;
    const providerSelect = form.querySelector("[data-provider-select]");
    const modelInput = form.querySelector("[data-model-input]");
    const fallbackInput = form.querySelector("[data-fallback-model-input]");
    const baseUrlInput = form.querySelector("[data-base-url-input]");
    const dimensionsInput = form.querySelector("[data-dimensions-input]");

    if (!providerSelect || !modelInput || !baseUrlInput) {
      return;
    }

    const applyProviderDefaults = (preserveCurrent = false) => {
      const provider = providerSelect.value;
      const defaults = providerDefaults[provider] || providerDefaults.ollama;
      const models =
        kind === "embedding" ? defaults.embeddingModels : defaults.chatModels;

      replaceSuggestions(modelInput, models);
      replaceSuggestions(fallbackInput, defaults.chatModels);

      if (!preserveCurrent) {
        modelInput.value = "";
        if (fallbackInput) {
          fallbackInput.value = "";
        }
      }

      baseUrlInput.value = defaults.baseUrl;

      if (dimensionsInput) {
        dimensionsInput.value = "768";
      }
    };

    applyProviderDefaults(true);
    providerSelect.addEventListener("change", () =>
      applyProviderDefaults(false),
    );
  };

  const selectedProjectFromUrl = (url) => {
    return new URL(url, window.location.href).searchParams.get("project") || "";
  };

  const updateProjectInputs = (projectSlug) => {
    document.querySelectorAll('input[name="project_slug"]').forEach((input) => {
      input.value = projectSlug;
    });
  };

  const initializeProjectTabs = () => {
    const providerConsole = document.querySelector(".provider-console");
    if (!providerConsole) {
      return;
    }

    const replaceEmbeddingTools = async (url, pushState = true) => {
      const scrollTop = providerConsole.scrollTop;
      const response = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) {
        throw new Error("Unable to load provider project.");
      }

      const html = await response.text();
      const parsedDocument = new DOMParser().parseFromString(html, "text/html");
      const nextEmbeddingTools =
        parsedDocument.querySelector(".embedding-tools");
      const currentEmbeddingTools = document.querySelector(".embedding-tools");

      if (!nextEmbeddingTools || !currentEmbeddingTools) {
        throw new Error("Provider project section was not found.");
      }

      currentEmbeddingTools.replaceWith(nextEmbeddingTools);
      updateProjectInputs(selectedProjectFromUrl(url));
      if (pushState) {
        window.history.pushState({}, "", url);
      }
      window.DashboardTabPersistence?.rememberCurrent("/providers/");
      providerConsole.scrollTop = scrollTop;
    };

    providerConsole.addEventListener("click", async (event) => {
      const link = event.target.closest(".embedding-tools .project-tabs a");
      if (!link) {
        return;
      }

      event.preventDefault();

      try {
        await replaceEmbeddingTools(link.href);
      } catch {
        window.location.href = link.href;
      }
    });

    window.addEventListener("popstate", async () => {
      try {
        await replaceEmbeddingTools(window.location.href, false);
      } catch {
        window.location.reload();
      }
    });
  };

  const providerConsole = () => document.querySelector(".provider-console");

  const rememberProviderScroll = () => {
    const consoleElement = providerConsole();
    if (!consoleElement) {
      return;
    }
    sessionStorage.setItem(
      providerScrollStorageKey,
      String(consoleElement.scrollTop),
    );
  };

  const restoreProviderScroll = () => {
    const consoleElement = providerConsole();
    if (!consoleElement) {
      return;
    }

    const storedScroll = sessionStorage.getItem(providerScrollStorageKey);
    if (storedScroll === null) {
      return;
    }

    const nextScrollTop = Number.parseInt(storedScroll, 10);
    if (Number.isNaN(nextScrollTop)) {
      sessionStorage.removeItem(providerScrollStorageKey);
      return;
    }

    requestAnimationFrame(() => {
      consoleElement.scrollTop = nextScrollTop;
      requestAnimationFrame(() => {
        consoleElement.scrollTop = nextScrollTop;
        sessionStorage.removeItem(providerScrollStorageKey);
      });
    });
  };

  const initializeProviderScrollPersistence = () => {
    const consoleElement = providerConsole();
    if (!consoleElement) {
      return;
    }

    if ("scrollRestoration" in window.history) {
      window.history.scrollRestoration = "manual";
    }

    restoreProviderScroll();

    consoleElement.addEventListener(
      "submit",
      () => {
        rememberProviderScroll();
      },
      true,
    );

    document.body.addEventListener("htmx:beforeSwap", (event) => {
      if (event.target?.classList?.contains("embedding-tools")) {
        rememberProviderScroll();
      }
    });

    document.body.addEventListener("htmx:afterSwap", (event) => {
      if (event.target?.classList?.contains("embedding-tools")) {
        restoreProviderScroll();
      }
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    document
      .querySelectorAll("[data-provider-form]")
      .forEach(initializeProviderForm);
    initializeProjectTabs();
    initializeProviderScrollPersistence();
  });
})();
