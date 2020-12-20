from flask import *
import pymongo
from pprint import pprint

app = Flask(__name__)
mgclient = pymongo.MongoClient("mongodb+srv://admin:qwep-]123p=]@cluster0.sax3u.mongodb.net/Cluster0?retryWrites=true&w=majority")


@app.route('/')
def hello_world():
    data = mgclient.issues_data.issues.find({})
    # pprint(data)
    return render_template("main.html", marks=data)


if __name__ == '__main__':
    app.run()
