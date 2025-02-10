
from flask import Flask  

app = Flask(__name__)  

@app.route('/')  
def home():  
    return "Hello, Flask on Render , Welcome Babu Shuhana Ab Jao Bol Uss Jhola Chhap ko Tera Server Puri duniya me Live Hai Aasam Me Bhi"  

if __name__ == '__main__':  
    app.run(debug=True)
