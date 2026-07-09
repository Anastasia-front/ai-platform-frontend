(() => {
  const providerDefaults = {
    ollama: {
      baseUrl: "http://localhost:11434",
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
      chatModels: ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
      embeddingModels: [],
    },
  };

  const replaceOptions = (select, models, selectedValue, includeEmpty = false) => {
    if (!select) {
      return;
    }

    const values = includeEmpty ? ["", ...models] : models;
    select.innerHTML = "";

    values.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model || "No fallback";
      select.append(option);
    });

    if (selectedValue && values.includes(selectedValue)) {
      select.value = selectedValue;
    } else {
      select.value = values[0] || "";
    }
  };

  const initializeProviderForm = (form) => {
    const kind = form.dataset.providerForm;
    const providerSelect = form.querySelector("[data-provider-select]");
    const modelSelect = form.querySelector("[data-model-select]");
    const fallbackSelect = form.querySelector("[data-fallback-model-select]");
    const baseUrlInput = form.querySelector("[data-base-url-input]");
    const dimensionsInput = form.querySelector("[data-dimensions-input]");

    if (!providerSelect || !modelSelect || !baseUrlInput) {
      return;
    }

    const applyProviderDefaults = (preserveCurrent = false) => {
      const provider = providerSelect.value;
      const defaults = providerDefaults[provider] || providerDefaults.ollama;
      const models = kind === "embedding" ? defaults.embeddingModels : defaults.chatModels;
      const currentModel = preserveCurrent ? modelSelect.dataset.currentModel : "";
      const currentFallback = preserveCurrent ? fallbackSelect?.dataset.currentModel : "";

      replaceOptions(modelSelect, models, currentModel);
      replaceOptions(fallbackSelect, defaults.chatModels, currentFallback, true);

      baseUrlInput.value = defaults.baseUrl;

      if (dimensionsInput) {
        dimensionsInput.value = "768";
      }

      modelSelect.disabled = models.length === 0;
    };

    applyProviderDefaults(true);
    providerSelect.addEventListener("change", () => applyProviderDefaults(false));
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-provider-form]").forEach(initializeProviderForm);
  });
})();
