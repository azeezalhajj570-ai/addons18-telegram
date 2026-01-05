/** @odoo-module */

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";

export class OcrField extends Component {
    static template = "ocr.OcrField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({
            menuVisible: false,
            menuTop: 0,
            menuLeft: 0,
            currentText: "",
            targetElement: null
        });

        // Close menu on outside click logic is handled by the overlay click listener or global
        this.onWindowClick = this.onWindowClick.bind(this);
        onMounted(() => window.addEventListener("click", this.onWindowClick));
        onWillUnmount(() => window.removeEventListener("click", this.onWindowClick));
    }

    onWindowClick(ev) {
        // Close if clicking outside the menu and outside a word box
        if (this.state.menuVisible) {
            const isMenu = ev.target.closest('.ocr-action-box');
            const isWordBox = ev.target.closest('.ocr_word_box');
            if (!isMenu && !isWordBox) {
                this.state.menuVisible = false;
            }
        }
    }

    /**
     * Handle clicks on the rendered HTML content
     */
    onContainerClick(ev) {
        const wordBox = ev.target.closest('.ocr_word_box');
        if (wordBox) {
            ev.stopPropagation(); // Stop bubbling
            ev.preventDefault();

            this.state.targetElement = wordBox;
            this.state.currentText = wordBox.getAttribute('data-text') || wordBox.innerText;

            // Calculate Position relative to the container (this.el) not simple offset
            // We want it visually above the element.
            // Since the overlay is position:relative, we can use offset relative to the clicked span.

            // Note: The HTML structure has a wrapper. formatting.
            // Let's rely on standard offset logic
            const rect = wordBox.getBoundingClientRect();
            // We need coords relative to the window or viewport? No, relative to the container if we position absolute inside it.
            // But we can just use fixed position or absolute relative to the field root.

            // Simplest: Position relative to the clicked element's offsetParent
            // The python HTML wraps everything in <div class="ocr_container"> with position relative.
            // We can place the menu logic inside that container ideally, but OWL renders it outside.
            // Let's use absolute positioning relative to the `div.o_field_ocr`.
            const containerRect = ev.currentTarget.getBoundingClientRect();

            // Relative coordinates within the component
            const relTop = rect.top - containerRect.top;
            const relLeft = rect.left - containerRect.left + (rect.width / 2);

            this.state.menuTop = relTop - 10; // Shift up slightly
            this.state.menuLeft = relLeft;
            this.state.menuVisible = true;
        }
    }

    async copyText() {
        if (this.state.currentText) {
            try {
                await navigator.clipboard.writeText(this.state.currentText);
                // Feedback - Flash Green
                if (this.state.targetElement) {
                    const originalColor = this.state.targetElement.style.backgroundColor;
                    this.state.targetElement.style.backgroundColor = "rgba(82, 196, 26, 0.4)";
                    setTimeout(() => {
                        this.state.targetElement.style.backgroundColor = originalColor;
                    }, 300);
                }
                this.state.menuVisible = false;
            } catch (err) {
                console.error("Failed to copy:", err);
            }
        }
    }

    correctText() {
        if (this.state.currentText && this.state.targetElement) {
            const oldText = this.state.currentText;
            const newText = prompt("Correct OCR Text:", oldText);
            if (newText !== null && newText !== oldText) {
                // Update DOM Visuals
                this.state.targetElement.innerText = newText;
                this.state.targetElement.setAttribute('data-text', newText);
                this.state.targetElement.title = newText;

                // Note: This does NOT save back to the backend currently. 
                // That would require a server call (orm.write) if we wanted persistence.

                this.state.menuVisible = false;
            }
        }
    }
}

export const ocrField = {
    component: OcrField,
    supportedTypes: ["html"],
};

registry.category("fields").add("ocr_interactive", ocrField);
