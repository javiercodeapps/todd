/** @odoo-module **/

import { BaseOptionComponent } from "@html_builder/core/utils";
import { useRef } from "@odoo/owl";

export class VideoUploadOption extends BaseOptionComponent {
    static id = "VideoUploadOption";
    static selector = ".s_video_upload";
    static template = "website_video_upload.VideoUploadOption";

    setup() {
        super.setup();
    }

    /**
     * Handle video upload action.
     */
    uploadVideo() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'video/mp4,video/webm,video/ogg';
        input.addEventListener('change', async (ev) => {
            const file = ev.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('video_file', file);
            formData.append('csrf_token', odoo.csrf_token);

            try {
                const response = await fetch('/website_video_upload/upload', {
                    method: 'POST',
                    body: formData,
                });
                const result = await response.json();
                if (result.error) {
                    console.error('Upload error:', result.error);
                    return;
                }

                const editingElement = this.env.getEditingElement();
                const video = editingElement.querySelector('.s_video_upload_player');
                const placeholder = editingElement.querySelector('.s_video_upload_placeholder');

                if (video) {
                    video.src = result.url;
                    video.classList.remove('d-none');
                }
                if (placeholder) {
                    placeholder.classList.add('d-none');
                }
                this._applyVideoOptions(editingElement);
            } catch (err) {
                console.error('Upload failed:', err);
            }
        });
        input.click();
    }

    /**
     * Apply video attributes based on CSS classes on the section.
     */
    _applyVideoOptions(section) {
        const video = section.querySelector('.s_video_upload_player');
        if (!video) return;

        if (section.classList.contains('s_video_autoplay')) {
            video.setAttribute('autoplay', '');
            video.setAttribute('muted', '');
            video.muted = true;
        } else {
            video.removeAttribute('autoplay');
            video.removeAttribute('muted');
            video.muted = false;
        }

        if (section.classList.contains('s_video_loop')) {
            video.setAttribute('loop', '');
        } else {
            video.removeAttribute('loop');
        }

        if (section.classList.contains('s_video_no_controls')) {
            video.removeAttribute('controls');
        } else {
            video.setAttribute('controls', '');
        }
    }
}
