import hmac
import random
import string
import traceback

import base64
from io import StringIO
from urllib.parse import urlparse

import bs4
import requests
import logging

import hashlib
import pytube
import re
import instaloader
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pytz import timezone
from datetime import datetime
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

app = Flask(__name__)
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Configure logging to print messages to the console
logging.basicConfig(filename='downloader_app.log', level=logging.DEBUG)

# Create a Limiter instance
limiter = Limiter(get_remote_address,  # Rate limit based on IP address
                  app=app, storage_uri="memory://", )  # Use in-memory storage (Can use other storage backends)


@app.errorhandler(429)
def handle_rate_limit_exceeded(e):
    return jsonify({"error": "Rate limit exceeded. Try again later."}), 429


def validate_uuid(userID, userSign):
    ind_time = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S.%f')
    SECRET_KEY = b'secret_key'
    # print("Inside validate_uuid")
    try:
        # Get UUID and signature from the request
        uuid = userID
        signature = userSign

        if len(uuid) == 36:
            signature_decoded = decode_url_safe_base64(signature)
            # print("signature OG ", signature_decoded)

            # Calculate HMAC of the UUID using the secret key
            hmac_calculated = hmac.new(SECRET_KEY, uuid.encode('utf-8'), hashlib.sha256).digest()

            # Compare the calculated HMAC with the decoded signature
            if hmac.compare_digest(signature_decoded, hmac_calculated):
                app.logger.info("SUCCESS | " + ind_time + " | Successful UUID verification for : " + uuid)
                return True  # "UUID is genuine"
            else:
                app.logger.error("ERROR | " + ind_time + " | HMAC verification failed for : " + uuid)
                return False  # "UUID is not genuine"
        else:
            app.logger.error("ERROR | " + ind_time + " | Invalid length for : " + uuid)
            return False  # "UUID is not genuine"
    except Exception as e:
        app.logger.error("ERROR | " + ind_time + " | validate_uuid | " + str(e))
        return False


def decode_url_safe_base64(encoded_string):
    # print("Inside decode_url_safe_base64", encoded_string)
    try:
        # Replacing URL-safe Base64 characters with standard Base64 characters
        encoded_string = encoded_string.replace('!', '/')

        # Padding the string if necessary
        encoded_string += '=' * ((4 - len(encoded_string) % 4) % 4)

        return base64.b64decode(encoded_string)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None


def getDirectLinkYT(video_url):
    ind_time = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S.%f')
    try:
        print("Inside YT")
        yt = pytube.YouTube(video_url)
        print("YT resp ", str(yt))
        thumbnail = yt.thumbnail_url

        yt_title = re.sub(r'[!@#$:?"`~-]', '', yt.title).replace("'", "").strip()

        videoDirectLink = yt.streams.get_highest_resolution().url
        onlyAudioDirectLink = yt.streams.get_audio_only().url
        # print("YT D-LINK ", videoDirectLink, "\nYT D-LINK(A) ", onlyAudioDirectLink)
        result = {"title": yt_title, "videoURL": videoDirectLink, "audioURL": onlyAudioDirectLink,
                  "thumbnail": thumbnail}

        return result

    except AttributeError as ae:
        print("Exception occurred : ", ae)
        print(traceback.format_exc())
        app.logger.error("ERROR | " + ind_time + " | getDirectLinkYT | " + str(ae))
        return jsonify({"error": str(ae)}), 250


# def getYTlinkFromKeepvid(url):
#     "https://www.keepvid.to/?f=t&url=https://youtu.be/AKiynoClCaA?si=tXWdIsuBeUUSIzc8"
#     try:
#         print("Inside twitter")
#         api_url = f"https://www.keepvid.to/?f=t&url={url}"
#
#         response = requests.get(api_url)
#         data = bs4.BeautifulSoup(response.text, "html.parser")
#         video_element = data.find('video')
#         highest_quality_url = video_element['src']
#
#         # download_button = data.find_all("div", class_="origin-top-right")[0]
#         # quality_buttons = download_button.find_all("a")
#         # highest_quality_url = quality_buttons[0].get("href")  # Highest quality video url
#
#         file_name = data.find_all("div", class_="leading-tight")[0].find_all("p", class_="m-2")[0].text
#         file_name = re.sub(r"[^a-zA-Z0-9]+", ' ', file_name).strip() + ".mp4"
#
#         # print("TWITTER D-LINK ", highest_quality_url)
#         result = {"videoURL": highest_quality_url, "title": file_name}
#         # print("result TW ", result)
#         return result
#         # download_video(highest_quality_url, file_name)
#     except Exception as e:
#         print(traceback.format_exc())
#         return jsonify({"error": str(e)}), 250


def getDirectLinkInsta(insta_url):
    ind_time = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S.%f')

    try:
        print("Inside insta")
        # Create an instance of the Instaloader class
        loader = instaloader.Instaloader()

        # Login to Instagram (optional)
        # loader.context.log("Login...")
        # loader.load_session_from_file("your_account")

        # Retrieve a post by its URL
        post_url = insta_url
        post = instaloader.Post.from_shortcode(loader.context, post_url.split("/")[-2])
        # print("INSTA D-LINK ", post.video_url)

        # Extract the post's caption
        caption = post.caption
        # print("Caption: ", caption)
        print(post.video_url)
        print(caption)
        print(post.url)
        app.logger.info("SUCCESS | " + ind_time + " | Generated successful Insta link : " + insta_url)
        result = {"videoURL": post.video_url, "title": caption, "thumbnail": post.url}
        print("result IN ", result)
        return result
        # loader.download_post(post, "target.mp4")
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        app.logger.error("ERROR | " + ind_time + " | getDirectLinkInsta | " + str(e))
        return jsonify({"error": str(e)}), 250


def getDirectLinkTwitter(url):
    ind_time = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S.%f')

    try:
        print("Inside twitter")
        api_url = f"https://twitsave.com/info?url={url}"

        response = requests.get(api_url)
        data = bs4.BeautifulSoup(response.text, "html.parser")
        video_element = data.find('video')
        highest_quality_url = video_element['src']

        # download_button = data.find_all("div", class_="origin-top-right")[0]
        # quality_buttons = download_button.find_all("a")
        # highest_quality_url = quality_buttons[0].get("href")  # Highest quality video url

        file_name = data.find_all("div", class_="leading-tight")[0].find_all("p", class_="m-2")[0].text
        file_name = re.sub(r"[^a-zA-Z0-9]+", ' ', file_name).strip() + ".mp4"

        # print("TWITTER D-LINK ", highest_quality_url)
        app.logger.info("SUCCESS | " + ind_time + " | Generated successful Twitter link : " + url)
        result = {"videoURL": highest_quality_url, "title": file_name}
        # print("result TW ", result)
        return result
        # download_video(highest_quality_url, file_name)
    except Exception as e:
        app.logger.error("ERROR | " + ind_time + " | getDirectLinkTwitter | " + str(e))
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 250


def downloader(userID, userSign, url):
    # print("Inside downloader")

    try:
        # userID = request.form.get('uuid')
        # userSign = request.form.get('signedUuid')
        # url = request.form.get('url')

        # print(userID, userSign, url)
        validateCheck = validate_uuid(userID, userSign)
        # print("Validating user id ", validateCheck)
        if validateCheck:

            # if "youtube" in url or "youtu.be" in url:
            #
            #     y_result = getDirectLinkYT(url)
            #     # print("Youtube URL", y_result)
            #     return y_result
            #
            # elif "instagram" in url or "insta" in url:
            #
            #     i_result = getDirectLinkInsta(url)
            #     print("Instagram URL", i_result)
            #     return i_result
            #
            # elif "twitter" in url:
            #
            #     t_result = getDirectLinkTwitter(url)
            #     # print("Twitter URL", t_result)
            #     return t_result
            #
            # else:
            result = allInOneDownloader(url)
            return result
        else:
            return jsonify({"error": "Unauthorized. Please install our app to use our features for free."}), 250

    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None


def extract_site_from_url(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith('www.'):
        domain = domain[4:]  # Remove 'www.' if present
    return domain


def get_ydl_opts_cred(site):
    credentials = {
        'example': ('rohangala07@gmail.com', 'rohangala07'),
        # 'youtube.com': ('rohangala07@gmail.com', 'rohangala07'),
        # 'youtu.be': ('rohangala07@gmail.com', 'rohangala07'),
        # 'instagram.com': ('katebrooks@myyahoo.com', 'OnlyFans1'),
        # 'twitter.com': ('brooks_kat83539', 'OnlyFans@1'),
        # 'pornhub.org': ('rohangala07@gmail.com', 'Bg.X.twWh4DQTDR'),
        # Add more sites and corresponding credentials as needed
    }

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]',
        # Other common options here
    }

    # Attempt to retrieve credentials for the site
    username, password = credentials.get(site, (None, None))
    if username and password:
        # Add authentication options if credentials are available
        ydl_opts['username'] = username
        ydl_opts['password'] = password

    return ydl_opts


def get_ydl_opts(site):
    if site == "facebook.com":
        ydl_opts = {
            'format': 'best',
            'nocheckcertificate': 'True',
        }
    else:
        ydl_opts = {
            'format': 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440][ext=mp4]',
            'nocheckcertificate': 'True',
        }
        if site in ["twitter.com", "x.com"]:
            cookies_url = "https://raw.githubusercontent.com/pavan098765/videoDownloader/master/twitter.com_cookies.txt"
            cookies = fetch_cookies(cookies_url)
            ydl_opts['cookiefile'] = cookies
        elif site in ["instagram.com", "insta.com"]:
            cookies_url = "https://raw.githubusercontent.com/pavan098765/videoDownloader/master/instagram.com_cookies.txt"
            cookies = fetch_cookies(cookies_url)
            ydl_opts['cookiefile'] = cookies
    return ydl_opts


def fetch_cookies(url):#
    response = requests.get(url)
    return StringIO(response.text)


def allInOneDownloader(url):
    site = extract_site_from_url(url)

    print("Using allInOneDownloader for Site : ", str(site))

    options = get_ydl_opts(site)

    with YoutubeDL(options) as ydl:
        try:

            info = ydl.extract_info(url, download=False, process=True)  # Extract video information without downloading
            print("info", info)

            if site in ["youtube.com", "youtu.be"]:
                direct_link = getYT_DLinkInfo(info)
                result = {"videoURL": direct_link, "title": extract_title(info)}

            elif site in ["twitter.com", "x.com"]:
                direct_link = getTW_DLinkInfo(info)
                result = {"videoURL": direct_link, "title": extract_title(info)}

            elif site in ["instagram.com", "insta.com"]:
                direct_link = getIN_DLinkInfo(info)
                result = {"videoURL": direct_link, "title": extract_title(info)}


            else:
                direct_link = info['url']  # Get the direct link
                result = {"videoURL": direct_link, "title": extract_title(info)}

            return result
        except KeyError as ke:

            print(traceback.format_exc())
            print("------")
            return handle_exception(info)


def getYT_DLinkInfo(info):
    if 'formats' in info:
        # link is youtube
        for items in info['formats']:
            if 'asr' in items:
                if items['audio_channels'] == 2 and items['quality'] == 8:
                    return items['url']
    else:
        direct_link = info['url']  # Get the direct link
        return direct_link


def getTW_DLinkInfo(info):
    # Iterate through entries to find the desired format
    list_dlink = []
    if 'entries' in info:  # multi post tweet, gets d link for all video posts
        for entry in info['entries']:
            for fmt in entry['formats']:
                if 'http' in fmt['format_id']:
                    if fmt['resolution'] != "audio only":
                        list_dlink.append(fmt['url'])
        return list_dlink[0]  # FOR NOW JUST RETURN 1st URL. TODO add client support for multi d-links list
    else:  # gets d link for single post tweet
        direct_link = info['url']  # Get the direct link
        return direct_link


def getIN_DLinkInfo(info):
    max_width = 0
    max_height = 0
    max_url = ""
    # Iterate through entries to find the desired format
    if 'formats' in info:
        # Iterate through the formats
        for fmt in info['formats']:
            width = fmt.get('width', 0)
            height = fmt.get('height', 0)
            format_id = fmt.get('format_id', '')
            ext = fmt.get('ext', '')

            # Check if this format has higher width and height, and format_id does not contain 'dash'
            if ext == "mp4":
                if width > max_width and height > max_height and 'dash' not in format_id:
                    max_width = width
                    max_height = height
                    max_url = fmt['url']
        return max_url

    else:
        direct_link = info['url']  # Get the direct link
        return direct_link


def handle_exception(info):
    try:
        print("In handle exception")
        # Implement your logic to handle the exception here
        result = {"videoURL": print_nested_urls(info)[0], "title": extract_title(info)}
        return result
    except Exception as e:
        print(traceback.format_exc())
        return None


def extract_title(data):
    if "title" in data:
        return data["title"]
    else:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


def print_nested_urls(data, key='url'):
    url_list = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key and ".mp4" in v:
                url_list.append(v)
            else:
                url_list.extend(print_nested_urls(v, key))  # Extend the list with the result of recursive call
    elif isinstance(data, list):
        for item in data:
            url_list.extend(print_nested_urls(item, key))  # Extend the list with the result of recursive call
    return url_list  # Return the url_list at the end


def decode_url_safe_base64URL(encoded_string):
    # print("Inside decode_url_safe_base64 for URL")
    try:
        # print(encoded_string)

        # Convert the URL-safe Base64 encoded string to bytes
        encoded_bytes = encoded_string.encode('utf-8')

        # Decode the bytes using URL-safe Base64 decoding
        decoded_bytes = base64.urlsafe_b64decode(encoded_bytes)

        # Convert the decoded bytes to a string
        decoded_string = decoded_bytes.decode('utf-8')
        # print("DECODED URL ",decoded_string)

        return decoded_string

    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None


@app.route('/api/downloaderHome/<string:params>')
@limiter.limit("10/minute")  # Apply the global rate limit to this route
def downloaderHome(params):
    ind_time = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S.%f')

    try:
        print("Welcome to downloader")
        params = params.split(";")
        user_id = params[0]
        user_sign = params[1]
        # print("Enc URL ", params[2])
        url = decode_url_safe_base64URL(params[2])
        # print("RECEIVED DATA" + "\nuser_id : " + user_id + "\nuser_sign" + user_sign + "\nurl " + str(url))
        result = downloader(user_id, user_sign, str(url))
        print("RESULT ", result)
        return jsonify(result)

    except Exception as e:
        print(e)
        print(traceback.format_exc())
        app.logger.error("ERROR | " + ind_time + " | downloader | " + str(e))
        return jsonify({"error": str(e)}), 250

# print(getDirectLinkYT("https://youtu.be/dQw4w9WgXcQ?feature=youtube_gdata_player"))
# print(getDirectLinkInsta("https://www.instagram.com/reel/C502HyHNp6C/?igsh=cnNkaWV0cTZmOHE5"))
# print(getDirectLinkTwitter("https://twitter.com/DesiHiroin/status/1783470993186640278?t=teUmxOOCzm-S8F4JTn8hQw&s=19"))
# if __name__ == '__main__':
#     print("Starting app with host")
#     app.run(host='0.0.0.0', port=5000)
