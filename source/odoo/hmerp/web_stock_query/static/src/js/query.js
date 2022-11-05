odoo.define('web.stock_query', function(require) {
    "use strict";
    var rpc = require('web.rpc');
    var SystrayMenu = require('web.SystrayMenu');
    var Widget = require('web.Widget');
    var Core = require('web.core');

    var PivotController = require('web.PivotController');
    var ControlPanelRenderer = require('web.ControlPanelRenderer');

    var StockQuery = Widget.extend({
         template: 'web_stock_query.stock_query',
         events: _.extend({}, Widget.prototype.events, {
        }),
        start: function () {
            this.$input = this.$('input');
            this._super.apply(this, arguments);
            this.show_stock_query();
            this.$board = false;
        },
        show_stock_query: function() {            
            var self = this,
                $input = self.$('input'),
                $destroy = self.$('.destroy'),
                $query = self.$();

            $input.on('focus', function(event) {
                $input.addClass('editable');
                if ($input.val() !== '' && self.$board) self.$board.fadeIn('fast');
            }).on('blur', function(event) {
                if ($input.val() === '') {
                    $input.removeClass('editable');
                }
                self.hide_query_board();
            }).on('input', function(event) {
                if ($input.val() === '') { 
                    $destroy.fadeOut('fast');
                    self.hide_query_board();
                } else {
                    $destroy.fadeIn('fast');
                    self.show_query_board($input);
                }
            }).on('keydown', function(event) {
                switch (event.which) {
                    case $.ui.keyCode.ENTER:
                        self.select_query();
                        break;
                    case $.ui.keyCode.DOWN:
                        self.query_board_move('down');
                        event.preventDefault();
                        break;
                    case $.ui.keyCode.UP:
                        self.query_board_move('up');
                        event.preventDefault();
                        break;
                }
            });
            $query.on('mousedown', '.search-to-stock', function(event) {
                self.select_query($(this));
            }).on('mousedown', '.search-to-form', function(event) {
                self.select_query_form($(this));
            }).on('mousedown', '.search-list-more', function(event) {
                self.open_report_stock_balance();
            }).on('mouseover', '.stock-query-search-list li', function(event) {
                self.query_board_move($(this));
            }).on('click', '.destroy', function(event) {           
                $input.val('');
                $input.focus();
                $destroy.fadeOut('fast');
            });

            $('.oe_systray').before(self);
        },

        show_query_board: function($input) {
            var self = this;

            rpc.query({
                model: 'goods',
                method: 'name_search',
                args: [$input.val()],
            })
            .then(function(results){                
                if (results.length <= 0) return self.hide_query_board();

                self.$board = $(Core.qweb.render('web_stock_query.search_list', {'values': _.map(results, function(result) {
                    return {id: result[0], name: result[1]};
                })}));

                self.$board.attr('top', $input.height() + 2 + 'px');
                $input.parent().find('.stock-query-search-list').html(self.$board);
            });
        },

        hide_query_board: function() {
            if (this.$board) this.$board.fadeOut('fast');
        },

        query_board_move: function(direction) {
            if (this.$board) {
                var current_move = this.$board.find('li.select'),
                    next_move = false;
                if (_.contains(['up', 'down'], direction)) {
                    next_move = direction === 'down'? current_move.next(): current_move.prev();
                    if (next_move && next_move.is('li')) {
                        var offset_y = next_move.offset().top - (direction === 'down'? this.$board.height(): 40);
                        this.$board.scrollTop(this.$board.scrollTop() + offset_y);
                    }
                } else if (direction.jquery) {
                    next_move = direction;
                }

                if (next_move && next_move.is('li')) {
                    next_move.addClass('select').siblings('.select').removeClass('select');
                }
            }
        },

        open_report_stock_balance: function() {
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'report.stock.balance',
                views: [[false, 'pivot'], [false, 'list']],
                limit:80000,
                target: 'current',
                name: '库存余额表',
            });
        },

        select_query: function($target) {
            var self = this;
            if (self.$board) {
                $target = $target || self.$board.find('li.select');
                if ($target.hasClass('search-list-more')) {
                    return self.open_report_stock_balance();
                }                  
                self.do_action({
                    type: 'ir.actions.act_window',
                    res_model: 'report.stock.balance',
                    views: [[false, 'pivot']],
                    domain: [['goods_id', '=', $target.data('id')]],
                    target: 'new',
                    name: '搜索：' + $target.text().trim(),
                }, {clear_breadcrumbs: true});
            }
        },
        select_query_form: function($target) {
            var self = this;
            if (self.$board) {
                $target = $target || self.$board.find('li.select');
                // if ($target.hasClass('search-list-more')) {
                //     return self.open_report_stock_balance();
                // }                  
                self.do_action({
                    type: 'ir.actions.act_window',
                    res_model: 'goods',
                    view_type: 'form',
                    views: [[false, 'form']],
                    target: 'current',
                    res_id: $target.data('id'),
                }, {clear_breadcrumbs: true});
            }
        },
    });
    SystrayMenu.Items.push(StockQuery);
    StockQuery.prototype.sequence = 100;

    PivotController.include({
        renderButtons: function ($node) {
            if($node.length>0 && $node[0].tagName!=='FOOTER'){
                return this._super.apply(this, arguments);
            }
        },

    });
    ControlPanelRenderer.include({
        updateContents: function (status, options) {
            var self = this;
            var def = this._super.apply(this, arguments);
            if(self.action.res_model==='report.stock.balance' && self.action.target==='new'){
                self.$el.find('.breadcrumb').parent().css('display','none');
                self.$el.find('.o_cp_right').css('display','none');
            }
            return def;
        },

    })
    return StockQuery;
});

// 增加快捷键支持
$.shortcut = function(key, callback, args) {
    $(document).keydown(function(e) {
        if(!args) args=[]; 
        if((e.keyCode == key) && !e.ctrlKey) {
            callback.apply(this, args);
        }
    });
};

//F8 快捷键，光标移到库存查询框
$.shortcut(119, function() {
    var $input = $('li.my_icon input.o_searchview_input');
    var focused = $input.focus();
    if(!(focused === undefined) && (focused !== false)){
        focused.select();
    }
    
});
