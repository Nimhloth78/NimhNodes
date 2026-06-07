import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "CustomNodes.SaveTextPreview",

    async nodeCreated(node) {
        if (node.comfyClass !== "SaveTextToFile") return;

        // Read-only display widget
        const display = node.addWidget("text", "last_saved", "", () => {}, {
            serialize: false,
        });

        if (display.inputEl) {
            display.inputEl.readOnly       = true;
            display.inputEl.style.opacity  = "0.75";
            display.inputEl.style.fontFamily = "monospace";
            display.inputEl.style.fontSize = "10px";
            display.inputEl.style.cursor   = "text";
        }

        // Update after execution
        const originalOnExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            if (originalOnExecuted) {
                originalOnExecuted.call(this, output);
            }
            if (output?.saved_path?.length) {
                const name = output.saved_filename?.[0] || "";
                const size = output.saved_size?.[0]     || "";
                display.value = `✅ ${name}  (${size})`;
                if (display.inputEl) {
                    display.inputEl.title = output.saved_path[0];
                }
            }
        };

        node.setSize(node.computeSize());
    },
});