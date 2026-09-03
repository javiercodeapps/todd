/** @odoo-module **/

import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

class VideoUploadOptionPlugin extends Plugin {
    static id = "videoUploadOption";
    static dependencies = ["builder-options"];

    resources = {
        builder_options: [
            {
                OptionComponent: "VideoUploadOption",
                selector: ".s_video_upload",
                template: "website_video_upload.VideoUploadOption",
            },
        ],
    };
}

registry.category("website-plugins").add(VideoUploadOptionPlugin.id, VideoUploadOptionPlugin);
