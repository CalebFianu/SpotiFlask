from platform import release
from urllib import response
from flask import Flask, redirect, request, session
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
import requests
import os
import json
import sys
import numpy as np

#Constants
load_dotenv() #To load our environment varaibles
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
FOLLOWED_ARTISTS = 'https://api.spotify.com/v1/me/following?type=artist'
USER_ID = os.getenv('SPOTIFY_USER_ID')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

def get_tokens():
    with open('tokens.json', 'r') as openfile:
        tokens = json.load(openfile)
    return tokens

def get_track():
    with open('tracks.json', 'r') as openfile:
        tracks_uris = json.load(openfile)
    return tracks_uris

#Requesting user authorization from Spotify
@app.route('/')
def request_auth():
    scope = 'user-top-read playlist-modify-public playlist-modify-private user-follow-read'
    return redirect(f'https://accounts.spotify.com/authorize?response_type=code&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}')

#Get Authorization token from spotify and return the response parameters
@app.route('/callback')
def request_tokens():
    code = request.args.get('code')
    payload = {
        'grant_type' : 'authorization_code',
        'code' : code,
        'redirect_uri' : REDIRECT_URI,
        'client_id' : CLIENT_ID,
        'client_secret' : CLIENT_SECRET
    }

    r = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    response = r.json()

    #storing response values
    tokens = {
        'access_token' : response['access_token'],
        'refresh_token' : response['refresh_token'],
        'expires_in' : response['expires_in']
    }

    with open('tokens.json', 'w') as outfile:
        json.dump(tokens, outfile) 
    
    return redirect('/get_artists')

#On to the fun stuff, 1. Get a user's followed artists
@app.route('/get_artists')
def get_artists():
    
    #Getting a json formatted list of user's followed artists using access token
    tokens = get_tokens()

    headers = {'Authorization' : f'Bearer {tokens["access_token"]}'}
    r = requests.get(FOLLOWED_ARTISTS, headers=headers)
    response = r.json()

    #Getting artist ids
    artist_ids = []
    artists = response['artists']['items']

    for artist in artists:
        artist_ids.append(artist['id'])

    #Getting all artists using 'next'
    while response['artists']['next']:
        next_page = response['artists']['next']
        r = requests.get(next_page, headers=headers)
        response = r.json()
        for artist in response['artists']['items']:
            artist_ids.append(artist['id'])

    print('Retrieved artist IDs: ')
    session['artist_ids'] = artist_ids

    return redirect('/get_albums')

#2. Get the artists' albums
@app.route('/get_albums')
def get_albums():
    #access tokens and artists from 'get_artists' function
    tokens = get_tokens()
    artist_ids = session['artist_ids']

    #Get album ids
    album_ids = []
    album_names = {}
    today = datetime.now()
    numberofweeks = timedelta(weeks=2)
    timeframe = (today-numberofweeks).date()

    for id in artist_ids:
        uri = f'https://api.spotify.com/v1/artists/{id}/albums?include_groups=album,single&country=GH'
        headers = {'Authorization' : f'Bearer {tokens["access_token"]}'}
        r = requests.get(uri, headers=headers)
        response = r.json()

        albums = response['items']
        for album in albums:
            try:
                release_date = datetime.strptime(album['release_date'], '%Y-%m-%d')
                album_name = album['name']
                artist_name = album['artists'][0]['name']
                if release_date.date() > timeframe:
                    if album_name not in album_names or artist_name != album_names[album_name]:
                        album_ids.append(album['id'])
                        album_names[album_name] = artist_name 
            except ValueError:
                print(f'Release date found with format: {album["release_date"]}')

    session['album_ids'] = album_ids
    print("Retrieve album IDs!")
    return redirect('/get_tracks')

#3. Get the tracks from said albums
@app.route('/get_tracks')
def get_tracks():
    tokens = get_tokens()
    album_ids = session['album_ids']
    

    track_uris = []

    for id in album_ids:
        uri = f'https://api.spotify.com/v1/albums/{id}/tracks'
        headers = {'Authorization' : f'Bearer {tokens["access_token"]}'}
        r = requests.get(uri, headers=headers)
        response = r.json()

        for track in response['items']:
            track_uris.append(track['uri'])
        
    print('Got the tracks!')

    uri_dict = {'uris': track_uris}
    with open('tracks.json', 'w') as outfile:
        json.dump(uri_dict, outfile)
        
    return redirect('/create_playlist')


#4. Create the playlist
@app.route('/create_playlist')
def create_playlist():
    tokens = get_tokens()
    current_date = (date.today()).strftime('%m-%d-%Y')
    playlist_name = f"Caleb's Python Playlist of New Releases - {current_date}" 
    
    uri = f'https://api.spotify.com/v1/users/{USER_ID}/playlists'
    headers = {'Authorization' : f'Bearer {tokens["access_token"]}', 'Content-Type': 'application/json'}
    payload = {'name' : playlist_name}
    r = requests.post(uri, headers=headers, data=json.dumps(payload))
    response = r.json()

    session['playlist_id'] = response['id']
    session['playlist_url'] = response['external_urls']['spotify']

    print(f'{r.status_code} - Created your playlist!')
    return redirect('/add_to_playlist')

#5. Add the tracks to said playlist
@app.route('/add_to_playlist')
def add_to_playlist():
    tokens = get_tokens()
    playlist_id = session['playlist_id']
    track_uris = get_track()
    
    track_list = track_uris['uris']
    number_of_tracks = len(track_list)

    if number_of_tracks > 200:
        three_split = np.array_split(track_list, 3)
        for newlist in three_split:
            uri = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
            headers = {'Authorization' : f'Bearer {tokens["access_token"]}', 'Content-Type': 'application/json'}
            payload = {'uris': list(newlist)}
            r = requests.post(uri, headers=headers, data=json.dump(payload))
            response = r.json()

    elif number_of_tracks > 100:
        two_split = np.array_split(track_list, 2)
        for newlist in two_split:
            uri = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
            headers = {'Authorization' : f'Bearer {tokens["access_token"]}', 'Content-Type': 'application/json'}
            payload = {'uris': list(newlist)}
            r = requests.post(uri, headers=headers, data=json.dumps(payload))
            response = r.json()

    else:
        uri = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {'Authorization' : f'Bearer {tokens["access_token"]}', 'Content-Type': 'application/json'}
        payload = {'uris': track_list}
        r = requests.post(uri, headers=headers, data=json.dumps(payload))
        response = r.json()
    
    print("Added track to playlist. Yay!")

    return redirect(session['playlist_url'])


if __name__ == "__main__":  
    app.run(debug=True)