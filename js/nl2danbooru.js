import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "CustomNodes.NL2Danbooru",

    async nodeCreated(node) {
        if (node.comfyClass !== "NL2DanbooruTags") return;

        const modelWidget   = node.widgets.find(w => w.name === "model");
        const apiKeyWidget  = node.widgets.find(w => w.name === "api_key");
        const apiBaseWidget = node.widgets.find(w => w.name === "api_base_url");

        if (!modelWidget) return;

        // ── Refresh Models button ───────────────────────
        const refreshBtn = node.addWidget(
            "button",
            "refresh_models",
            "🔄 Refresh Models",
            async () => {
                const params = new URLSearchParams();
                if (apiKeyWidget?.value)  {
					params.set("api_key",  apiKeyWidget.value);
				}
                if (apiBaseWidget?.value)  {
					params.set("api_base", apiBaseWidget.value);
				}

                refreshBtn.name = "⏳ Loading…";

                try {
                    const resp = await fetch(`/nanogpt/models?${params.toString()}`);
                    const data = await resp.json();

                    if (data.models?.length > 0) {
                        modelWidget.options.values = data.models;
                        if (!data.models.includes(modelWidget.value)) {
                            modelWidget.value = data.models[0];
                        }
                        refreshBtn.name = `🔄 Refresh (${data.models.length} models)`;
                    } else {
                        refreshBtn.name = `❌ ${data.error || "No models"}`;
                    }
                } catch (err) {
                    console.error("[NL2Danbooru]", err);
                    refreshBtn.name = "❌ Network error";
                }

                app.graph.setDirtyCanvas(true, true);
                node.setSize(node.computeSize());
            }
        );

        // Position button right after model dropdown
        const modelIdx = node.widgets.indexOf(modelWidget);
        const btnIdx   = node.widgets.indexOf(refreshBtn);
        if (btnIdx > -1 && modelIdx > -1 && btnIdx !== modelIdx + 1) {
            node.widgets.splice(btnIdx, 1);
            node.widgets.splice(modelIdx + 1, 0, refreshBtn);
        }

        // ── Tag preview after execution ─────────────────
        const preview = node.addWidget("text", "tag_preview", "", () => {}, {
            serialize: false,
        });

        if (preview.inputEl) {
            preview.inputEl.readOnly        = true;
            preview.inputEl.style.opacity   = "0.8";
            preview.inputEl.style.fontFamily = "monospace";
            preview.inputEl.style.fontSize  = "10px";
            preview.inputEl.style.cursor    = "text";
            preview.inputEl.style.height    = "60px";
        }

        const originalOnExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            if (originalOnExecuted) originalOnExecuted.call(this, output);

            // The tags output is index 0 in RETURN_TYPES
            // We read it from the node's output slots after execution
            if (node.outputs?.[0]?.links?.length > 0) {
                preview.value = "✅ Tags generated — see connected node";
            }
        };

        node.setSize(node.computeSize());
    },
});