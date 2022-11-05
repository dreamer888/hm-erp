odoo.define('core.multi_row_header', function (require) {
"use strict";

var ListRenderer = require('web.ListRenderer');


ListRenderer.include({

    _renderBody: function () {
        // 删除空行，edit by 信莱德软件，2020.07.14
        var $tbody = this._super.apply(this, arguments);
        if (this.state.data.length<4){
            var $add = $tbody.find("tr td.o_field_x2many_list_row_add").parent();
            $tbody.find("tr:not(.o_data_row)").remove();
            if ($add.length>0){
                $tbody.append($add);
            }
        }
        return $tbody;
    },

    _renderHeader: function () {
        var $header = this._super.apply(this, arguments);

        if ($header.find('[data-merge]').length>0){

            $header.find('th.o_list_record_selector')
            .eq(0)
            .attr('rowspan','2')
            .css({'vertical-align': 'middle'});
            
            _.each($header.find('[data-normal]'), function (el) {
                $(el).attr('rowspan','2');
            });
            
            var $tr = $('<tr>');
            _.each($header.find('[data-merge]'), function (el) {
                var $el = $(el);
                var $th = $('<th>').text($el.data('child-name'));

                if($el.data('name')){
                    $th.attr('data-name', $el.data('name'));
                    $el.removeAttr('data-name');
                }
                if($el.data('original-title')){
                    $th.attr('data-original-title', $el.data('original-title'));
                    $el.removeAttr('data-original-title');
                }
                if($el.attr('aria-sort')){
                    $th.attr('aria-sort', $el.attr('aria-sort'));
                    $el.removeAttr('aria-sort');
                }
                if($el.attr('title')){
                    $th.attr('title', $el.attr('title'));
                    $el.removeAttr('title');
                }
                if($el.attr('class')){
                    $th.attr('class', $el.attr('class'));
                    $el.removeAttr('class');
                }

                $tr.append($th);

                if($el.data('merge')==='True'){
                    $el.remove();
                }
            });
            $header.append($tr);
        }

        return $header;
    },


    _renderHeaderCell: function (node) {
        var $th = this._super.apply(this, arguments);

        if (node.attrs.base_string){
            $th.attr('colspan', node.attrs.colspan);
            $th.text(node.attrs.base_string);
        }

        if (node.attrs.child_name){
            $th.attr('data-child-name', node.attrs.child_name);
            $th.attr('data-merge', node.attrs.merge);
            $th.css({'text-align': 'center','border-bottom':'none'});
        }else{
            $th.attr('data-normal', 'true');
            $th.css({'vertical-align': 'middle'});
        }

        return $th;
    },
    _computeDefaultWidths: function () {
        const isListEmpty = !this._hasVisibleRecords(this.state);
        const relativeWidths = [];
        this.columns.forEach(column => {
            const th = this._getColumnHeader(column);
            if (th.offsetParent === null) {
                relativeWidths.push(false);
            } else {
                const width = this._getColumnWidth(column);
                if (width.match(/[a-zA-Z]/)) { // absolute width with measure unit (e.g. 100px)
                    if (isListEmpty) {
                        th.style.width = width;
                    } else {
                        // If there are records, we force a min-width for fields with an absolute
                        // width to ensure a correct rendering in edition
                        th.style.minWidth = width;
                    }
                    relativeWidths.push(false);
                } else { // relative width expressed as a weight (e.g. 1.5)
                    relativeWidths.push(parseFloat(width, 10));
                }
            }
        });

        // Assignation of relative widths
        if (isListEmpty) {
            const totalWidth = this._getColumnsTotalWidth(relativeWidths);
            for (let i in this.columns) {
                if (relativeWidths[i]) {
                    const th = this._getColumnHeader(this.columns[i]);
                    // th.style.width = (relativeWidths[i] / totalWidth * 100) + '%';
                    th.style.minWidth = '80px';
                }
            }
            // Manualy assigns trash icon header width since it's not in the columns
            const trashHeader = this.el.getElementsByClassName('o_list_record_remove_header')[0];
            if (trashHeader) {
                trashHeader.style.width = '32px';
            }
        }
    }
});

});
