import datetime,time
import os

import flask, requests, base64, json, uuid
import pymongo
from flask import request, redirect, jsonify, session, render_template
from pprint import pprint
import urllib.parse
import collections
from app import app, collection,db
app.secret_key = b'jt\xd88\x15\xe9\x0c\x9a\xdc\xdf\x80\xc2\xd06\x0fQ'
client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')

redirect_uri = 'http://localhost:5000/spotify/callback/'
userplaylists = db['user_playlists']
collplaylists = db['playlists']
separator = ", "


class UserPlaylist:
    def __init__(self,
                 spotyid=None,
                 playlist=None,
                 name=None,
                 cron=True,
                 excluded=None):

        self.spotyid = spotyid
        self.playlist = playlist
        self.name = name
        self.cron = cron
        self.excluded = excluded


class Users:
    def __init__(self,
                 spotyid=None,
                 country=None,
                 display_name=None,
                 access_token=None,
                 refresh_token=None):

        self.spotyid = spotyid
        self.country = country
        self.display_name = display_name
        self.access_token = access_token
        self.refresh_token = refresh_token


class ClientCredentials:
    def __init__(self,
                 client_id=None,
                 client_secret=None,
                 grant_type='client_credentials'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.grant_type = grant_type



@app.route('/spotify/auth/')
def auth():
    cc = ClientCredentials(client_id=client_id, client_secret=client_secret)
    url = 'https://accounts.spotify.com/api/token'
    data = {'grant_type': cc.grant_type, 'client_id': cc.client_id, 'client_secret': cc.client_secret}
    req = requests.post(url=url, data=data)
    res = req.json()
    access_token = res['access_token']
    autorization = 'Authorization: Bearer ' + access_token
    return flask.Response(status=200)


@app.route('/spotify/login/')
def authclient():
    url = 'https://accounts.spotify.com/authorize'
    params = {'client_id': client_id, 'client_secret': client_secret, 'redirect_uri': redirect_uri,
              'scope': 'user-library-read user-read-private playlist-read-collaborative playlist-read-private '
                       'playlist-modify-public ugc-image-upload',
              'response_type': 'code', 'show_dialog': True}
    req = requests.get(url=url, params=params)
    return redirect(req.url)


@app.route('/spotify/callback/')
def cod():
    code = request.args.get('code')
    url = 'https://accounts.spotify.com/api/token'
    data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri,'client_id':client_id,
            'client_secret':client_secret}
    req = requests.post(url=url, data=data)
    res = req.json()
    access_token = res['access_token']
    refresh_token = res['refresh_token']
    url = 'https://api.spotify.com/v1/me'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'scope': 'user-read-private user-read-email'
    }
    re = requests.get(url=url, headers=headers)
    recontent = re.content
    t = json.loads(recontent)
    print(t)
    col = {"_id": uuid.uuid4(),"spotyid": t['id'], "country": t['country'], "display_name": t["display_name"],
           "access_token": access_token,
           "refresh_token": refresh_token}
    if collection.find_one({"spotyid":t['id']}):
        spotyid = {"spotyid":t['id']}
        col2 =  {"$set":{"access_token": access_token}}
        collection.update_one(spotyid,col2)
    else:
        collection.insert_one(col)
    session['username'] = t['id']
    session['nickname'] = t['display_name']
    return redirect('/')


@app.route('/spotify/playlist/', methods = ['POST'])
def playlist():
    playlist = request.form.get('playlistid')
    if playlist.startswith('spotify:playlist:'):
        playlist_id = playlist.replace('spotify:playlist:', '')
    elif playlist.startswith('https://open.spotify.com/playlist/'):
        pid = playlist.replace('https://open.spotify.com/playlist/', '').split('?')
        playlist_id = pid[0]
    else:
        return
    print(playlist_id)

    user = collection.find_one({'spotyid':session['username']})
    print(user)
    up = userplaylists.find_one({'spotyid':session['username'], 'playlist': playlist_id})
    if up:
        pass
    else:
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}'
        headers = {
            'Authorization': 'Bearer {}'.format(user['access_token']),
        }
        params = {
            'fields': 'description,external_urls,images(url),name,owner(display_name,external_urls(spotify),id),tracks(items(added_at,added_by,track(album(external_urls,release_date,name),artists(external_urls,name),external_urls,duration_ms,name,preview_url)))'}
        req = requests.get(url=url, params=params, headers=headers)
        if req.status_code == 401:
            refresh()
        playlist = req.json()
        print(playlist)
        if collplaylists.find_one(playlist):
            pass
        else:
            a_dictionary = {"timestamp": datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)}
            playlist.update(a_dictionary)
            collplaylists.insert_one(playlist)
        playl = {'spotyid': session['username'], 'playlist': playlist_id, 'name': playlist['name'], 'cron':True}
        userplaylists.insert_one(playl)
        return redirect('/library/')


@app.route('/spotify/playlists/', methods = ['GET'])
def playlists():
    user = collection.find_one({'spotyid': session['username']})
    offset = 0
    while 1:
        url = f'https://api.spotify.com/v1/me/playlists?offset={offset}&limit=20'
        access_token = user['access_token']
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        all = requests.get(url=url,headers=headers)
        if all.status_code == 401:
            refresh()
        resp = all.json()
        for play in resp['items']:
            playlist = play['uri']
            playlist_id = playlist.replace('spotify:playlist:', '')

            up = userplaylists.find_one({'spotyid':session['username'], 'playlist': playlist_id})
            if up:
                pass
            else:
                url = f'https://api.spotify.com/v1/playlists/{playlist_id}'
                headers = {
                    'Authorization': 'Bearer {}'.format(user['access_token']),
                }
                params = {
                    'fields': 'description,external_urls,images(url),name,owner(display_name,external_urls(spotify),id),tracks(items(added_at,added_by,track(album(external_urls,release_date,name),artists(external_urls,name),external_urls,duration_ms,name,preview_url)))'}
                req = requests.get(url=url, params=params, headers=headers)
                if req.status_code == 401:
                    refresh()
                playlist = req.json()
                print(playlist)
                if collplaylists.find_one(playlist):
                    pass
                else:
                    a_dictionary = {"timestamp": datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)}
                    playlist.update(a_dictionary)
                    collplaylists.insert_one(playlist)
                    playl = {'spotyid': session['username'], 'playlist': playlist_id, 'name': playlist['name'], 'cron':True}
                    userplaylists.insert_one(playl)
        if resp['next'] is None:
            break
        offset += 20
    return redirect('/library/')


@app.route('/spotify/playlists/')
def req():
    user = collection.find_one({'spotyid':session['username']})
    print(user)
    spotyid = user['spotyid']
    access_token = user['access_token']
    url = f'https://api.spotify.com/v1/users/{spotyid}/playlists?offset=0&limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    req = requests.get(url=url, headers=headers)
    playlists = req.json()
    print(playlists)
    for playlist in playlists['items']:
        print(playlist)
        if userplaylists.find_one({'playlist':playlist['id']}):
            pass
        else:
            playl = {'spotyid': session['username'], 'playlist': playlist['id'], 'name': playlist['name'], 'cron':True}
            userplaylists.insert_one(playl)
    return ('Hi')


@app.route('/spotify/playlists/update/')
def update():
    user = collection.find_one({'spotyid':session['username']})

    col = userplaylists.find({'cron':True})
    for c in col:
        playlistc = c['playlist']
        access_token = user['access_token']
        url = f'https://api.spotify.com/v1/playlists/{playlistc}'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        params = {'fields':'description,external_urls,images(url),name,owner(display_name,external_urls(spotify),id),tracks(items(added_at,added_by,track(album(external_urls,release_date,name),artists(external_urls,name),external_urls,duration_ms,name,preview_url,uri)))'}
        req = requests.get(url=url, params=params,headers=headers)
        if req.status_code == 401:
            refresh()
            continue
        r = req.json()
        print(r)
        #search = collplaylists.find_one({'tracks':r['tracks']['items']})
        if collplaylists.find_one(r):
            pass
        else:
            a_dictionary = {"timestamp": datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)}
            r.update(a_dictionary)
            collplaylists.insert_one(r)
    print('Hi')
    alert = {'alert':'successfuly updated'}
    playlists = userplaylists.find({'spotyid':session['username']})
    return render_template('library.html', playlists=playlists,alert=alert)


@app.route('/spotify/logout/')
def logout():
    session.clear()
    return redirect('/')


@app.route('/library/')
def library():
    try:
        playlists = userplaylists.find({'spotyid':session['username']})
        #print(playlists)
        return render_template('library.html', playlists=playlists)
    except:
        return render_template('401.html')


@app.route('/library/archive/')
def archive():
    user = userplaylists.find({'spotyid': session['username']})
    col = collplaylists.find({})

    for u in user:
        for c in col:
            print(u)
            uri = c['external_urls']['spotify']
            # c['tracks']['items']
            s = uri.replace('https://open.spotify.com/playlist/','')
            if u['playlist'] == s:
                return render_template('playlist-history.html', s=s, c=c)


@app.route('/library/playlist/<playlist_id>')
def pl(playlist_id=None):
    try:
        user = userplaylists.find_one({'spotyid':session['username'],'playlist': playlist_id})
        addurl = 'https://open.spotify.com/playlist/' + playlist_id

        # col = collplaylists.find_one({'external_urls':{'spotify':addurl}})
        currr = collplaylists.find({"external_urls": {"spotify": addurl}}).sort([('timestamp', -1)]).limit(1)
        coll = collplaylists.find({'external_urls': {'spotify': addurl}}).sort([('timestamp', -1)])

        return render_template('playlist-history.html', coll=coll, currr=currr,user=user)
    except KeyError:
        un = 'spotify'
        user = userplaylists.find_one({'spotyid':un,'playlist': playlist_id})
        addurl = 'https://open.spotify.com/playlist/' + playlist_id

        # col = collplaylists.find_one({'external_urls':{'spotify':addurl}})
        currr = collplaylists.find({"external_urls": {"spotify": addurl}}).sort([('timestamp', -1)]).limit(1)
        coll = collplaylists.find({'external_urls': {'spotify': addurl}}).sort([('timestamp', -1)])

        return render_template('playlist-history.html', coll=coll, currr=currr,user=user)


@app.route('/spotify/refresh_token/')
def refresh():
    col = collection.find_one({"spotyid": session['username']})
    url = 'https://accounts.spotify.com/api/token'
    data = {'grant_type': 'refresh_token','refresh_token': col['refresh_token'], 'client_id':client_id,
            'client_secret':client_secret}
    req = requests.post(url=url, data=data)
    res = req.json()
    access_token = res['access_token']
    collection.update_one({"spotyid": session['username']}, {'$set': {"access_token":access_token}})


@app.route('/spotify/values/',methods = ['POST', 'GET'])
def keys():
    req = request.get_json(force=True)
    check = req['checkb']
    playlistid = req['playlistid'].replace('/library/playlist/','')
    #print(playlistid)
    if check == True:
        user = userplaylists.find_one_and_update({'spotyid': session['username'], 'playlist': playlistid}, {'$set': {'cron':True}})
    else:
        user = userplaylists.find_one_and_update({'spotyid': session['username'],'playlist':playlistid}, {'$set': {'cron':False}})
    return jsonify({'status':200})
    # req = request.form.get('checkb')
    # return jsonify(req)


@app.route('/spotify/delete/', methods=['POST'])
def delete():
    url = request.form.get('url')
    timestamp = request.form.get('timestamp')
    print(url)
    print(timestamp)
    r = collplaylists.delete_one({'external_urls': {'spotify': url}, 'timestamp': datetime.datetime.fromisoformat(timestamp)})
    print(datetime.datetime.fromisoformat(timestamp))
    print(r.deleted_count)
    playlist_id = url.replace('https://open.spotify.com/playlist/','')
    # if r:
    #     return jsonify({'status': 200})
    return redirect('/library/playlist/' + playlist_id)


@app.route('/spotify/remove_playlist')
def removeplay():
    playlist = request.form.get('playlist')
    user = userplaylists.find({'spotyid': session['username'],'playlist':playlist})


@app.route('/spotify/remove_account')
def removeacc():
    collection.find({'spotyid': session['username']})


@app.route('/spotify/publish',methods=['POST'])
def publish():
    user = collection.find_one({'spotyid': session['username']})
    plurl = request.form.get('url')
    timestamp = request.form.get('timestamp')
    print(plurl)
    print(timestamp)
    collect = collplaylists.find_one({'external_urls': {'spotify': plurl}, 'timestamp': datetime.datetime.fromisoformat(timestamp)})
    spotyid = user['spotyid']
    url1 = f'https://api.spotify.com/v1/users/{spotyid}/playlists'
    params = {
        'name': collect['name'] + ' ' + timestamp.replace('00:00:00',''),
        'description': collect['description']
    }
    access_token = user['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    print(params)
    req = requests.post(url=url1, data=json.dumps(params),headers=headers)
    print(req.headers)
    print(req.json())
    if req.status_code == 201:
        a = []
        for t in collect['tracks']['items']:
            uris = t['track']['uri']
            a.append(uris)
        location = req.headers['Location'].replace('https://api.spotify.com/v1/playlists/','')
        url = f'https://api.spotify.com/v1/playlists/{location}/tracks'
        data = {
            'uris': a
        }
        req2 = requests.post(url=url, data=json.dumps(data),headers=headers)
        print(req2.status_code)
        if req2.status_code == 201:
            url2 = f'https://api.spotify.com/v1/playlists/{location}/images'
            headers.update({'Content-Type':'image/jpeg'})
            image = requests.get(url=collect['images'][0]['url'])
            datas = base64.b64encode(image.content)
            req3 = requests.put(url=url2,headers=headers,data=datas)
            print(req3.status_code)
            if req3.status_code == 202:
                playlist_id = plurl.replace('https://open.spotify.com/playlist/','')
                return flask.redirect('/library/playlist/' + playlist_id)


@app.route('/spotify/synchro')
def synchro():
    utc = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    orient = datetime.datetime.combine(datetime.date.today(), datetime.time(00, 00)).strftime("%Y-%m-%d %H:%M")
    utcm8 = (datetime.datetime.utcnow() - datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    utcm7 = (datetime.datetime.utcnow() - datetime.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M")
    utcm6 = (datetime.datetime.utcnow() - datetime.timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
    est = (datetime.datetime.utcnow() - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
    utcm4 = (datetime.datetime.utcnow() - datetime.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    utcm3 = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    utcm2 = (datetime.datetime.utcnow() - datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    utcm1 = (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    utc1 = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    utc2 = (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    utc3 = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    utc4 = (datetime.datetime.utcnow() + datetime.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    utc5 = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
    utc6 = (datetime.datetime.utcnow() + datetime.timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
    utc7 = (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M")
    utc8 = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    dst = time.localtime().tm_isdst
    if dst == 0:
        if utc == orient:
            pass
        elif utc1 == orient:
            pass
        elif utc2 == orient:
            #дописать тех у кого это постоянное время
            coll = collection.find({'country':{'$in':['BG','GR','IL','JO','CY','LT','LB','LV','RO','MD','PS','UA','FI'
                                                      'EG',]}})
        elif est == orient:
            #обновлять все плейлисты, так как в это время они обновляются
            up = userplaylists.find({'name': {'$nin': ['Discover Weekly', 'Release Radar']}})
            pass
    else:
        if utc == orient:
            pass
        elif utc3 == orient:
            coll = collection.find(
                {'country': {'$in': ['BG', 'GR', 'IL', 'JO', 'CY', 'LT', 'LB', 'LV', 'RO', 'MD', 'PS', 'UA', 'FI']}})