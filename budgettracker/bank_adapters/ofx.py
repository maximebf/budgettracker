from budgettracker.data import Account, Transaction
import ofxparse, re
from ofxparse import OfxParser


ADAPTER_TYPE = 'file'


def _parseofx(session):
    if isinstance(session, ofxparse.ofxparse.Ofx):
        return session
    return OfxParser.parse(session)


def _get_ofx_account(ofx, account_id):
    for account in ofx.accounts:
        if account.account_id == account_id:
            return account


def fetch_accounts(session):
    ofx = _parseofx(session)
    for account in ofx.accounts:
        yield Account(id=str(account.account_id),
                      title="%s %s" % (account.account_type, account.account_id),
                      amount=float(account.statement.balance))


def fetch_transactions(session, account, start_date=None, end_date=None):
    ofx = _parseofx(session)
    ofx_account = _get_ofx_account(ofx, account.id)
    transactions = []

    for tx in ofx_account.statement.transactions:
        if (start_date and start_date > tx.date.date()) or (end_date and end_date <= tx.date.date()):
            continue
        transactions.append(Transaction(
            id=str(tx.id),
            label="%s %s" % (re.sub("\s+", " ", tx.payee.strip()), re.sub("\s+", " ", tx.memo.strip())),
            date=tx.date.date(),
            amount=float(tx.amount),
            account=str(account.id)))

    return transactions


def fetch_transactions_from_all_accounts(session, start_date=None, end_date=None):
    session = _parseofx(session)
    transactions = []
    for account in fetch_accounts(session):
        transactions.extend(fetch_transactions(session, account, start_date, end_date))
    return sorted(transactions, key=lambda i: i.date, reverse=True)