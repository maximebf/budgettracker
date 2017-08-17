import os, json, inspect, unicodecsv, codecs, datetime, re
from .data import Account, Transaction, period_to_months, filter_transactions_period


def get_storage(name):
    for o in globals().values():
        if inspect.isclass(o) and issubclass(o, StorageBase) and o is not StorageBase and o.name == name:
            return o


class StorageBase(object):
    def __init__(self, config):
        self.config = config

    def load_accounts(self):
        raise NotImplementedError

    def save_accounts(self, accounts):
        raise NotImplementedError

    def load_monthly_transactions(self, date):
        raise NotImplementedError

    def save_monthly_transactions(self, date, transactions):
        raise NotImplementedError

    def load_period_transactions(self, start_date, end_date):
        transactions = []
        for date in period_to_months(start_date, end_date):
            transactions.extend(self.load_monthly_transactions(date))
        return filter_transactions_period(transactions, start_date, end_date)

    def load_yearly_transactions(self, date):
        start_date = date.replace(day=1, month=1)
        end_date = start_date.replace(year=start_date.year+1)
        return self.load_period_transactions(start_date, end_date)

    def iter_months(self):
        raise NotImplementedError

    def iter_monthly_transactions_for_update(self, date, iterator):
        transactions = filter(bool, map(iterator, self.load_monthly_transactions(date)))
        self.save_monthly_transactions(date, transactions)

    def iter_all_transactions_for_update(self, iterator):
        for date in self.iter_months():
            self.iter_monthly_transactions_for_update(date, iterator)

    def update_transaction(self, date, id, **kwargs):
        def iterator(tx):
            if tx.id == id:
                return tx.update(**kwargs)
            return tx
        self.iter_monthly_transactions_for_update(date, iterator)


class FileStorageBase(StorageBase):
    extension = None

    @property
    def directory(self):
        path = self.config.get('storage_dir', os.environ.get('BUDGET_DIR', '.'))
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def get_accounts_filename(self):
        filename = 'accounts.%s' % self.extension
        if self.directory:
            filename = os.path.join(self.directory, filename)
        return filename

    def get_monthly_transactions_filename(self, date):
        filename = date.replace(day=1).strftime("%Y-%m.{0}".format(self.extension))
        if self.directory:
            filename = os.path.join(self.directory, filename)
        return filename

    def load_transactions(self, filename):
        raise NotImplementedError

    def save_transactions(self, transactions, filename):
        raise NotImplementedError

    def load_monthly_transactions(self, date):
        return self.load_transactions(self.get_monthly_transactions_filename(date))

    def save_monthly_transactions(self, date, transactions):
        self.save_transactions(transactions, self.get_monthly_transactions_filename(date))

    def iter_months(self):
        for filename in os.listdir(self.directory):
            pathname = os.path.join(self.directory, filename)
            if not os.path.isfile(pathname) or not re.match(r"[0-9]{4}-[0-9]{2}\.%s" % self.extension, filename):
                continue
            yield datetime.date(*map(int, filename.split('.')[0].split('-') + [1]))


class CSVStorage(FileStorageBase):
    name = 'csv'
    extension = 'csv'

    def load_accounts(self):
        filename = self.get_accounts_filename()
        if not os.path.exists(filename):
            return []
        with codecs.open(filename) as f:
            return map(self._csv_row_to_account, unicodecsv.reader(f))

    def load_transactions(self, filename):
        if not os.path.exists(filename):
            return []
        with codecs.open(filename) as f:
            return map(self._csv_row_to_transaction, unicodecsv.reader(f))

    def save_accounts(self, accounts):
        with codecs.open(self.get_accounts_filename(), 'w') as f:
            writer = unicodecsv.writer(f)
            for acc in accounts:
                writer.writerow(acc)

    def save_transactions(self, transactions, filename):
        with codecs.open(filename, 'w') as f:
            writer = unicodecsv.writer(f)
            for tx in transactions:
                writer.writerow(self._transaction_to_csv_row(tx))

    def _csv_row_to_account(self, row):
        return Account(row[0], row[1], float(row[2]))

    def _csv_row_to_transaction(self, row):
        return Transaction(row[0], row[1], datetime.datetime.strptime(row[2], "%Y-%m-%d").date(),
            float(row[3]), row[4], filter(unicode.strip, row[5].split(',')), row[6] or None)

    def _transaction_to_csv_row(self, tx):
        return [tx.id, tx.label, tx.date.isoformat(), tx.amount, tx.account, ', '.join(tx.categories), tx.goal]


class JSONStorage(FileStorageBase):
    name = 'json'
    extension = 'json'

    def load_accounts(self):
        filename = self.get_accounts_filename()
        if not os.path.exists(filename):
            return []
        with codecs.open(filename) as f:
            return json.load(f, object_hook=lambda dct: Account.from_dict(dct))

    def load_transactions(self, filename):
        if not os.path.exists(filename):
            return []
        with codecs.open(filename) as f:
            return json.load(f, object_hook=lambda dct: Transaction.from_dict(dct))

    def save_accounts(self, accounts):
        with codecs.open(self.get_accounts_filename(), 'w') as f:
            json.dump(map(lambda acc: acc.to_dict(), accounts), f, indent=2)

    def save_transactions(self, transactions, filename):
        with codecs.open(filename, 'w') as f:
            json.dump(map(lambda tx: tx.to_dict(), transactions), f, indent=2)
