(() => {
  const providerScrollStorageKey = "dashboard:providers:scrollTop";

  const emptyProviderCardValue = (text, placeholder) =>
    text && text !== placeholder ? text : "";

  const readProviderCardData = (kind) => {
    const sections = document.querySelectorAll(".provider-section");
    const section = kind === "embedding" ? sections[1] : sections[0];
    const data = {};
    if (!section) {
      return data;
    }

    section.querySelectorAll(".provider-card").forEach((card) => {
      const name = card.querySelector("h3")?.textContent?.trim();
      if (!name) {
        return;
      }
      data[name] = {
        baseUrl: emptyProviderCardValue(
          card.querySelector("small")?.textContent?.trim(),
          "Base URL not configured",
        ),
        model: emptyProviderCardValue(
          card.querySelector("p")?.textContent?.trim(),
          "No default model saved",
        ),
      };
    });

    return data;
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

    const cardData = readProviderCardData(kind);
    const chatCardData =
      kind === "embedding" ? readProviderCardData("chat") : cardData;

    const applyProviderDefaults = (preserveCurrent = false) => {
      const provider = providerSelect.value;
      const defaults = cardData[provider] || { baseUrl: "", model: "" };
      const fallbackDefaults = chatCardData[provider] || { model: "" };

      replaceSuggestions(modelInput, defaults.model ? [defaults.model] : []);
      replaceSuggestions(
        fallbackInput,
        fallbackDefaults.model ? [fallbackDefaults.model] : [],
      );

      if (!preserveCurrent) {
        modelInput.value = defaults.model || "";
        if (fallbackInput) {
          fallbackInput.value = "";
        }
      }

      baseUrlInput.value = defaults.baseUrl || "";

      if (dimensionsInput) {
        dimensionsInput.value =
          "768 — fixed (the backend only supports this dimension)";
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

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (!event.target?.querySelectorAll) {
      return;
    }
    event.target
      .querySelectorAll("[data-provider-form]")
      .forEach(initializeProviderForm);
  });

  document.addEventListener("DOMContentLoaded", () => {
    document
      .querySelectorAll("[data-provider-form]")
      .forEach(initializeProviderForm);
    initializeProjectTabs();
    initializeProviderScrollPersistence();
  });
})();
