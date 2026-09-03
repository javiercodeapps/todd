/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class UploadVideoSelector extends Component {
    static template = "website_video_upload_v19.UploadVideoSelector";
    static mediaSpecificClasses = ["s_uploaded_video"];
    static mediaSpecificStyles = [];
    static mediaExtraClasses = [];
    static tagNames = ["VIDEO"];

    static props = {
        selectMedia: Function,
        errorMessages: Function,
        media: { optional: true },
        "*": true,
    };

    setup() {
        this.state = useState({
            videoUrl: "",
            uploading: false,
            autoplay: false,
            loop: false,
            controls: true,
        });

        // If editing an existing uploaded video element
        if (this.props.media && this.props.media.tagName === "VIDEO") {
            const video = this.props.media;
            this.state.videoUrl = video.getAttribute("src") || "";
            this.state.autoplay = video.hasAttribute("autoplay");
            this.state.loop = video.hasAttribute("loop");
            this.state.controls = video.hasAttribute("controls");
            if (this.state.videoUrl) {
                this._updateSelection();
            }
        }
    }

    async onFileChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;

        this.state.uploading = true;
        this.props.errorMessages("");

        const formData = new FormData();
        formData.append("video_file", file);
        formData.append("csrf_token", odoo.csrf_token);

        try {
            const response = await fetch("/website_video_upload/upload", {
                method: "POST",
                body: formData,
            });
            const result = await response.json();
            if (result.error) {
                this.props.errorMessages(result.error);
                this.state.uploading = false;
                return;
            }
            this.state.videoUrl = result.url;
            this.state.uploading = false;
            this._updateSelection();
        } catch (err) {
            this.props.errorMessages(_t("Upload failed"));
            this.state.uploading = false;
        }
    }

    onToggleAutoplay() {
        this.state.autoplay = !this.state.autoplay;
        this._updateSelection();
    }

    onToggleLoop() {
        this.state.loop = !this.state.loop;
        this._updateSelection();
    }

    onToggleControls() {
        this.state.controls = !this.state.controls;
        this._updateSelection();
    }

    _updateSelection() {
        if (this.state.videoUrl) {
            this.props.selectMedia({
                id: this.state.videoUrl,
                src: this.state.videoUrl,
                autoplay: this.state.autoplay,
                loop: this.state.loop,
                controls: this.state.controls,
            });
        }
    }

    static createElements(selectedMedia) {
        return selectedMedia.map((video) => {
            const el = document.createElement("video");
            el.setAttribute("src", video.src);
            el.setAttribute("playsinline", "");
            el.setAttribute("contenteditable", "false");
            el.classList.add("s_uploaded_video");
            el.style.width = "100%";
            el.style.maxWidth = "100%";

            if (video.autoplay) {
                el.setAttribute("autoplay", "");
                el.setAttribute("muted", "");
            }
            if (video.loop) {
                el.setAttribute("loop", "");
            }
            if (video.controls) {
                el.setAttribute("controls", "");
            }
            return el;
        });
    }
}
