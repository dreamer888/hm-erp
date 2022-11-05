odoo.define('warehouse.warehouse', function (require) {
    var FormController = require('web.FormController');
    FormController.include({
        update: function (params, options) {
            // jeff 20210717 扫码的时候让页面立即刷新
            if (this.barcodeMutex){
                options={}
            };
            return this._super(params, options);
        },
    })
});
