{
    'name': 'Website Video Upload',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Upload and embed MP4 videos directly on your website with HTML5 player',
    'description': 'Adds an Upload Video tab to the media dialog. Upload MP4/WebM/OGG files directly into Odoo and display them with a native HTML5 video player — no YouTube, no Vimeo, no external players.',
    'author': 'Dow Group',
    'license': 'OPL-1',
    'depends': ['website'],
    'data': [],
    'images': ['static/description/thumbnail.png'],
    'assets': {
        'html_editor.assets_media_dialog': [
            'website_video_upload_v19/static/src/media_dialog/upload_video_selector.js',
            'website_video_upload_v19/static/src/media_dialog/upload_video_selector.xml',
        ],
        'html_editor.assets_editor': [
            'website_video_upload_v19/static/src/media_dialog/upload_video_plugin.js',
        ],
    },
    'installable': True,
    'application': False,
}
