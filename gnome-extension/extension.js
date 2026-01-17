import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import Meta from 'gi://Meta';
import Soup from 'gi://Soup?version=3.0';
import Pango from 'gi://Pango';

import { Extension, gettext as _ } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const SelectionArea = GObject.registerClass({
    Signals: { 'area-selected': { param_types: [GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT] } },
}, class SelectionArea extends St.Widget {
    _init() {
        super._init({
            name: 'selection-area',
            reactive: true,
            visible: false,
            style: 'background-color: rgba(0,0,0,0.1);',
            x: 0,
            y: 0,
            width: global.screen_width,
            height: global.screen_height,
        });

        this._startX = 0;
        this._startY = 0;
        this._isSelecting = false;
        this._lasso = new St.Widget({ style_class: 'selection-laso', visible: false });
        this.add_child(this._lasso);

        this.connect('button-press-event', this._onButtonPress.bind(this));
        this.connect('motion-event', this._onMotion.bind(this));
        this.connect('button-release-event', this._onButtonRelease.bind(this));
    }

    _onButtonPress(actor, event) {
        let [x, y] = event.get_coords();
        this._startX = x;
        this._startY = y;
        this._isSelecting = true;
        this._lasso.set_position(x, y);
        this._lasso.set_size(0, 0);
        this._lasso.show();
        return Clutter.EVENT_STOP;
    }

    _onMotion(actor, event) {
        if (!this._isSelecting) return Clutter.EVENT_PROPAGATE;
        let [x, y] = event.get_coords();
        let w = x - this._startX;
        let h = y - this._startY;

        let lx = this._startX;
        let ly = this._startY;
        if (w < 0) { lx = x; w = -w; }
        if (h < 0) { ly = y; h = -h; }

        this._lasso.set_position(lx, ly);
        this._lasso.set_size(w, h);
        return Clutter.EVENT_STOP;
    }

    _onButtonRelease(actor, event) {
        if (!this._isSelecting) return Clutter.EVENT_PROPAGATE;
        this._isSelecting = false;
        this._lasso.hide();
        this.hide();

        let [x, y] = event.get_coords();
        let w = Math.abs(x - this._startX);
        let h = Math.abs(y - this._startY);
        let lx = Math.min(x, this._startX);
        let ly = Math.min(y, this._startY);

        if (w > 10 && h > 10) {
            this.emit('area-selected', lx, ly, w, h);
        }
        return Clutter.EVENT_STOP;
    }
});

export default class ScreenshotTranslatorExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._selectionArea = new SelectionArea();
        Main.layoutManager.addChrome(this._selectionArea);

        this._selectionArea.connect('area-selected', (obj, x, y, w, h) => {
            this._takeScreenshot(x, y, w, h);
        });

        console.log("ScreenshotTranslator: ENABLED (Version Manual Byte Construction Clean)");

        Main.wm.addKeybinding(
            'start-capture',
            this._settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL,
            () => {
                this._startSelection();
            }
        );

        this._httpSession = new Soup.Session();
    }

    disable() {
        if (this._selectionArea) {
            this._selectionArea.destroy();
            this._selectionArea = null;
        }
        if (this._resultBox) {
            this._resultBox.destroy();
            this._resultBox = null;
        }
        Main.wm.removeKeybinding('start-capture');
        this._settings = null;
    }

    _startSelection() {
        if (this._selectionArea) {
            this._selectionArea.show();
            global.stage.set_key_focus(this._selectionArea);
        }
    }

    async _takeScreenshot(x, y, w, h) {
        const cleanPath = GLib.build_filenamev([GLib.get_tmp_dir(), 'clean.png']);

        try {
            const file = Gio.File.new_for_path(cleanPath);
            const stream = file.replace(null, false, Gio.FileCreateFlags.NONE, null);

            const screenshot = new Shell.Screenshot();
            screenshot.screenshot_area(x, y, w, h, stream, (screenshot, success) => {
                try {
                    stream.close(null);
                } catch (e) {
                    console.error('Failed to close stream', e);
                }

                if (success) {
                    this._processAndSend(cleanPath, x, y, w, h);
                } else {
                    console.error('Screenshot failed (callback)');
                    Main.notify('Screenshot failed');
                }
            });
        } catch (e) {
            console.error('Screenshot failed:', e);
            Main.notify('Screenshot failed', e.message);
        }
    }

    async _processAndSend(cleanPath, x, y, w, h) {
        try {
            const [success, cleanBytes] = GLib.file_get_contents(cleanPath);
            if (!success) {
                console.error('Failed to read clean.png');
                Main.notify('Error', 'Failed to read screenshot file');
                return;
            }

            const guideBytes = cleanBytes; /* guide same as clean for now */
            this._uploadImages(cleanBytes, guideBytes, x, y, w, h);

        } catch (e) {
            console.error('Processing failed:', e);
            Main.notify('Processing Error', e.message);
        }
    }

    _concatBuffers(buffers) {
        let totalLength = 0;
        for (let b of buffers) totalLength += b.length;

        let result = new Uint8Array(totalLength);
        let offset = 0;
        for (let b of buffers) {
            result.set(b, offset);
            offset += b.length;
        }
        return result;
    }

    async _uploadImages(cleanBytes, guideBytes, x, y, w, h) {
        console.log("ScreenshotTranslator: uploadImages called (Manual Byte Construction)");
        const url = 'http://127.0.0.1:8012/api/v1/ocr_translate_with_grounding';

        try {
            const boundary = "------------------------" + Date.now().toString(16);
            const encoder = new TextEncoder();
            const parts = [];

            const addPart = (name, filename, contentType, data) => {
                let header = `--${boundary}\r\n`;
                header += `Content-Disposition: form-data; name="${name}"`;
                if (filename) header += `; filename="${filename}"`;
                header += `\r\n`;
                if (contentType) header += `Content-Type: ${contentType}\r\n`;
                header += `\r\n`;

                parts.push(encoder.encode(header));
                parts.push(data instanceof Uint8Array ? data : encoder.encode(data));
                parts.push(encoder.encode("\r\n"));
            };

            addPart('clean_image', 'clean.png', 'image/png', cleanBytes);
            addPart('guide_image', 'guide.png', 'image/png', guideBytes);
            addPart('options', null, null, JSON.stringify({ return_roi_fallback: true }));

            parts.push(encoder.encode(`--${boundary}--\r\n`));

            const bodyBytes = this._concatBuffers(parts);
            const glibBytes = new GLib.Bytes(bodyBytes);

            const msg = Soup.Message.new('POST', url);
            msg.set_request_body_from_bytes(`multipart/form-data; boundary=${boundary}`, glibBytes);

            const bytes = await this._httpSession.send_and_read_async(msg, GLib.PRIORITY_DEFAULT, null);

            const status = msg.get_status();
            if (status !== 200) {
                throw new Error(`Server returned ${status} ${msg.get_reason_phrase()}`);
            }

            const responseBody = new TextDecoder().decode(bytes.get_data());

            const json = JSON.parse(responseBody);
            this._showResult(json, x, y, w, h);

        } catch (e) {
            console.error('Translation request failed:', e);
            Main.notify('Translation Error', e.message);
        }
    }

    _showResult(json, x, y, w, h) {
        if (this._resultBox) {
            this._resultBox.destroy();
            this._resultBox = null;
        }

        const text = json.ja_translation || json.ocr_text || "No result";

        this._resultBox = new St.BoxLayout({
            style_class: 'result-container',
            vertical: true,
            x: x,
            y: y + 20
        });

        if (x + 300 > global.screen_width) this._resultBox.set_position(global.screen_width - 320, y);
        const maxHeight = 600;
        if (y + maxHeight > global.screen_height) this._resultBox.set_position(x, global.screen_height - (maxHeight + 20));

        const scrollView = new St.ScrollView({
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
            style_class: 'result-scrollview'
        });

        // Match selection size (clamped)
        // Width: 200 ~ 960
        let boxW = Math.max(200, Math.min(960, w));
        // Height: selection height minus approx header (40px), max 600
        let boxH = Math.max(100, Math.min(600, h - 40));

        scrollView.set_width(boxW);
        scrollView.set_height(boxH);

        const label = new St.Label({
            text: text,
            style_class: 'result-text'
        });

        label.clutter_text.line_wrap = true;
        label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        label.clutter_text.set_width(boxW); // Ensure wrapping matches width

        // St.Label doesn't implement St.Scrollable needs wrapper
        const scrollContent = new St.BoxLayout({ vertical: true });
        scrollContent.add_child(label);
        scrollView.set_child(scrollContent);

        const closeBtn = new St.Button({
            child: new St.Label({ text: "X" }),
            style_class: 'close-button'
        });
        closeBtn.connect('clicked', () => {
            if (this._resultBox) {
                this._resultBox.destroy();
                this._resultBox = null;
            }
        });

        const header = new St.BoxLayout();
        header.add_child(new St.Label({ text: "Translation", style_class: 'result-title' }));
        header.add_child(closeBtn);

        this._resultBox.add_child(header);
        this._resultBox.add_child(scrollView);

        Main.layoutManager.addChrome(this._resultBox);
    }
}
