import requests
import re
import os.path
import sys


LINKS_PATTERN = re.compile("<a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a>")
def extract_anchors(content):
    result = LINKS_PATTERN.findall(content)
    result_filtered = [(text.strip(), url) for url, text in result
                        if url.startswith("dir") or "download?" in url]
    return result_filtered


def filter_for_links(anchors):
    return [url for text, url in anchors
            if text != "." and text != ".." and url.startswith("dir")]


def filter_for_medias(anchors):
    return [(text, link) for text, link in anchors
            if "download?" in link]


def download_media(url, destination_folder, media_name):
    media_path = os.path.join(destination_folder, media_name)
    if os.path.exists(media_path):
        print("Skipped " + media_name)
        return
    r = requests.get(url, stream=True)
    total_length = r.headers.get('content-length')
    with open(media_path, "wb") as f:
        if total_length is None: # no content length header
            f.write(r.content)
        else:
            total_length = int(total_length)
            dl = 0
            for chunk in r.iter_content(1024):
                dl += len(chunk)
                f.write(chunk)
                downloaded_perc = (dl / total_length) * 100
                print("\rDownloading %s [%.2f%%]" % (media_name, downloaded_perc), end="")
    print("\rDownloaded %s %s" % (media_name, " " * 10))


def download_images_recursively(url, destination_folder):
    try:
        r = requests.get(url)
    except requests.HTTPError as e:
        print(e.reason)
        return
    if r.status_code != 200:
        return
    anchors = extract_anchors(r.text)
    sub_pages = filter_for_links(anchors)
    medias = filter_for_medias(anchors)
    for media_name, media_url in medias:
        download_media(media_url, destination_folder, media_name)
    for sub_url in sub_pages:
        download_images_recursively(BASE_URL + sub_url, destination_folder)


BASE_URL = "http://ezshare.card/"
ROOT_URL = BASE_URL + "dir?dir=A:%5CDCIM"

destination_folder = '.'

if __name__ == "__main__":
    if len(sys.argv) > 1:
        destination_folder = sys.argv[1]

    download_images_recursively(ROOT_URL, destination_folder)
