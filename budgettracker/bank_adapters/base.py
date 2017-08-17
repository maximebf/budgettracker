import json, requests, os, time, uuid, re, inspect
from importlib import import_module
from ..data import Account, Transaction
from ..categories import Category, match_categories


def get_bank_adapter(name):
    module = import_module('budgettracker.bank_adapters.' + name)
    for obj in module.__dict__.values():
        if inspect.isclass(obj) and issubclass(obj, BankAdapter) and obj is not BankAdapter:
            return obj


class BankAdapter(object):
    fetch_type = 'file'

    def __init__(self, config, filename=None):
        self.config = config
        self.filename = filename

    @property
    def categories(self):
        if not self.__dict__.get('categories'):
            self.__dict__['categories'] = map(Category.from_dict, self.config.get('categories', []))
        return self.__dict__['categories']

    def fetch_transactions_from_all_accounts(self, start_date=None, end_date=None):
        transactions = []
        for account in self.fetch_accounts():
            transactions.extend(self.fetch_transactions(account, start_date, end_date))
        return sorted(transactions, key=lambda i: i.date, reverse=True)

    def create_request_session(self, reuse=True, filename='session.json'):
        if reuse and getattr(self, 'request_session_cache', None):
            return self.request_session_cache

        session = requests.Session()
        exp = time.time() - 1800 # cookie jar expires after 30min
        if reuse and os.path.exists(filename) and os.path.getmtime(filename) > exp:
            with open(filename) as f:
                cookies = json.load(f)
            session.cookies.update(cookies)
        else:
            self.login(session)
            with open(filename, 'w') as f:
                json.dump(session.cookies.get_dict(), f)

        self.request_session_cache = session
        return session

    def make_transaction(self, **kwargs):
        if not kwargs.get('id'):
            kwargs['id'] = str(uuid.uuid4())
        kwargs['label'] = re.sub("\s+", " ", kwargs['label'].replace("\n", " ").strip())
        kwargs.setdefault('categories', match_categories(self.categories, kwargs['label']))
        kwargs.setdefault('goal', None)
        return Transaction(**kwargs)