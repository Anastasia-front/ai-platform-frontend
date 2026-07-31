(() => {
    // Restores scroll position on pages whose actions (add step, run
    // workflow, delete execution, ...) do a normal POST + redirect back to
    // the same page. Without this, every such action snaps the page back
    // to the top. Opt in per-page by adding `data-scroll-persist` to the
    // page's scrollable root container.
    const keyFor = () =>
        `dashboard:scrollTop:${window.location.pathname}${window.location.search}`;

    const storage = {
        get(key) {
            try {
                return window.sessionStorage.getItem(key);
            } catch {
                return null;
            }
        },
        set(key, value) {
            try {
                window.sessionStorage.setItem(key, value);
            } catch {
                // Scroll restore is a nice-to-have; ignore storage failures.
            }
        },
        remove(key) {
            try {
                window.sessionStorage.removeItem(key);
            } catch {
                // Ignore.
            }
        },
    };

    const remember = (container) => {
        // Either the inner container or the window itself may be the thing
        // that actually scrolls, depending on the page's layout -- record
        // both and restore whichever turns out to apply.
        storage.set(
            keyFor(),
            JSON.stringify({
                container: container.scrollTop,
                window: window.scrollY,
            }),
        );
    };

    const restore = (container) => {
        const key = keyFor();
        const raw = storage.get(key);
        if (raw === null) {
            return;
        }

        let parsed;
        try {
            parsed = JSON.parse(raw);
        } catch {
            return;
        }

        requestAnimationFrame(() => {
            if (Number.isFinite(parsed.container)) {
                container.scrollTop = parsed.container;
            }
            if (Number.isFinite(parsed.window)) {
                window.scrollTo(0, parsed.window);
            }
            storage.remove(key);
        });
    };

    const init = () => {
        const container = document.querySelector("[data-scroll-persist]");
        if (!container) {
            return;
        }

        if ("scrollRestoration" in window.history) {
            window.history.scrollRestoration = "manual";
        }

        restore(container);

        // Capture phase: fires before the browser navigates away for a
        // plain form submit, regardless of which element triggered it.
        container.addEventListener("submit", () => remember(container), true);
        window.addEventListener("beforeunload", () => remember(container));
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
})();
