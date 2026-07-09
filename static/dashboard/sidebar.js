(() => {
  const minWidth = 220;
  const maxWidth = 520;
  const widthStorageKey = "dashboardSidebarWidth";
  const collapsedStorageKey = "dashboardSidebarCollapsed";

  const clampWidth = (width) => Math.min(maxWidth, Math.max(minWidth, width));

  const storage = {
    get(key) {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        // Sidebar controls should still work when localStorage is unavailable.
      }
    },
  };

  const initializeSidebarControls = () => {
    const shell = document.querySelector(".app-shell");
    if (!shell || shell.dataset.sidebarReady === "true") {
      return;
    }

    shell.dataset.sidebarReady = "true";

    const toggle = shell.querySelector("[data-sidebar-toggle]");
    const resizer = shell.querySelector("[data-sidebar-resizer]");
    const sidebar = shell.querySelector(".sidebar");
    const hoverZone = shell.querySelector("[data-sidebar-hover-zone]");

    const setPeeking = (isPeeking) => {
      shell.classList.toggle("sidebar-peeking", isPeeking);
    };

    const setCollapsed = (isCollapsed) => {
      if (!isCollapsed) {
        setPeeking(false);
      }
      shell.classList.toggle("sidebar-collapsed", isCollapsed);
      if (toggle) {
        toggle.setAttribute("aria-expanded", String(!isCollapsed));
        toggle.setAttribute(
          "aria-label",
          isCollapsed ? "Open sidebar" : "Close sidebar",
        );
      }
      storage.set(collapsedStorageKey, String(isCollapsed));
    };

    const savedWidth = Number(storage.get(widthStorageKey));
    if (Number.isFinite(savedWidth) && savedWidth > 0) {
      shell.style.setProperty("--sidebar-width", `${clampWidth(savedWidth)}px`);
    }

    setCollapsed(storage.get(collapsedStorageKey) === "true");

    toggle?.addEventListener("click", () => {
      if (
        shell.classList.contains("sidebar-collapsed") &&
        shell.classList.contains("sidebar-peeking")
      ) {
        setCollapsed(false);
        return;
      }

      setCollapsed(!shell.classList.contains("sidebar-collapsed"));
    });

    hoverZone?.addEventListener("pointerenter", () => {
      if (
        !window.matchMedia("(max-width: 980px)").matches &&
        shell.classList.contains("sidebar-collapsed")
      ) {
        setPeeking(true);
      }
    });

    sidebar?.addEventListener("pointerleave", () => {
      if (shell.classList.contains("sidebar-collapsed")) {
        setPeeking(false);
      }
    });

    resizer?.addEventListener("pointerdown", (event) => {
      if (window.matchMedia("(max-width: 980px)").matches) {
        return;
      }

      event.preventDefault();
      document.body.classList.add("sidebar-resizing");
      setCollapsed(false);

      const handlePointerMove = (moveEvent) => {
        const width = clampWidth(moveEvent.clientX);
        shell.style.setProperty("--sidebar-width", `${width}px`);
        storage.set(widthStorageKey, String(width));
      };

      const handlePointerUp = () => {
        document.body.classList.remove("sidebar-resizing");
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", handlePointerUp);
        window.removeEventListener("pointercancel", handlePointerUp);
      };

      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp);
      window.addEventListener("pointercancel", handlePointerUp);
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSidebarControls, {
      once: true,
    });
  } else {
    initializeSidebarControls();
  }
})();
