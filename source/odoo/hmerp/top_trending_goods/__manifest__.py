
{
    'name': '产品分级',
    'version': '13.0.0.1',
    'summary': '按销售排行对产品进行分级',
    'category': 'Hidden',
    'author': '信莱德软件',
    'website': 'https://zhsunlight.cn',
    'depends': ['sell'],
    'description':
    '''
产品分级
===========================================

 * 1. 高利润高销售额产品

 * 2. 低利润高销售额产品

 * 3. 高利润低销售额产品

 * 4. 低利润低销售额产品

 * 利润：取利润率，产品上的 （销售价-成本）/ 销售价

 * 销售额：取当前日前前三个月的销售发货量汇总

 * graph显示前三个月销量

 * 按前三个月利润贡献总额倒序排序
    ''',
    'data': [
        'views/goods_view.xml',
        'data/data.xml',
    ],
    'installable': True,
    'application': False,
}
