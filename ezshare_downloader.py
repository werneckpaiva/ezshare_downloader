import requests
import re
import os.path
import sys
import threading
import queue
from typing import Final, List, Tuple

LINKS_PATTERN = re.compile("<a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a>")
def extract_anchors(content:str) ->List[Tuple[str, str]]:
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


def should_download_media(url:str, media_name:str, destination_folder:str)->bool:
    media_path = os.path.join(destination_folder, media_name)
    return not os.path.exists(media_path)

def download_media(url:str, media_name:str, destination_folder:str) -> None:
    r = requests.get(url, stream=True)
    total_length = r.headers.get('content-length')
    media_path = os.path.join(destination_folder, media_name)
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

def media_downloader_thread(medias_to_download:queue.Queue, destination_folder:str) -> None:
    while not medias_to_download.empty():
        media_url, media_name  = medias_to_download.get()
        download_media(media_url, media_name, destination_folder)
        medias_to_download.task_done()

def download_images_recursively(url:str, destination_folder:str) -> None:
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
    medias_to_download = queue.Queue(len(medias))
    for media_name, media_url in medias:
        if should_download_media(media_url, media_name, destination_folder):
            medias_to_download.put((media_url, media_name))

    if len(medias) > 0:
        print("Total medias:", len(medias))
        print("Medias to download:", medias_to_download.qsize())

        for _ in range(NUM_THREADS):
            threading.Thread(target=media_downloader_thread, args=(medias_to_download, destination_folder,)).start()

        medias_to_download.join()

    for sub_url in sub_pages:
        download_images_recursively(BASE_URL + sub_url, destination_folder)

NUM_THREADS:Final[int] = 3
BASE_URL:Final[str] = "http://192.168.4.1/" # "http://ezshare.card/"
ROOT_URL:Final[str] = BASE_URL + "dir?dir=A:%5CDCIM"

destination_folder:str = '.'

if __name__ == "__main__":
    if len(sys.argv) > 1:
        destination_folder = sys.argv[1]

    download_images_recursively(ROOT_URL, destination_folder)
