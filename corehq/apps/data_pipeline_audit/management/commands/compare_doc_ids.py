from itertools import izip_longest

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.data_pipeline_audit.dbacessors import get_es_user_ids, get_es_form_ids, get_primary_db_form_ids, \
    get_primary_db_case_ids, get_es_case_ids
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain
from corehq.util.markup import SimpleTableWriter, CSVRowFormatter, TableRowFormatter
from couchforms.models import doc_types


class Command(BaseCommand):
    help = "Print doc IDs that are in the primary DB but not in ES. Use in conjunction with 'raw_doc' view."
    args = '<domain> <doc_type>'

    def add_arguments(self, parser):
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domain, doc_type, **options):
        csv = options.get('csv')

        handlers = {
            'CommCareCase': _compare_cases,
            'CommCareCase-Deleted': _compare_cases,
            'CommCareUser': _compare_mobile_users,
            'WebUser': _compare_web_users,
        }
        handlers.update({doc_type: _compare_xforms for doc_type in doc_types()})
        try:
            primary_only, es_only = handlers[doc_type](domain, doc_type)
        except KeyError:
            raise CommandError('Unsupported doc type. Use on of: {}'.format(', '.join(handlers)))

        if csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter([50, 50])

        writer = SimpleTableWriter(self.stdout, row_formatter)
        writer.write_table(
            ['Only in Primary', 'Only in ES'],
            izip_longest(primary_only, es_only, fillvalue='')
        )


def _compare_cases(domain, doc_type):
    primary_ids = get_primary_db_case_ids(domain, doc_type)
    es_ids = get_es_case_ids(domain, doc_type)
    return primary_ids - es_ids, es_ids - primary_ids


def _compare_xforms(domain, doc_type):
    primary_ids = get_primary_db_form_ids(domain, doc_type)
    es_ids = get_es_form_ids(domain, doc_type)
    return primary_ids - es_ids, es_ids - primary_ids


def _compare_mobile_users(domain, doc_type):
    primary_ids = set(get_all_user_ids_by_domain(domain, include_web_users=False))
    es_ids = get_es_user_ids(domain, doc_type)
    return primary_ids - es_ids, es_ids - primary_ids


def _compare_web_users(domain, doc_type):
    primary_ids = set(get_all_user_ids_by_domain(domain, include_mobile_users=False))
    es_ids = get_es_user_ids(domain, doc_type)
    return primary_ids - es_ids, es_ids - primary_ids
