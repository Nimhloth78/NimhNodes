import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "CustomNodes.FolderPromptPreset",

    async nodeCreated(node) {
        if (node.comfyClass !== "FolderPromptPreset") return;

        const folderWidget = node.widgets.find(w => w.name === "folder");
        const presetWidget = node.widgets.find(w => w.name === "preset");
        if (!folderWidget || !presetWidget) return;

        const refresh = async () => {
            const params = new URLSearchParams({ folder: folderWidget.value || "" });
            try {
                const resp = await fetch(`/nimh/folder_presets?${params.toString()}`);
                const data = await resp.json();

                if (data.presets && data.presets.length > 0) {
                    presetWidget.options.values = data.presets;
                    if (!data.presets.includes(presetWidget.value)) {
                        presetWidget.value = data.presets[0];
                    }
                    refreshBtn.name = `🔄 Refresh (${data.presets.length} files)`;
                } else {
                    presetWidget.options.values = ["(no prompt files found)"];
                    presetWidget.value = "(no prompt files found)";
                    refreshBtn.name = `❌ ${data.error || "No files found"}`;
                }
            } catch (err) {
                console.error("[FolderPromptPreset] Fetch error:", err);
                refreshBtn.name = "❌ Network error – retry";
            }
            app.graph.setDirtyCanvas(true, true);
        };

        const refreshBtn = node.addWidget("button", "refresh_presets", "🔄 Refresh", refresh);

        // Put the button between the folder and preset widgets
        const folderIdx = node.widgets.indexOf(folderWidget);
        const btnIdx    = node.widgets.indexOf(refreshBtn);
        if (btnIdx > -1 && folderIdx > -1 && btnIdx !== folderIdx + 1) {
            node.widgets.splice(btnIdx, 1);
            node.widgets.splice(folderIdx + 1, 0, refreshBtn);
        }

        // Re-list whenever the folder text changes
        const origCallback = folderWidget.callback;
        folderWidget.callback = function (value) {
            if (origCallback) origCallback.call(this, value);
            refresh();
        };

        // On load, wait for the saved workflow values to be restored, then re-list.
        // The saved preset is kept if it still exists in the folder.
        setTimeout(refresh, 0);

        node.setSize(node.computeSize());
    },
});
