from base import *
import re, unicodecsv, uuid, datetime, codecs


class CSVAdapter(BankAdapter):
    name = 'CSV'

    def parse_csv(self):
        if not getattr(self, 'csv', None):
            with codecs.open(self.filename) as f:
                self.csv = list(unicodecsv.reader(f))
        return self.csv

    def fetch_accounts(self):
        accounts = {}
        for row in self.parse_csv():
            accounts.setdefault(str(row[4]), 0)
            accounts[str(row[4])] += float(row[3])

        for id, balance in accounts.items():
            yield Account(id=id, title=id, amount=balance)

    def fetch_transactions(self, account, start_date=None, end_date=None):
        transactions = []
        for row in self.parse_csv():
            if row[4] != account.id:
                continue
            date = datetime.datetime.strptime(row[2], '%Y-%m-%d')
            if (start_date and start_date > date) or (end_date and end_date <= date):
                continue
            transactions.append(self.make_transaction(
                id=row[0].strip(),
                label=row[1],
                date=date,
                amount=float(row[3]),
                account=row[4]))

        return transactions
