from base import *
from ..data import update_accounts, update_transactions


class MultiAdapter(BankAdapter):
    name = 'Multiple adapters'

    @property
    def adapters(self):
        for name in self.config.get('bank_adapters', []):
            yield get_bank_adapter(name)(self.config, self.filename)

    @property
    def fetch_type(self):
        for adapter in self.adapters:
            if adapter.fetch_type == 'file':
                return 'file'
        return 'web'

    def fetch_accounts(self):
        accounts = []
        for adapter in self.adapters:
            accounts = update_accounts(accounts, list(adapter.fetch_accounts()))
        return accounts

    def fetch_transactions(self, account, start_date=None, end_date=None):
        transactions = []
        for adapter in self.adapters:
            transactions = update_transactions(transactions, adapter.fetch_transactions(account, start_date, end_date))
        return transactions