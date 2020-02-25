from core import translate, load_model
from flask import Flask, render_template, request
from wtforms import Form, TextAreaField, validators
import sqlite3
import os

app = Flask(__name__)

MODEL_DIR = '.'

cur_dir = os.path.dirname(__file__)
db = os.path.join(cur_dir, 'trReviews.sqlite')

def sqlite_entry(path, original_text, translation_suggested):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("INSERT INTO trReviews (date, OriginalText, TranslationSuggested)"\
    " VALUES (DATETIME('now'), ?, ?)", (original_text, translation_suggested))
    conn.commit()
    conn.close()

class ReviewForm(Form):
    TRreview = TextAreaField('',
                             [validators.DataRequired(),
                             validators.length(min=15)])

@app.before_first_request
def loading():
    global confo
    confo = load_model(".")


@app.route("/")
def index():
    form = ReviewForm(request.form)
    return render_template('index.html', predict=False)

@app.route("/results", methods=['POST'])
def results():
    form = ReviewForm(request.form)
    if request.method == 'POST':
        message = request.form["message"]
        answer = translate(message, **confo)
        return render_template('results.html', predict=True, answer=answer, message=message)
    else:
        return render_template('results.html', predict=False)

@app.route("/thanks", methods=["POST"])
def feedback():

    feedback = request.form['feedback_button']
    
    if feedback == 'Correct':
        print("Correct translation")
    return render_template('thanks.html')

@app.route("/reviews", methods=["POST"])
def reviews():

    feedback = request.form['feedback_button']
    review = request.form['review']

    if feedback == 'Incorrect':
        print("Incorrect translation")    
    
    return render_template('reviews.html', review=review)

@app.route("/reviews-thanks", methods=["POST"])
def contribution():
    form = ReviewForm(request.form)
    review = request.form['review']
    if request.method == 'POST':
        correction = request.form['correction']
	
    sqlite_entry(db, review, correction) 
    return render_template("reviews-thanks.html")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
