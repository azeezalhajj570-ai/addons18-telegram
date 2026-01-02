/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useRef, onWillUnmount, useEffect } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

export class BPMNField extends Component {
    static template = "bpmn_widget.BPMNField";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["text", "char"];

    setup() {
        this.bpmnContainer = useRef("bpmnContainer");
        this.modeler = null;

        useEffect(() => {
            if (this.props.record.data[this.props.name] !== undefined) {
                this.initBpmn();
            }
        }, () => [this.props.record.data[this.props.name]]);

        onWillUnmount(() => {
            if (this.modeler) {
                this.modeler.destroy();
            }
        });
    }

    async initBpmn() {
        // Load BPMN-JS assets
        try {
            await Promise.all([
                loadCSS("https://unpkg.com/bpmn-js@14.0.0/dist/assets/diagram-js.css"),
                loadCSS("https://unpkg.com/bpmn-js@14.0.0/dist/assets/bpmn-font/css/bpmn.css"),
                loadJS("https://unpkg.com/bpmn-js@14.0.0/dist/bpmn-modeler.development.js")
            ]);
        } catch (e) {
            console.error("Failed to load BPMN assets", e);
            return;
        }

        if (!this.bpmnContainer.el || !window.BpmnJS) return;

        // Initialize Modeler if not exists
        if (!this.modeler) {
            this.modeler = new window.BpmnJS({
                container: this.bpmnContainer.el,
                keyboard: {
                    bindTo: window
                }
            });

            this.modeler.on('commandStack.changed', this.onDiagramChange.bind(this));
        }

        // Import XML
        const xmlContent = this.props.record.data[this.props.name] || this.getEmptyDiagram();
        try {
            await this.modeler.importXML(xmlContent);
        } catch (err) {
            console.error('BPMN Import Error', err);
        }
    }

    async onDiagramChange() {
        if (!this.modeler) return;
        try {
            const { xml } = await this.modeler.saveXML({ format: true });
            if (xml !== this.props.record.data[this.props.name]) {
                await this.props.record.update({ [this.props.name]: xml });
            }
        } catch (err) {
            console.error('BPMN Save Error', err);
        }
    }

    getEmptyDiagram() {
        return `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="_BPMNShape_StartEvent_2" bpmnElement="StartEvent_1">
        <dc:Bounds x="173" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;
    }

    get style() {
        return "height: 600px; border: 1px solid #ccc;";
    }
}

export const bpmnField = {
    component: BPMNField,
    supportedTypes: ["text", "char"],
};

registry.category("fields").add("bpmn_field", bpmnField);


