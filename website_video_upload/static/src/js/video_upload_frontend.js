/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.VideoUploadFrontend = publicWidget.Widget.extend({
    selector: '.s_video_upload',

    /**
     * @override
     */
    start: function () {
        return this._super.apply(this, arguments).then(() => {
            this._applyVideoAttributes();
        });
    },

    /**
     * Apply autoplay/loop/controls based on CSS classes.
     */
    _applyVideoAttributes: function () {
        const section = this.el;
        const video = section.querySelector('.s_video_upload_player');
        if (!video || !video.getAttribute('src')) return;

        // Show the video, hide placeholder
        video.classList.remove('d-none');
        const placeholder = section.querySelector('.s_video_upload_placeholder');
        if (placeholder) {
            placeholder.classList.add('d-none');
        }

        if (section.classList.contains('s_video_autoplay')) {
            video.setAttribute('autoplay', '');
            video.setAttribute('muted', '');
            video.muted = true;
        }

        if (section.classList.contains('s_video_loop')) {
            video.setAttribute('loop', '');
        }

        if (section.classList.contains('s_video_no_controls')) {
            video.removeAttribute('controls');
        }
    },
});

export default publicWidget.registry.VideoUploadFrontend;
