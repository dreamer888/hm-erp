##############################################################################
#    This file is part of hmERP
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    "name": "hmERP库存管理",
    "version": '13.0',
    "author": 'ZhengXiang',
    "website": "http://www.dreammm.net",
    "category": "hmERP",
    "depends": ['core', 'goods', 'money', 'barcodes'],
    "description":
    '''
        该模块实现了 hmERP 中 仓库管理的功能。

        通过创建或者处理销售发货单/销售退货单，来完成出/入库。
        通过创建或者处理采购入库单/采购退货单，来完成入/出库。
        通过创建其他出入库单，来完成其他出入库的流程。
        通过创建组装/拆卸单，来完成商品的生产。
        通过创建盘点单，完成仓库中商品的实际库存数量与账面库存数量的比较和调整。

        仓库管理的报表有：
        库存余额表；
        商品收发明细表；
        批次余额表；
        库存调拨；
        库龄报表。
    ''',
    "data": [
        'data/warehouse_data.xml',
        'security/groups.xml',
        'security/rules.xml',
        'wizard/save_bom_view.xml',
        'wizard/stock_transceive_wizard_view.xml',
        'wizard/non_active_report_wizard.xml',
        'view/assets_backend.xml',
        'view/warehouse_view.xml',
        'view/inventory_view.xml',
        'view/production_view.xml',
        'view/res_company.xml',
        'view/qc_rule.xml',
        'view/goods_reference_black_list_view.xml',
        'report/report_data.xml',
        'report/stock_balance_view.xml',
        'report/stock_transceive_view.xml',
        'report/lot_status_view.xml',
        'action/warehouse_action.xml',
        'menu/warehouse_menu.xml',
        'data/sequence.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'data/warehouse_demo.xml',
    ],
}
