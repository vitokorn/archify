import pymongo
from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from uuid import uuid4


app = Flask(__name__)

# Database
client = MongoClient('mongodb://localhost:27017/?readPreference=primary&appname=MongoDB%20Compass&ssl=false')
db = client['archify']


collection = db['users']
userplaylists = db['user_playlists']
collplaylists = db['playlists']
# post = {"_id": uuid4(), "name": "test", "score": 4}
# collection.insert_one(post)


#Routes
from user import routers
from archify import spoti


@app.route('/')
def hello_world():
    l = []
    spot = userplaylists.find({'spotyid':'spotify'})
    for s in spot:
        addurl = 'https://open.spotify.com/playlist/' + s['playlist']
        colplay = collplaylists.find_one({'external_urls': {'spotify':addurl}})
        #colplay = collplaylists.find_one({'external_urls': {'spotify':addurl}},sort=[('timestamp', pymongo.DESCENDING)])
        l.append(colplay)
    l.sort(key=lambda x:x['timestamp'])
    return render_template("home.html", l=l)


@app.route('/playlist-history')
def playlist_history():
    return render_template("playlist-history.html")


if __name__ == '__main__':
    app.run(debug=True, host='192.168.31.179')
