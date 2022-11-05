odoo.define('form_disable_edit_mode', function (require) {
    var FormRenderer = require('web.FormRenderer');
    var Domain = require("web.Domain");
    FormRenderer.include({

        autofocus: function () {
            this.show_hide_edit_button();
            return this._super();
        },

        show_hide_edit_button : function () {
            if( 'disable_edit_mode' in this.arch.attrs && this.arch.attrs.disable_edit_mode) {
                var domain = Domain.prototype.stringToArray(this.arch.attrs.disable_edit_mode)
                var button = $(".o_form_button_edit");
                if (button) {
                    var hide_edit = new Domain(domain).compute(this.state.data);
                    button.toggle(!hide_edit);
                }
            }
        },
    });
});