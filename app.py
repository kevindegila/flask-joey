from core import translate, load_model
from flask import Flask, render_template, request


app = Flask(__name__)

MODEL_DIR = '.'


@app.before_first_request
def loading():
    global confo
    confo = load_model(".")


@app.route("/", methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        message = request.form["message"]
        answer = translate(message, **confo)
        return render_template('index.html', predict=True, answer=answer, message=message)
    else:
        return render_template('index.html', predict=False)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
