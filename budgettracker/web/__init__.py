from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from monthdelta import monthdelta
import datetime, functools, json, unicodecsv, StringIO
from ..budget import IncomeSource, RecurringExpense, SavingsGoal
from ..helpers import (CONFIG_FILENAME, load_config, make_budget_from_config,
                       load_budget_of_month_from_config, load_balance, update_local_data)


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

    budget = load_budget_of_month_from_config(config, date)
    if not budget and date == current:
        budget = make_budget_from_config([], config)

    return render_template('index.html',
      date=date,
      prev_date=(date - monthdelta(1)),
      next_date=(date + monthdelta(1)) if date < current else None,
      account_balance=load_balance(),
      budget=budget,
      max=max)


@app.route('/<int:year>-<int:month>/budget.json')
@requires_passcode
def budget(year, month):
    date = datetime.date(year, month, 1)
    budget = load_budget_of_month_from_config(config, date)
    return jsonify(real_balance=budget.real_balance,
                   balance=budget.balance,
                   income=budget.income,
                   recurring_expenses=budget.recurring_expenses,
                   expenses=budget.expenses,
                   savings=budget.savings,
                   savings_goal=budget.savings_goal,
                   expected_real_balance=budget.expected_real_balance,
                   expected_balance=budget.expected_balance,
                   expected_income=budget.expected_income,
                   expected_recurring_expenses=budget.expected_recurring_expenses,
                   expected_savings=budget.expected_savings,
                   expected_remaining=budget.expected_remaining)


@app.route('/<int:year>-<int:month>/transactions.json')
@requires_passcode
def transactions(year, month):
    date = datetime.date(year, month, 1)
    budget = load_budget_of_month_from_config(config, date)
    return jsonify(map(lambda tx: tx.to_dict(), budget.transactions))


@app.route('/<int:year>-<int:month>/transactions.csv')
@requires_passcode
def transactions_csv(year, month):
    date = datetime.date(year, month, 1)
    budget = load_budget_of_month_from_config(config, date)
    out = StringIO.StringIO()
    writer = unicodecsv.writer(out)
    for tx in budget.transactions:
        writer.writerow(tx)
    return out.getvalue(), {"Content-Disposition": "attachment; filename=%s-%s.csv" % (year, month),
                 "Content-Type": "text/csv"}


@app.route('/refresh', methods=['POST'])
@requires_passcode
def refresh():
    update_local_data(config)
    return redirect(url_for('index'))


@app.route('/config', methods=['GET', 'POST'])
@requires_passcode
def edit_config():
    global config
    if request.method == 'POST':
        income_sources = map(lambda a: IncomeSource(*a), zip(request.form.getlist('income_sources_label'),
          request.form.getlist('income_sources_amount', float),
          request.form.getlist('income_sources_match')))
        recurring_expenses = map(lambda a: RecurringExpense(*a), zip(request.form.getlist('recurring_expenses_label'),
          request.form.getlist('recurring_expenses_amount', float),
          request.form.getlist('recurring_expenses_recurrence'),
          request.form.getlist('recurring_expenses_match')))
        savings_goals = map(lambda a: SavingsGoal(*a), zip(request.form.getlist('savings_goals_label'),
          request.form.getlist('savings_goals_amount', float)))

        config.update(
          income_sources=map(lambda s: s.to_dict(), income_sources),
          recurring_expenses=map(lambda e: e.to_dict(), recurring_expenses),
          savings_goals=map(lambda g: g.to_dict(), savings_goals))

        try:
            with open(CONFIG_FILENAME, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=2)
            return redirect(url_for('index'))
        except:
            pass

    return render_template('config.html',
        config=config,
        income_sources=map(IncomeSource.from_dict, config.get('income_sources', [])),
        recurring_expenses=map(RecurringExpense.from_dict, config.get('recurring_expenses', [])),
        savings_goals=map(SavingsGoal.from_dict, config.get('savings_goals', [])))
