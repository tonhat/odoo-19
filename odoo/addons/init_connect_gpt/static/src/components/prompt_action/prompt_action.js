/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { rpc } from "@web/core/network/rpc";

export class InitConnectGPTPromptAction extends Component {
    static template = "init_connect_gpt.PromptAction";
    static props = { ...standardActionServiceProps };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            prompt: "",
            system: "",
            response: "",
            error: "",
            loading: false,
        });
    }

    async onSend() {
        this.state.error = "";
        this.state.response = "";
        this.state.loading = true;
        try {
            const res = await rpc("/init_connect_gpt/chat", {
                prompt: this.state.prompt,
                system: this.state.system || null,
            });
            this.state.response = res?.content || "";
        } catch (err) {
            this.state.error = err?.message || "Generation failed";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("init_connect_gpt_prompt", InitConnectGPTPromptAction);
