from flask import Flask, render_template, jsonify, request, session, redirect, url_for, abort
from werkzeug.utils import secure_filename
from monthdelta import monthdelta
from tempfile import NamedTemporaryFile
import datetime, functools, json, unicodecsv, StringIO, os
from ..budget import IncomeSource, PlannedExpense, BudgetGoal
from ..categories import Category
from ..helpers import (load_config, save_config, get_storage_from_config, get_bank_adapter_from_config,
                       load_yearly_budgets_from_config, load_monthly_budget_from_config, update_local_data,
                       compute_yearly_budget_goals_from_config, compute_monthly_categories_from_config,
                       rematch_categories, create_amount_formatter)


app = Flask(__name__)
config = load_config()
storage = get_storage_from_config(config)
bank_adapter = get_bank_adapter_from_config(config)
app.config['SECRET_KEY'] = config.get('web_passcode', 'budgettracker')
app.config.update(config.get('web_config', {}))

months_labels = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']


@app.context_processor
def utility_processor():
    return dict(famount=create_amount_formatter(config))


def requires_passcode(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if config.get('web_passcode') and not session.get('allowed') and (
          not request.authorization or request.authorization.username != config['web_passcode']):
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not config.get('web_passcode'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form['code'] == config.get('web_passcode'):
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

    accounts = storage.load_accounts()
    budgets = load_yearly_budgets_from_config(config, date, storage=storage)
    budget_goals, savings_after_goals = compute_yearly_budget_goals_from_config(config, date, storage=storage)
    categories = compute_monthly_categories_from_config(config, date, storage=storage)
    category_colors = {c.name: c.color for c in categories}
    months = [(i, label) for i, label in enumerate(months_labels)]

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
        budget_goals=budget_goals,
        savings_after_goals=savings_after_goals,
        months=months)


@app.route('/<int:year>-<int:month>/budget.json')
@requires_passcode
def budget(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date, storage=storage)
    return jsonify(**budget.to_dict(with_transactions=False))


@app.route('/<int:year>-<int:month>/transactions.json')
@requires_passcode
def transactions(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date, storage=storage)
    return jsonify(map(lambda tx: tx.to_dict(), budget.transactions))


@app.route('/<int:year>-<int:month>/transactions.csv')
@requires_passcode
def transactions_csv(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date, storage=storage)
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
    storage.update_transaction(date, transaction_id, categories=categories, goal=goal)

    existing_categories = [c['name'] for c in config.get('categories') or []]
    has_new_categories = False
    for category in categories:
        if category not in existing_categories:
            if not config.get('categories'):
                config['categories'] = []
            config['categories'].append({'name': category})
            has_new_categories = True
    if has_new_categories:
        save_config(config)

    return ''


@app.route('/<int:year>-<int:month>', methods=['POST'])
@requires_passcode
def update(year, month):
    date = datetime.date(year, month, 1)
    filename = None
    delete_file = False
    if bank_adapter.fetch_type == 'file':
        if 'file' not in request.files:
            abort(400)
        file = request.files['file']
        if config.get('imports_dir'):
            filename = os.path.join(config['imports_dir'],
                '%s-%s' % (datetime.date.today().isoformat(), secure_filename(file.filename)))
            if not os.path.exists(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
        else:
            temp_file = NamedTemporaryFile(delete=False)
            filename = temp_file.name
            temp_file.close()
            delete_file = True
        file.save(filename)
    update_local_data(config, date=date, filename=filename, storage=storage)
    if delete_file:
        os.unlink(filename)
    return redirect(url_for('index', year=year, month=month))


@app.route('/config', methods=['GET', 'POST'])
@requires_passcode
def edit_config():
    global config
    if request.method == 'POST':
        date_cast = lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date() if d else ''
        color_cast = lambda c: '#%s' % c if not c.startswith('#') else c
        keywords_cast = lambda k: filter(bool, map(unicode.strip, k.split(',')))
        warning_threshold_cast = lambda w: float(w) if w else None
        income_sources = map(lambda a: IncomeSource(*a), zip(
            request.form.getlist('income_sources_label'),
            request.form.getlist('income_sources_amount', float),
            request.form.getlist('income_sources_match'),
            request.form.getlist('income_sources_from_date', date_cast),
            request.form.getlist('income_sources_to_date', date_cast)))
        planned_expenses = map(lambda a: PlannedExpense(*a), zip(
            request.form.getlist('planned_expenses_label'),
            request.form.getlist('planned_expenses_amount', float),
            request.form.getlist('planned_expenses_recurrence'),
            request.form.getlist('planned_expenses_match'),
            request.form.getlist('planned_expenses_from_date', date_cast),
            request.form.getlist('planned_expenses_to_date', date_cast)))
        budget_goals = map(lambda a: BudgetGoal(*a), zip(
            request.form.getlist('budget_goals_label'),
            request.form.getlist('budget_goals_amount', float)))
        categories = map(lambda a: Category(*a), zip(
            request.form.getlist('categories_name'),
            request.form.getlist('categories_color', color_cast),
            request.form.getlist('categories_keywords', keywords_cast),
            request.form.getlist('categories_warning_threshold', warning_threshold_cast)))

        config.update(
          income_sources=map(lambda s: s.to_dict(), income_sources),
          planned_expenses=map(lambda e: e.to_dict(), planned_expenses),
          budget_goals=map(lambda g: g.to_dict(), budget_goals),
          categories=map(lambda c: c.to_dict(), categories))

        save_config(config)
        rematch_categories(config, storage)
        return redirect(url_for('index'))

    return render_template('config.html',
        config=config,
        income_sources=map(IncomeSource.from_dict, config.get('income_sources', [])),
        planned_expenses=map(PlannedExpense.from_dict, config.get('planned_expenses', [])),
        budget_goals=map(BudgetGoal.from_dict, config.get('budget_goals', [])),
        categories=map(Category.from_dict, config.get('categories', [])))
