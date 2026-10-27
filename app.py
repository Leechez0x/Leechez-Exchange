from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit
import threading, time
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv


app = Flask(__name__)
socketio = SocketIO(app)
latest_prices = {}
app.secret_key = 'leechez_secret_key'

client = MongoClient(os.getenv('MONGO_URI'), tls=True, tlsAllowInvalidCertificates=True)
db = client['Leechex_Exchange']
users = db['users']



@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        #checking if email already exists
        existing_user = users.find_one({'email': email})
        if existing_user:
            return render_template('signup.html', error='Email already registered!')

        #Save new users to MongoDB
        users.insert_one({'name': name, 'email': email, 'password': generate_password_hash(password)})
        return redirect('/login')

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user'] = user['name']
            session['email'] = user['email']
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Wrong email or password!')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    #Fetch livecrypto prices from coingecko API

    data = latest_prices
    coin_map = {
        'bitcoin':     {'name': 'Bitcoin',  'symbol': 'BTC', 'icon': '₿'},
        'ethereum':    {'name': 'Ethereum', 'symbol': 'ETH', 'icon': 'Ξ'},
        'solana':      {'name': 'Solana',   'symbol': 'SOL', 'icon': '◎'},
        'binancecoin': {'name': 'BNB',      'symbol': 'BNB', 'icon': '🔶'},
        'cardano':     {'name': 'Cardano',  'symbol': 'ADA', 'icon': '🔵'},
    }

    prices = []
    for c in coin_map:
        try:
            prices.append({
                'id': c,
                'name': coin_map[c]['name'],
                'symbol': coin_map[c]['symbol'],
                'icon': coin_map[c]['icon'],
                'price': f"{data[c]['usd']:,}"
            })
        except KeyError:
            prices.append({
                'id': c,
                'name': coin_map[c]['name'],
                'symbol': coin_map[c]['symbol'],
                'icon': coin_map[c]['icon'],
                'price': 'N/A'
            })
    # Load this user's holdings from MongoDB
    user_holdings = list(db['holdings'].find({'email': session['email']}))
    holdings_display = []
    total_value = 0

    for h in user_holdings:
        current = data.get(h['coin'], {}).get('usd', 0)
        value = round(h['amount'] * current, 2)
        pl = round((current - h['bought_at']) * h['amount'], 2)
        total_value += value
        holdings_display.append({
            'id': str(h['_id']),
            'coin_name': coin_map[h['coin']]['name'],
            'amount': h['amount'],
            'bought_at': h['bought_at'],
            'current_price': f"{current:,}",
            'value': f"{value:,}",
            'pl': pl,
        })

    return render_template('dashboard.html',
        username=session['user'],
        prices=prices,
        holdings=holdings_display,
        total_value=f"{round(total_value, 2):,}"
    )

@app.route('/add_holding', methods=['POST'])
def add_holding():
    if 'user' not in session:
        return redirect('/login')
    coin = request.form['coin']
    amount = float(request.form['amount'])
    bought_at = float(request.form['bought_at'])
    db['holdings'].insert_one({
        'email': session['email'],
        'coin': coin,
        'amount': amount,
        'bought_at': bought_at
    })
    return redirect('/dashboard')

@app.route('/delete_holding/<id>')
def delete_holding(id):
    from bson import ObjectId
    db['holdings'].delete_one({'_id': ObjectId(id)})
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


def background_prices():
    global latest_prices          # tells Python we're updating the global variable
    while True:
        import requests
        url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,cardano&vs_currencies=usd'
        response = requests.get(url).json()
        if 'bitcoin' in response:  # only update if API returned valid data
            latest_prices = response
        socketio.emit('price_update', latest_prices)
        time.sleep(5)

thread = threading.Thread(target=background_prices)
thread.daemon = True
thread.start()

if __name__ == '__main__':
    socketio.run(app, debug=True)