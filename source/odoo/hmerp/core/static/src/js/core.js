odoo.define('core.core', function (require) {
    "use strict";
    
// var ListRenderer = require('web.ListRenderer');
// var core = require('web.core');
// var _t = core._t;

// ListRenderer.include({
//     events: _.extend({}, ListRenderer.prototype.events, {
//         'click tr .o_list_record_copy': '_onCopyIconClick',
//     }),
//     _onCopyIconClick: function (event) {
//         event.stopPropagation();
//         var $row = $(event.target).closest('tr');
//         var id = $row.data('id');
//         if ($row.hasClass('o_selected_row')) {
//             alert('1:'+id);
//             // this.trigger_up('list_record_remove', {id: id});
//         } else {
//             var self = this;
//             this.unselectRow().then(function () {
//                 alert('2:'+id);
//                 // self.trigger_up('list_record_remove', {id: id});
//             });
//         }
//     },

//     _renderFooter: function () {
//         const $footer = this._super.apply(this, arguments);
//         if (this.addTrashIcon && !(this.isMany2Many)) {
//             $footer.find('tr').prepend($('<td>'));
//         }
//         return $footer;
//     },

//     _renderHeader: function () {
//         var $thead = this._super.apply(this, arguments);
//         if (this.addTrashIcon && !(this.isMany2Many)) {
//             $thead.find('tr').prepend($('<th>', {class: 'o_list_record_copy_header'}));
//         }
//         return $thead;
//     },

//     _renderRow: function (record, index) {
//         var $row = this._super.apply(this, arguments);
//         if (this.addTrashIcon && !(this.isMany2Many)) {
//             var $icon = $('<button>', {'class': 'fa fa-clone', 'name': 'copy', 'aria-label': _t('Copy row ') + (index + 1)});
//             var $td = $('<td>', {class: 'o_list_record_copy'}).append($icon);
//             $row.prepend($td);
//         }
//         return $row;
//     },

// });

});
