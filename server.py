from flask import *
import pymongo
from pprint import pprint

app = Flask(__name__)
mgclient = pymongo.MongoClient("mongodb+srv://admin:qwep-]123p=]@cluster0.sax3u.mongodb.net/Cluster0?retryWrites=true&w=majority")


@app.route('/')
def hello_world():
    data = mgclient.issues_data.issues.find({})
    render_data = []
    for i in data:
        pprint(i)
        i["photo_links"] = i["photo_links"].split(" , ")
        render_data.append(i)
    return render_template("main.html", marks=render_data)


if __name__ == '__main__':
    app.run()
