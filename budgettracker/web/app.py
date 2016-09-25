from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import datetime
from ..utils import load_config, load_budget_from_config, load_balance
from ..data import transaction_to_dict
from monthdelta import monthdelta
import functools


app = Flask(__name__)
config = load_config()
app.config['SECRET_KEY'] = config['web_passcode']
app.config.update(config.get('web_config', {}))


def requires_passcode(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('allowed') and (not request.authorization or request.authorization.username != config['web_passcode']):
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['code'] == config['web_passcode']:
            session['allowed'] = True
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'allowed' in session:
        del session['allowed']
    return redirect(url_for('index'))


@app.route('/')
@app.route('/<int:year>-<int:month>')
@requires_passcode
def index(year=None, month=None):
    current = datetime.date.today().replace(day=1)
    if year:
        date = datetime.date(year, month, 1)
    else:
        date = current
    budget, adapter, session = load_budget_from_config(config, date)
    return render_template('index.html',
      date=date,
      prev_date=(date - monthdelta(1)),
      next_date=(date + monthdelta(1)) if date < current else None,
      balance=load_balance(adapter, session),
      budget=budget)


@app.route('/<int:year>-<int:month>/budget.json')
@requires_passcode
def budget(year, month):
    date = datetime.date(year, month, 1)
    budget, _, __ = load_budget_from_config(config, date)
    return jsonify(balance=budget.balance,
                   income=budget.income,
                   recurring_expenses=budget.recurring_expenses,
                   available=budget.available,
                   expenses=budget.expenses,
                   savings=budget.savings,
                   savings_goal=budget.savings_goal,
                   remaining=budget.remaining)


@app.route('/<int:year>-<int:month>/transactions.json')
@requires_passcode
def transactions(year, month):
    date = datetime.date(year, month, 1)
    budget, _, __ = load_budget_from_config(config, date)
    return jsonify(map(transaction_to_dict, budget.transactions))