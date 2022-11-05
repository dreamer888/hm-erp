odoo.define('num_to_china.NumberToChina', function(require) {
"use strict";

var basicFields = require('web.basic_fields');
var fieldRegistry = require('web.field_registry');

var NumberToChina = basicFields.FieldFloat.extend({
    _renderReadonly: function () {
        var self = this;
        this._rpc({
                model: 'res.currency',
                method: 'rmb_upper',
                args: [parseFloat(this.value) || 0],
            }).then(function (data) {
                self.$el.text(data || self.value);
            });

    },
});

fieldRegistry.add('num_to_china', NumberToChina);

return NumberToChina;

});
