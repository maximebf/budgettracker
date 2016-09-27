from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from monthdelta import monthdelta
import datetime, functools, json
from ..helpers import CONFIG_FILENAME, load_config, load_budget_of_month_from_config, load_balance, update_local_data


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
    return render_template('index.html',
      date=date,
      prev_date=(date - monthdelta(1)),
      next_date=(date + monthdelta(1)) if date < current else None,
      account_balance=load_balance(),
      budget=load_budget_of_month_from_config(config, date),
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


@app.route('/refresh', methods=['POST'])
def refresh():
    update_local_data(config)


@app.route('/config', methods=['GET', 'POST'])
@requires_passcode
def edit_config():
    global config
    if request.method == 'POST':
        try:
            config = json.loads(request.form['config'])
            with open(CONFIG_FILENAME, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=True)
            return redirect(url_for('index'))
        except:
            pass
    return render_template('config.html', config=json.dumps(config, indent=2, sort_keys=True))