
from odoo.models import Model

original_export_data = Model.export_data

def export_report_data(self, fields_to_export):
    """ 导出报表数据.

        :param fields_to_export: list of lists of fields_to_export to traverse
        :return: dictionary with a *datas* matrix
    """

    if not hasattr(self, 'get_data_from_cache'):
        return original_export_data(self, fields_to_export)

    lines = []
    records = self.get_data_from_cache()
    for record in records:
        # main line of record, initially empty
        current = [''] * len(fields_to_export)
        lines.append(current)

        for i, path in enumerate(fields_to_export):
            current[i] = record.get(path) or ''

    return {'datas': lines}

Model.export_data = export_report_data
