from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv


app = Flask(__name__)
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
        users.insert_one({'name': name, 'email': email, 'password': password})
        return redirect('/login')

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users.find_one({'email': email, 'password': password})
        if user:
            session['user'] = user['name']
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Wrong email or password!')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    #Fetch livecrypto prices from coingecko API

    import requests
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,cardano&vs_currencies=usd'
    response = requests.get(url)
    data = response.json()

    prices = [
        {'name': 'Bitcoin',  'icon': '₿',  'price': f"{data['bitcoin']['usd']:,}"},
        {'name': 'Ethereum', 'icon': 'Ξ',  'price': f"{data['ethereum']['usd']:,}"},
        {'name': 'Solana',   'icon': '◎',  'price': f"{data['solana']['usd']:,}"},
        {'name': 'BNB',      'icon': '🔶', 'price': f"{data['binancecoin']['usd']:,}"},
        {'name': 'Cardano',  'icon': '🔵', 'price': f"{data['cardano']['usd']:,}"},
    ]

    return render_template('dashboard.html', username=session['user'], prices=prices)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)