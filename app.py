
from flask import Flask  

app = Flask(__name__)  

@app.route('/')  
def home():  
    return "Hello, Bro This is The King Server"  

if __name__ == '__main__':  
    app.run(debug=True)
