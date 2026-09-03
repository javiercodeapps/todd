/** @odoo-module **/

import { Plugin } from "@html_editor/plugin";
import { Editor } from "@html_editor/editor";
import { UploadVideoSelector } from "./upload_video_selector";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

export class UploadVideoPlugin extends Plugin {
    static id = "uploadVideo";
    resources = {
        media_dialog_extra_tabs: {
            id: "UPLOAD_VIDEO",
            title: _t("Upload Video"),
            Component: UploadVideoSelector,
            sequence: 35,
        },
    };
}

// Inject our plugin into the editor's plugin list.
// Odoo 19 has no plugin registry — plugins are passed as an explicit array,
// so we patch Editor to add ours before plugins are processed.
patch(Editor.prototype, {
    preparePlugins() {
        if (this.config.Plugins && !this.config.Plugins.includes(UploadVideoPlugin)) {
            this.config.Plugins.push(UploadVideoPlugin);
        }
        return super.preparePlugins(...arguments);
    },
});
