from base import *
from ofxparse import OfxParser
import codecs, re


class OFXAdapter(BankAdapter):
    name = 'OFX'

    def parse_ofx(self):
        if not getattr(self, 'ofx', None):
            with codecs.open(self.filename) as f:
                self.ofx = OfxParser.parse(f)
        return self.ofx

    def get_ofx_account(self, account_id):
        for account in self.parse_ofx().accounts:
            if account.account_id == account_id:
                return account

    def fetch_accounts(self):
        for account in self.parse_ofx().accounts:
            yield Account(id=str(account.account_id),
                          title="%s %s" % (account.account_type, account.account_id),
                          amount=float(account.statement.balance))

    def fetch_transactions(self, account, start_date=None, end_date=None):
        ofx_account = self.get_ofx_account(account.id)
        transactions = []

        for tx in ofx_account.statement.transactions:
            if (start_date and start_date > tx.date.date()) or (end_date and end_date <= tx.date.date()):
                continue
            transactions.append(self.make_transaction(
                id=str(tx.id),
                label="%s %s" % (tx.payee, tx.memo),
                date=tx.date.date(),
                amount=float(tx.amount),
                account=str(account.id)))

        return transactions
