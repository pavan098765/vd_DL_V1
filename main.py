import hmac
import os
import random
import string
import time
import traceback
from instagrapi import Client
from instagrapi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag
import asyncio
import telegram

import base64
from io import StringIO
from urllib.parse import urlparse, quote

import bs4
import requests
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

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

app = Flask(__name__)
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Configure logging to print messages to the console
logging.basicConfig(filename='downloader_app.log', level=logging.DEBUG)

# Create a Limiter instance
limiter = Limiter(get_remote_address,  # Rate limit based on IP address
                  app=app, storage_uri="memory://", )  # Use in-memory storage (Can use other storage backends)


@app.errorhandler(429)
def handle_rate_limit_exceeded(e):
    print(e)
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
        print("YT resp ", str(yt.channel_id), " | ", yt.length)
        thumbnail = yt.thumbnail_url

        yt_title = re.sub(r'[!@#$:?"`~-]', '', yt.title).replace("'", "").strip()

        videoDirectLink = yt.streams.get_highest_resolution().url
        onlyAudioDirectLink = yt.streams.get_audio_only().url
        # print("YT D-LINK ", videoDirectLink, "\nYT D-LINK(A) ", onlyAudioDirectLink)
        result = {"title": yt_title,
                  "videoURL": [videoDirectLink],
                  "audioURL": onlyAudioDirectLink,
                  "thumbnail": [thumbnail],
                  "realTitle": yt.title,
                  "uploader": yt.author,
                  "duration": format_duration(yt.length)

                  }
        return result
    except AttributeError as ae:
        print("Exception occurred : ", ae)
        print(traceback.format_exc())
        app.logger.error("ERROR | " + ind_time + " | getDirectLinkYT | " + str(ae))
        return jsonify({"error": str(ae)}), 250


def format_duration(duration):
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)

    formatted_duration = ""

    if hours > 0:
        formatted_duration += f"{hours} hr. "
    if minutes > 0:
        formatted_duration += f"{minutes} min. "
    if seconds > 0:
        formatted_duration += f"{seconds:.1f} sec."
    elif duration == 0:
        formatted_duration += "0 sec."

    return formatted_duration.strip()  # Remove trailing whitespace


def getDirectLinkInsta_instagrapi(insta_url):
    cl = Client()
    cl.login(username="katebrooks@myyahoo.com", password="OnlyFans1")

    media_pk = cl.media_pk_from_url(insta_url)
    media_info = cl.media_info(media_pk).dict()

    result = {"title": media_info['title'], "videoURL": media_info["video_url"],
              "thumbnail": media_info["thumbnail_url"]}

    return result


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


def getTerra(url):
    print("Inside twitter")

    # Configure Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode, no UI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    full_path_binary = os.path.expanduser('~/chrome-bin/opt/google/chrome/chrome')
    print("full_path_binary ", full_path_binary)
    chrome_options.binary_location = full_path_binary  # os.environ.get("GOOGLE_CHROME_BIN")

    full_path_executable = os.path.expanduser('~/chrome-bin/chromedriver')
    print("full_path_executable ", full_path_executable)
    service = Service(executable_path=full_path_executable)  # os.environ.get("CHROMEDRIVER_PATH"))

    # Initialize Chrome WebDriver
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Load the page
    driver.get(url)

    # Wait for the page to fully load (adjust timeout as needed)
    time.sleep(5)  # Wait for 10 seconds (you may need to adjust this)

    # Get the HTML content after the page is fully loaded
    html_content = driver.page_source

    # Parse HTML content
    soup = bs4.BeautifulSoup(html_content, 'html.parser')

    print(soup)

    download_buttons = soup.find_all('a')
    d_links = []
    # Extract the value of the 'href' attribute for each button
    for button in download_buttons:
        download_link = button.get('href')
        if len(download_link) > 200:
            d_links.append(download_link)

    # Close the WebDriver
    driver.quit()
    title = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    result = {"title": title, "videoURL": d_links[1],
              "thumbnail": "https://cdn77-pic.xvideos-cdn.com/videos/thumbs169lll/45/a3/cd/45a3cd213fd88303e7f82978e9158aab-1/45a3cd213fd88303e7f82978e9158aab.16.jpg"}

    return result


def prepareTerraURL(terra_link):
    return "https://teradownloader.com/download?link=" + quote(terra_link, safe='')


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
    ind_time = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S.%f')

    try:

        # print(userID, userSign, url)
        validateCheck = validate_uuid(userID, userSign)
        # print("Validating user id ", validateCheck)
        if validateCheck:
            try:
                if "youtube" in url or "youtu.be" in url:
                    try:
                        y_result = getDirectLinkYT(url)
                        message = ("SUCCESS | " + ind_time + " | " + "Successful link : " + url)
                        asyncio.run(telegram_bot(message))
                        return y_result
                    except Exception as e:
                        result = allInOneDownloader(url)
                        return result

                elif 'terabox' in url:
                    T_result = getTerra(prepareTerraURL(url))
                    message = ("SUCCESS | " + ind_time + " | " + "Successful link : " + url)
                    asyncio.run(telegram_bot(message))
                    return T_result
                else:
                    result = allInOneDownloader(url)
                    message = ("SUCCESS | " + ind_time + " | " + "Successful link : " + url)
                    asyncio.run(telegram_bot(message))
                    return result

            except Exception as e:
                message = ("ERROR | " + ind_time + " | " + str(e) + " | Failed link : " + url)
                asyncio.run(telegram_bot(message))
                result = {'error': str(e)}
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
        'example': ('email@gmail.com', 'pass'),

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
    cookies_base_url = "https://raw.githubusercontent.com/pavan098765/vd_DL_V1/master/"

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
            cookies_url = cookies_base_url + "twitter.com_cookies.txt"
            cookies = fetch_cookies(cookies_url)
            ydl_opts['cookiefile'] = cookies
        elif site in ["instagram.com", "insta.com"]:
            cookies_url = cookies_base_url + "instagram.com_cookies.txt"
            cookies = fetch_cookies(cookies_url)
            ydl_opts['cookiefile'] = cookies
        elif site == 'pornhub.org':
            cookies_url = cookies_base_url + "pornhub.org_cookies.txt"
            cookies = fetch_cookies(cookies_url)  # fetch_cookies(cookies_url)
            ydl_opts['cookiefile'] = cookies
    return ydl_opts


def fetch_cookies(url):  #
    response = requests.get(url)
    return StringIO(response.text)


def extract_thumbnail(data):
    # Initialize an empty list to store thumbnails
    thumbnails = []

    # Helper function to traverse the data recursively
    def traverse(obj):
        # If the object is a dictionary, iterate over its key-value pairs
        if isinstance(obj, dict):
            for key, value in obj.items():
                # If the key is "thumbnail", add the value to the thumbnails list
                if key == "thumbnail":
                    thumbnails.append(value)
                # If the value is a nested dictionary or list, recursively call traverse
                elif isinstance(value, (dict, list)):
                    traverse(value)
        # If the object is a list, iterate over its elements
        elif isinstance(obj, list):
            for item in obj:
                # Recursively call traverse for each element
                traverse(item)

    # Start traversing the data
    traverse(data)

    return thumbnails


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
                result = {
                    "videoURL": direct_link,
                    "title": extract_title(info)[0],
                    "thumbnail": extract_thumbnail(info),
                    "realTitle": extract_title(info)[1],
                    "uploader": find_uploader(info),
                    "duration": find_max_duration(info)
                }

            elif site in ["twitter.com", "x.com"]:
                direct_link = getTW_DLinkInfo(info)
                result = {
                    "videoURL": direct_link,
                    "title": extract_title(info)[0],
                    "thumbnail": extract_thumbnail(info),
                    "realTitle": extract_title(info)[1],
                    "uploader": find_uploader(info),
                    "duration": find_max_duration(info)
                }

            elif site in ["instagram.com", "insta.com"]:
                direct_link = getIN_DLinkInfo(info)
                result = {
                    "videoURL": direct_link,
                    "title": extract_title(info)[0],
                    "thumbnail": extract_thumbnail(info),
                    "realTitle": extract_title(info)[1],
                    "uploader": find_uploader(info),
                    "duration": find_max_duration(info)
                }

            elif "xvideo" in site or "pornhub" in site:
                direct_link = getXV_DLinkInfo(info, site)
                result = {
                    "videoURL": direct_link,
                    "title": extract_title(info)[0],
                    "thumbnail": extract_thumbnail(info),
                    "realTitle": extract_title(info)[1],
                    "uploader": find_uploader(info),
                    "duration": find_max_duration(info)
                }

            else:
                direct_link = info['url']  # Get the direct link
                result = {
                    "videoURL": direct_link,
                    "title": extract_title(info)[0],
                    "thumbnail": extract_thumbnail(info),
                    "realTitle": extract_title(info)[1],
                    "uploader": find_uploader(info),
                    "duration": find_max_duration(info)
                }

            return result
        except KeyError as ke:

            print(traceback.format_exc())
            print(ke)
            return handle_exception(info)


def find_uploader(response):
    def traverse(data):
        if isinstance(data, dict):
            if 'uploader' in data:
                return data['uploader']
            for value in data.values():
                result = traverse(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = traverse(item)
                if result:
                    return result
        return ""  # Return empty string if key not found

    return traverse(response)


def find_max_duration(response):
    max_duration = 0

    def traverse(data):
        nonlocal max_duration

        if isinstance(data, dict):
            if 'duration' in data:
                max_duration = max(max_duration, data['duration'])
            for value in data.values():
                traverse(value)
        elif isinstance(data, list):
            for item in data:
                traverse(item)

    traverse(response)

    return format_duration(max_duration)


# xvideos.com, pornhub.com
def getXV_DLinkInfo(info, site):
    # Iterate through entries to find the desired format
    if "pornhub" in site:
        format_id = "720p"
    else:
        format_id = "mp4-high"

    if 'formats' in info:
        for format_info in info['formats']:
            if format_info.get('protocol') == 'https' and format_info.get('format_id') == format_id:
                return [format_info.get('url')]

    else:  # gets d link for single post tweet
        direct_link = info['url']  # Get the direct link
        return [direct_link]


# youtube.com
def getYT_DLinkInfo(info):
    if 'formats' in info:
        highest_quality_item = None
        # link is youtube
        for items in info['formats']:
            if 'asr' in items and items['audio_channels'] == 2:
                if highest_quality_item is None or items['quality'] > highest_quality_item['quality']:
                    highest_quality_item = items
        if highest_quality_item:
            return [highest_quality_item['url']]
    else:
        direct_link = info['url']  # Get the direct link
        return [direct_link]


# twitter.com
def getTW_DLinkInfo(info):
    # Iterate through entries to find the desired format
    list_dlink = []
    if 'entries' in info:  # multi post tweet, gets d link for all video posts
        for entry in info['entries']:
            for fmt in entry['formats']:
                if 'http' in fmt['format_id']:
                    if fmt['resolution'] != "audio only":
                        list_dlink.append(fmt['url'])

        highest_resolution = 0
        highest_resolution_urls = []

        for url in list_dlink:
            # Extract resolution from URL
            resolution_str = url.split('/')[-2]
            resolution = int(
                resolution_str.split('x')[1])  # Extract the second part of resolution e.g., '720' from '720x1280'

            # If the current URL has higher resolution, clear the list and add the current URL
            if resolution > highest_resolution:
                highest_resolution = resolution
                highest_resolution_urls = [url]
            # If the current URL has the same resolution as the highest resolution, add it to the list
            elif resolution == highest_resolution:
                highest_resolution_urls.append(url)

        return highest_resolution_urls
    else:  # gets d link for single post tweet
        direct_link = info['url']  # Get the direct link
        return [direct_link]


# instagram.com
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
        return [max_url]

    else:
        direct_link = info['url']  # Get the direct link
        return [direct_link]


def handle_exception(info):
    try:
        print("In handle exception")
        # Implement your logic to handle the exception here
        result = {"videoURL": print_nested_urls(info),
                  "title": extract_title(info)[0],
                  "thumbnail": extract_thumbnail(info),
                  "realTitle": extract_title(info)[1],
                  "uploader": find_uploader(info),
                  "duration": find_max_duration(info)
                  }
        return result
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None


def extract_title(data):
    list_title = []
    if "title" in data:
        title = data["title"]

        cleaned_title = re.sub(r'[^a-zA-Z0-9]', ' ', title)
        rand = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        list_title.append(cleaned_title + "_" + rand)
        list_title.append(title)
        return list_title
    else:
        return [''.join(random.choices(string.ascii_letters + string.digits, k=6)), "video.mp4"]


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


async def telegram_bot(message):
    TELEGRAM_API_KEY = '7044476456:AAHXNCdnterlKZDhKVIhWXy6ke5QD5hwhxs'
    TELEGRAM_USERID = '1260787366'
    api_key = TELEGRAM_API_KEY
    user_id = TELEGRAM_USERID
    bot = telegram.Bot(token=api_key)

    await bot.send_message(chat_id=user_id, text=message)


@app.route('/api/downloaderHome/<string:params>')
@limiter.limit("10/minute")  # Apply the global rate limit to this route
def downloaderHome(params):
    print("Welcome to downloader")

    params = params.split(";")
    user_id = params[0]
    user_sign = params[1]
    url = decode_url_safe_base64URL(params[2])
    try:
        result = downloader(user_id, user_sign, str(url))
        print("RESULT ", result)

        return jsonify(result)

    except Exception as e:
        print(e)
        print(traceback.format_exc())

        return jsonify({"error": str(e)}), 250
