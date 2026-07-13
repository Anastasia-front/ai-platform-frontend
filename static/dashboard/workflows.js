(() => {
    const storageKey = "dashboard.openWorkflowTemplate";

    const readStoredTemplate = () => {
        try {
            return window.localStorage.getItem(storageKey) || "";
        } catch {
            return "";
        }
    };

    const writeStoredTemplate = (templateKey) => {
        try {
            if (templateKey) {
                window.localStorage.setItem(storageKey, templateKey);
            } else {
                window.localStorage.removeItem(storageKey);
            }
        } catch {
            // Workflow accordions should still work when localStorage is unavailable.
        }
    };

    const openTemplate = (templates, outerAccordion, templateKey) => {
        let matchedTemplate = null;

        templates.forEach((template) => {
            const isMatch = template.dataset.templateKey === templateKey;
            template.open = isMatch;
            if (isMatch) {
                matchedTemplate = template;
            }
        });

        if (matchedTemplate) {
            outerAccordion.open = true;
        }

        return matchedTemplate;
    };

    const setupCvDocumentPickers = () => {
        document.querySelectorAll("[data-cv-document-picker]").forEach((picker) => {
            const list = picker.querySelector("[data-cv-document-list]");
            const limitMessage = picker.querySelector("[data-cv-document-limit]");
            const maxDocuments = Number(picker.dataset.maxCvDocuments || 10);
            const firstSelect = list?.querySelector("select");

            if (!list || !firstSelect || !maxDocuments) {
                return;
            }

            const createRow = () => {
                const rowCount = list.querySelectorAll(".cv-document-picker-row").length;
                const row = document.createElement("label");
                row.className = "cv-document-picker-row";

                const label = document.createElement("span");
                label.textContent = `CV ${rowCount + 1}`;

                const select = firstSelect.cloneNode(true);
                select.required = false;
                select.value = "";

                row.append(label, select);
                list.append(row);
                return select;
            };

            const syncRows = () => {
                const rows = Array.from(list.querySelectorAll(".cv-document-picker-row"));
                const selects = rows.map((row) => row.querySelector("select")).filter(Boolean);
                const lastSelect = selects[selects.length - 1];
                const hasEmptySelect = selects.some((select) => !select.value);
                const canAddMore = selects.length < maxDocuments;

                if (lastSelect?.value && !hasEmptySelect && canAddMore) {
                    createRow();
                }

                if (limitMessage) {
                    const reachedLimit =
                        list.querySelectorAll(".cv-document-picker-row").length >= maxDocuments &&
                        Array.from(list.querySelectorAll("select")).every((select) => select.value);
                    limitMessage.hidden = !reachedLimit;
                }
            };

            list.addEventListener("change", (event) => {
                if (event.target.matches("select")) {
                    syncRows();
                }
            });
            syncRows();
        });
    };

    document.addEventListener("DOMContentLoaded", () => {
        setupCvDocumentPickers();

        const outerAccordion = document.querySelector("[data-workflow-templates]");
        if (!outerAccordion) {
            return;
        }

        const templates = Array.from(
            outerAccordion.querySelectorAll(".workflow-template-accordion[data-template-key]")
        );
        if (!templates.length) {
            return;
        }

        const urlTemplate = new URLSearchParams(window.location.search).get("template") || "";
        const initialTemplate = urlTemplate || readStoredTemplate();

        if (initialTemplate) {
            const openedTemplate = openTemplate(templates, outerAccordion, initialTemplate);
            if (openedTemplate) {
                writeStoredTemplate(initialTemplate);
            }
        }

        templates.forEach((template) => {
            template.addEventListener("toggle", () => {
                const templateKey = template.dataset.templateKey || "";

                if (template.open) {
                    templates.forEach((sibling) => {
                        if (sibling !== template) {
                            sibling.open = false;
                        }
                    });
                    outerAccordion.open = true;
                    writeStoredTemplate(templateKey);
                    return;
                }

                const hasOpenTemplate = templates.some((item) => item.open);
                if (!hasOpenTemplate && readStoredTemplate() === templateKey) {
                    writeStoredTemplate("");
                }
            });
        });

        outerAccordion.addEventListener("toggle", () => {
            if (!outerAccordion.open && templates.some((template) => template.open)) {
                outerAccordion.open = true;
            }
        });
    });
})();
