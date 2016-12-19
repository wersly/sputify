from bs4 import BeautifulSoup
from selenium import webdriver
from urllib.parse import urlparse
import webbrowser
import requests
import time
import random
import spotipy
import spotipy.util as util
from login_info import credentials

def urlSanityCheck():
    list_url = input("\nlist url >>> ")
    if list_url[0:3] == 'www':
        return list_url
    elif list_url[0:4] == 'http':
        return list_url
    elif list_url[0:5] == 'https':
        return list_url
    else:
        urlSanityCheck()

def sampleSanityCheck():
    sample = input("how many tracks per album would you like to sample? (full albums -> press enter) >>> ")
    if sample.isdigit() == True:
        return int(sample)
    elif sample == '':
        return sample
    else:
        sampleSanityCheck()

def randomizeSanityCheck():
    randomize = input("would you like to randomize this playlist? (y/n) >>> ").lower()
    if randomize == 'y' or randomize == 'n':
        return randomize
    else:
        randomizeSanityCheck()

print('''\n _     _                         
| |__ (_)                        
| '_ \| |                        
| | | | |                        
|_| |_|_|        _   _  __       
 ___ _ __  _   _| |_(_)/ _|_   _ 
/ __| '_ \| | | | __| | |_| | | |
\__ \ |_) | |_| | |_| |  _| |_| |
|___/ .__/ \__,_|\__|_|_|  \__, |
    |_|                    |___/ \n''')
print("""what is this?
============
provided urls to sput music lists containing records, sputify will parse the list, automate your spotify login, and query the contents of the sput list against the spotify api to generate a spotify playlist.
before use, make sure to write your spotify credentials into the 'credentials.py' file, or else you will not be able to log in to spotify.
if this is your first time using sputify, please follow spotify's prompt upon login to give this script permission to access your account. you will only have 7 seconds to do before selenium closes the browser window, so move swiftly (:

what do i need to run this?
===========================
- latest version firefox
- latest selenium webdriver
- latest version of geckodriver (firefox) or chromedriver (chrome) tucked away in /usr/local/bin

etc
===
chrome compatibility (login automation via selenium/chromedriver) coming soon\n\n~""")

#import user credentials
uname = credentials.get('uname', None)
pw = credentials.get('pw', None)
        
#prompts
#list_url = "http://www.sputnikmusic.com/list.php?memberid=1042215&listid=167186"
list_url = urlSanityCheck()
playlist_name = input("playlist name >>> ")
sample = sampleSanityCheck()
randomize = randomizeSanityCheck()

#obtain and parse list
r = requests.get(list_url)
data = r.text
soup = BeautifulSoup(data)
music = soup.find_all('td', {"class" : "alt1"})
sput_list = []

print("\nfetching from sputnik...")
for link in music:
    if type(link.b) != type(None):
        this_artist = link.a.b.contents[0].strip().lower()
    else:
        continue

    if type (link.span) != type(None):
        this_album = link.find('span', style="font-size: 11pt; ").contents[0].strip().lower()
    else:
        continue

    entry = (this_artist, this_album)
    sput_list.append(entry)

#skeleton query via implicit authorization flow
query = 'https://accounts.spotify.com/authorize?client_id=df24fd4194d04511b1cab8eb4e8c44c1&redirect_uri=http:%2F%2Flocalhost:8888%2Fcallback&scope=playlist-modify-public&response_type=token'

#fetch browser type
print("logging in to spotify...")
flag = '1'
def automateLogin():
    browser.get(query)
    button = browser.find_element_by_partial_link_text('Log in to Spotify')
    button.click()

    name_field = browser.find_element_by_id('login-username')
    pass_field = browser.find_element_by_id('login-password')

    name_field.send_keys(uname)
    pass_field.send_keys(pw)
    pass_field.submit()
    time.sleep(7)

try:
    webbrowser.get('firefox')
    while flag == '1':
        browser = webdriver.Firefox()
        automateLogin()
        flag = '0'
    
except webbrowser.Error:
    while flag == '1':
        browser = webdriver.Chrome()
        automateLogin() #for now, traditional selenium methods in automateLogin() are not compatible with chromedriver
        flag = '0'
        
unprocessed_key = browser.current_url #find a way to do this one time (not continously), so NoneType is not returned
browser.quit()

p = urlparse(unprocessed_key)
s = str(p[5])
api_return = dict(item.split("=") for item in s.split("&"))
token = api_return.get('access_token', None)

search_jsons = []
album_ids = []
lost_queries = []
track_ids = []

print("\nassembling playlist...")
if token:
    sp = spotipy.Spotify(auth=token)
    new_playlist = sp.user_playlist_create(user=uname,name=playlist_name,public=True)
    new_playlist_id = sp.user_playlists(user=uname,limit=1,offset=0).get('items', None)[0].get('id', None)

    for item in sput_list:
        q = "%a AND %a" % (item[0], item[1])
        result = sp.search(q, limit=1, type='album')
        try:
            identifier = result.get('albums', None).get('items', None)[0].get('id', None)
            album_ids.append(identifier)
            search_jsons.append(result)
            pass

        except IndexError:
            #add failed to a list that will print at the end or log to external file
            lost_queries.append([item[0], item[1]])
            continue

    #for each album, get album tracks and add to playlist // perform sampling
    if isinstance(sample, int) == True:
       for t in album_ids:
           temp1 = []
           temp2 = []
           album_json = sp.album_tracks(t,limit=50,offset=0)
           i = album_json.get('items', None)
           for entry in i:
               track = entry.get('id', None)
               temp1.append(track)
           try:
               temp2 = random.sample(temp1, sample)
               for track in temp2:
                   track_ids.append(track)

           except ValueError:
               for track in temp1:
                   track_ids.append(track)

    else:
        for t in album_ids:
            album_json = sp.album_tracks(t,limit=50,offset=0)
            i = album_json.get('items', None)
            for entry in i:
                track = entry.get('id', None)
                track_ids.append(track)

    #randomize whole playlist?
    if randomize == 'y':
        random.shuffle(track_ids)

    #add track_ids to playlist
    if len(track_ids) > 100:
        a = 0
        b = 100
        remainder = len(track_ids[b:])

        while remainder > 100:
            if a == 0:
                sp.user_playlist_add_tracks(user=uname,playlist_id=new_playlist_id,tracks=track_ids[a:b],position=None)
            else:
                aa = a+1
                sp.user_playlist_add_tracks(user=uname,playlist_id=new_playlist_id,tracks=track_ids[aa:b],position=None)

            a += 100
            b += 100
            remainder = len(track_ids[b:])

        sp.user_playlist_add_tracks(user=uname,playlist_id=new_playlist_id,tracks=track_ids[b:],position=None)

    else:
        sp.user_playlist_add_tracks(user=uname,playlist_id=new_playlist_id,tracks=track_ids,position=None)

else:
    print("\nCan't get token for", uname)

print("\ndone! added {0} of {1} records.".format(len(album_ids), len(sput_list)))
if len(lost_queries) > 1:
    print("could not find the following:\n")
    for item in lost_queries:
        print('Artist: {0} \t Album: {1}'.format(item[0], item[1]))
