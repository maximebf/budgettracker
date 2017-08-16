from flask import Flask, render_template, jsonify, request, session, redirect, url_for, abort
from werkzeug.utils import secure_filename
from monthdelta import monthdelta
import datetime, functools, json, unicodecsv, StringIO, os
from ..budget import IncomeSource, RecurringExpense, SavingsGoal, Category
from ..utils import CONFIG_FILENAME, load_config, load_adapter
from ..helpers import (budgetize_from_config, load_yearly_budgets_from_config,
                       load_monthly_budget_from_config, load_accounts_from_config, update_local_data,
                       load_monthly_transactions, dump_transactions, get_monthly_transactions_filename,
                       compute_yearly_savings_goals_from_config, compute_monthly_categories_from_config)


app = Flask(__name__)
config = load_config()
bank_adapter = load_adapter('bank_adapters', config['bank_adapter'])
app.config['SECRET_KEY'] = config['web_passcode']
app.config['CURRENCY'] = config.get('currency', '$')
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

    accounts = load_accounts_from_config(config)
    budgets = load_yearly_budgets_from_config(config, date)
    categories = compute_monthly_categories_from_config(config, date)
    category_colors = {c.name: c.color for c in categories}
    savings_goals = compute_yearly_savings_goals_from_config(config, date)

    return render_template('index.html',
        date=date,
        prev_date=(date - monthdelta(1)),
        next_date=(date + monthdelta(1)) if date < current else None,
        accounts=accounts,
        account_balance=sum([a.amount for a in accounts]),
        budgets=budgets,
        budget=budgets.get_from_date(date),
        max=max,
        bank_adapter=bank_adapter,
        categories=categories,
        category_colors=category_colors,
        savings_goals=savings_goals)


@app.route('/<int:year>-<int:month>/budget.json')
@requires_passcode
def budget(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date)
    return jsonify(**budget.to_dict(with_transactions=False))


@app.route('/<int:year>-<int:month>/transactions.json')
@requires_passcode
def transactions(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date)
    return jsonify(map(lambda tx: tx.to_dict(), budget.transactions))


@app.route('/<int:year>-<int:month>/transactions.csv')
@requires_passcode
def transactions_csv(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date)
    out = StringIO.StringIO()
    writer = unicodecsv.writer(out)
    for tx in budget.transactions:
        writer.writerow(tx)
    return out.getvalue(), {"Content-Disposition": "attachment; filename=%s-%s.csv" % (year, month),
                 "Content-Type": "text/csv"}


@app.route('/<int:year>-<int:month>/<transaction_id>', methods=['POST'])
def update_transaction(year, month, transaction_id):
    date = datetime.date(year, month, 1)
    categories = request.form.getlist('categories')
    goal = request.form.get('goal')
    transactions = load_monthly_transactions(date, directory=config.get('data_dir'))
    final = []
    new_tx = None
    for tx in transactions:
        if tx.id == transaction_id:
            new_tx = tx.update(categories=categories, goal=goal)
            final.append(new_tx)
        else:
            final.append(tx)
    if not new_tx:
        abort(404)
    dump_transactions(final, get_monthly_transactions_filename(date, config.get('data_dir')))
    return jsonify(**new_tx.to_dict())


@app.route('/update', methods=['POST'])
@requires_passcode
def update():
    filename = None
    if bank_adapter.ADAPTER_TYPE == 'file':
        if 'file' not in request.files:
            abort(400)
        file = request.files['file']
        filename = os.path.join(config.get('imports_dir', '.'), secure_filename(file.filename))
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        file.save(filename)
    update_local_data(config, filename=filename)
    return redirect(url_for('index'))


@app.route('/config', methods=['GET', 'POST'])
@requires_passcode
def edit_config():
    global config
    if request.method == 'POST':
        date_cast = lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date() if d else ''
        color_cast = lambda c: '#%s' % c if not c.startswith('#') else c
        income_sources = map(lambda a: IncomeSource(*a), zip(
            request.form.getlist('income_sources_label'),
            request.form.getlist('income_sources_amount', float),
            request.form.getlist('income_sources_match'),
            request.form.getlist('income_sources_from_date', date_cast),
            request.form.getlist('income_sources_to_date', date_cast)))
        recurring_expenses = map(lambda a: RecurringExpense(*a), zip(
            request.form.getlist('recurring_expenses_label'),
            request.form.getlist('recurring_expenses_amount', float),
            request.form.getlist('recurring_expenses_recurrence'),
            request.form.getlist('recurring_expenses_match'),
            request.form.getlist('recurring_expenses_from_date', date_cast),
            request.form.getlist('recurring_expenses_to_date', date_cast)))
        savings_goals = map(lambda a: SavingsGoal(*a), zip(
            request.form.getlist('savings_goals_label'),
            request.form.getlist('savings_goals_amount', float)))
        categories = map(lambda a: Category(*a), zip(
            request.form.getlist('categories_name'),
            request.form.getlist('categories_color', color_cast)))

        app.logger.debug(recurring_expenses)
        app.logger.debug(map(lambda e: e.to_dict(), recurring_expenses))

        config.update(
          income_sources=map(lambda s: s.to_dict(), income_sources),
          recurring_expenses=map(lambda e: e.to_dict(), recurring_expenses),
          savings_goals=map(lambda g: g.to_dict(), savings_goals),
          categories=map(lambda c: c.to_dict(), categories))

        app.logger.debug(config)

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
        savings_goals=map(SavingsGoal.from_dict, config.get('savings_goals', [])),
        categories=map(Category.from_dict, config.get('categories', [])))
