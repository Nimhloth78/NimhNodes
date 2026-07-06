import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "CustomNodes.NanoGPTLocal",

    async nodeCreated(node) {
        if (node.comfyClass !== "NanoGPT_Local_ChatCompletion") return;

        const providerWidget = node.widgets.find(w => w.name === "provider");
        const modelWidget     = node.widgets.find(w => w.name === "model");
        const apiKeyWidget    = node.widgets.find(w => w.name === "api_key");
        const apiBaseWidget   = node.widgets.find(w => w.name === "api_base_url");
        const serverWidget    = node.widgets.find(w => w.name === "local_server_url");

        if (!modelWidget || !providerWidget) return;

        // ── Refresh button ──────────────────────────────
        const refreshBtn = node.addWidget(
            "button",
            "refresh_models",
            "🔄 Refresh Models",
            async () => {
                const provider = providerWidget.value;
                refreshBtn.name = "⏳ Loading…";

                let url;
                if (provider === "NanoGPT (Cloud)") {
                    const params = new URLSearchParams();
                    if (apiKeyWidget && apiKeyWidget.value) params.set("api_key", apiKeyWidget.value);
                    if (apiBaseWidget && apiBaseWidget.value) params.set("api_base", apiBaseWidget.value);
                    url = `/nanogpt/models?${params.toString()}`;
                } else {
                    const params = new URLSearchParams();
                    params.set("provider", provider);
                    if (serverWidget && serverWidget.value) params.set("server_url", serverWidget.value);
                    url = `/nanogpt/local_models?${params.toString()}`;
                }

                try {
                    const resp = await fetch(url);
                    const data = await resp.json();

                    if (data.models && data.models.length > 0) {
                        modelWidget.options.values = data.models;
                        if (!data.models.includes(modelWidget.value)) {
                            modelWidget.value = data.models[0];
                        }
                        refreshBtn.name = `🔄 Refresh Models (${data.models.length} loaded)`;
                    } else {
                        refreshBtn.name = `❌ ${data.error || "No models returned"}`;
                    }
                } catch (err) {
                    console.error("[NanoGPT-Local] Fetch error:", err);
                    refreshBtn.name = "❌ Network error – retry";
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

        // ── Auto-save API key on change ─────────────────
        if (apiKeyWidget) {
            const origCallback = apiKeyWidget.callback;
            apiKeyWidget.callback = function (value) {
                if (origCallback) origCallback.call(this, value);
                if (value && value.length > 5) {
                    fetch("/nanogpt/save_config", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ api_key: value }),
                    }).catch(() => {});
                }
            };
        }

        node.setSize(node.computeSize());
    },
});
