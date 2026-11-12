/* @odoo-module */
import { Component, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// Any of these events counts as user activity and restarts the countdown.
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keypress", "click", "touchstart"];

class TimerSystrayItem extends Component {
    static template = "apg_auto_logout_idle.TimerSystray";
    static props = {};

    setup() {
        super.setup();
        this.state = useState({ idle_time: null });
        this.minutes = 0;
        this.updatedTimestamp = 0;
        this.interval = null;
        this.unmounted = false;

        this.resetTimer = this.resetTimer.bind(this);
        for (const eventName of ACTIVITY_EVENTS) {
            document.addEventListener(eventName, this.resetTimer);
        }
        onWillUnmount(() => {
            this.unmounted = true;
            clearInterval(this.interval);
            for (const eventName of ACTIVITY_EVENTS) {
                document.removeEventListener(eventName, this.resetTimer);
            }
        });

        this.get_idle_time();
    }

    get_idle_time() {
        rpc("/get_idle_time/timer", {}).then((minutes) => {
            if (minutes && !this.unmounted) {
                this.minutes = minutes;
                this.startTimer();
            }
        });
    }

    resetTimer() {
        this.updatedTimestamp = Date.now() + this.minutes * 60 * 1000;
    }

    /** Run the countdown and feed the value displayed by the template. */
    startTimer() {
        this.resetTimer();
        this.interval = setInterval(() => {
            const distance = this.updatedTimestamp - Date.now();
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            if (days) {
                this.state.idle_time = `${days}d ${hours}h ${minutes}m ${seconds}s`;
            } else if (hours) {
                this.state.idle_time = `${hours}h ${minutes}m ${seconds}s`;
            } else {
                this.state.idle_time = `${minutes}m ${seconds}s`;
            }

            if (distance < 0) {
                clearInterval(this.interval);
                this.interval = null;
                this.state.idle_time = "EXPIRED";
                browser.location.replace("/web/session/logout");
            }
        }, 1000);
    }
}

export const systrayItem = {
    Component: TimerSystrayItem,
};

registry.category("systray").add("apg_auto_logout_idle.TimerSystray", systrayItem, {
    sequence: 25,
});
