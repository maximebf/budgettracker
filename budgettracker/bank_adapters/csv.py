from budgettracker.data import Account, Transaction
import re, unicodecsv, uuid, datetime


ADAPTER_TYPE = 'file'


def _parsecsv(session):
    if isinstance(session, list):
        return session
    return list(unicodecsv.reader(session))


def fetch_accounts(session):
    csv = _parsecsv(session)
    accounts = {}
    for row in csv:
        accounts.setdefault(str(row[4]), 0)
        accounts[str(row[4])] += float(row[3])

    for id, balance in accounts.items():
        yield Account(id=id, title=id, amount=balance)


def fetch_transactions(session, account, start_date=None, end_date=None):
    csv = _parsecsv(session)
    transactions = []

    for row in csv:
        if row[4] != account.id:
            continue
        date = datetime.datetime.strptime(row[2], '%Y-%m-%d')
        if (start_date and start_date > date) or (end_date and end_date <= date):
            continue
        id = row[0].strip()
        if not id:
            id = str(uuid.uuid4()).split('-')[0]
        transactions.append(Transaction(
            id=id,
            label=re.sub("\s+", " ", row[1].replace("\n", " ").strip()),
            date=date,
            amount=float(row[3]),
            account=row[4]))

    return transactions


def fetch_transactions_from_all_accounts(session, start_date=None, end_date=None):
    session = _parsecsv(session)
    transactions = []
    for account in fetch_accounts(session):
        transactions.extend(fetch_transactions(session, account, start_date, end_date))
    return sorted(transactions, key=lambda i: i.date, reverse=True)