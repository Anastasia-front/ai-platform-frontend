(() => {
  const pages = [
    {
      key: "dashboard.lastProvidersUrl",
      path: "/providers/",
      pageSelector: ".provider-console",
      tabSelector: ".embedding-tools .project-tabs a",
    },
    {
      key: "dashboard.lastWorkflowsUrl",
      path: "/workflows/",
      pageSelector: ".workflow-console",
      tabSelector: ".project-tabs a, .workflow-list-item",
    },
    {
      key: "dashboard.lastExecutionsUrl",
      path: "/executions/",
      pageSelector: ".execution-console .execution-tabs",
      tabSelector: ".execution-tabs a",
    },
  ];

  const readStoredUrl = (key) => {
    try {
      return window.localStorage.getItem(key) || "";
    } catch {
      return "";
    }
  };

  const writeStoredUrl = (key, url) => {
    try {
      window.localStorage.setItem(key, url);
    } catch {
      // Navigation still works normally when localStorage is unavailable.
    }
  };

  const isSamePath = (url, path) => {
    try {
      return new URL(url, window.location.href).pathname === path;
    } catch {
      return false;
    }
  };

  const pathAndSearch = (url) => {
    const parsedUrl = new URL(url, window.location.href);
    return `${parsedUrl.pathname}${parsedUrl.search}`;
  };

  const normalizedCurrentUrl = () => `${window.location.pathname}${window.location.search}`;

  const updateUtilityLinks = () => {
    pages.forEach(({key, path}) => {
      const storedUrl = readStoredUrl(key);
      if (!storedUrl || !isSamePath(storedUrl, path)) {
        return;
      }

      document.querySelectorAll(".utility-nav a").forEach((link) => {
        if (isSamePath(link.href, path)) {
          link.href = storedUrl;
        }
      });
    });
  };

  const initializePagePersistence = () => {
    pages.forEach(({key, path, pageSelector, tabSelector}) => {
      const page = document.querySelector(pageSelector);
      if (!page || window.location.pathname !== path) {
        return;
      }

      writeStoredUrl(key, normalizedCurrentUrl());

      document.addEventListener("click", (event) => {
        const link = event.target.closest(tabSelector);
        if (!link || !isSamePath(link.href, path)) {
          return;
        }

        writeStoredUrl(key, pathAndSearch(link.href));
        updateUtilityLinks();
      });
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    updateUtilityLinks();
    initializePagePersistence();
  });

  window.DashboardTabPersistence = {
    rememberCurrent(path) {
      const page = pages.find((item) => item.path === path);
      if (page) {
        writeStoredUrl(page.key, normalizedCurrentUrl());
        updateUtilityLinks();
      }
    },
  };
})();
