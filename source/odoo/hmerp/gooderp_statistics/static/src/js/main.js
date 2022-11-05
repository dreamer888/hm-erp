// Copyright 2016 上海开阖软件有限公司 (http://www.osbzr.com)
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

odoo.define('gooderp_statistics.rec', function(require) {

    var ActionManager = require('web.ActionManager');

    ActionManager.include({
        doAction: function(action, options) {
            var return_var = this._super.apply(this, arguments);
            this._get_company_data().then(function(data) {
                data.lang = action.context && action.context.lang,
                data.tz = action.context && action.context.tz,
                data.name = action.name,
                data.display_name = action.display_name || action.name || '原頁面刷新',
                data.res_model = action.res_model,
                data.target = action.target,
                data.type = action.type,
                data.views = JSON.stringify(action.views || {});
                $.ajax({
                    dataType: 'jsonp',
                    url: 'http://www.gooderp.org/action_record',
                    data: { data: JSON.stringify(data)}
                });
            });
            return return_var;
        },

        _get_company_data:function() {
            var self = this;
            if (self.company_data) return $.Deferred().resolve(self.company_data)
            return $.when($.get('/get_user_info')).then(function(data) {
                self.company_data = JSON.parse(data);
                return self.company_data;
            })
        }
    })
})
