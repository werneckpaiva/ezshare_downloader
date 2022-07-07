import requests
import re
import os.path
import sys
import threading
import queue
from typing import Final, List, Tuple
import tempfile

LINKS_PATTERN = re.compile("<a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a>")
def extract_anchors(content:str) ->List[Tuple[str, str]]:
    result = LINKS_PATTERN.findall(content)
    result_filtered = [(url, text.strip()) for url, text in result
                        if url.startswith("dir") or "download?" in url]
    return result_filtered


def filter_for_links(anchors:List[Tuple[str, str]]) -> List[str]:
    return [url for url, text in anchors
            if text != "." and text != ".." and url.startswith("dir")]


def filter_for_medias(anchors:List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return [(url, text) for url, text in anchors
            if "download?" in url]


def should_download_media(url:str, media_name:str, destination_folder:str)->bool:
    media_path = os.path.join(destination_folder, media_name)
    return not os.path.exists(media_path)

def download_media(url:str, media_name:str, destination_folder:str, download_state:queue.Queue) -> None:
    r = requests.get(url, stream=True)
    total_length = r.headers.get('content-length')
    media_path = os.path.join(destination_folder, media_name)
    # Use temp file to guarantee the file is copied up to the end, when moved to final destination
    with tempfile.NamedTemporaryFile() as temp_fp:
        if total_length is None: # no content length header
            temp_fp.write(r.content)
        else:
            total_length = int(total_length)
            dl = 0
            for chunk in r.iter_content(1024):
                dl += len(chunk)
                temp_fp.write(chunk)
                downloaded_perc = (dl / total_length) * 100
                download_state.put((downloaded_perc, media_name))
        with open(media_path, "wb") as dest_fp:
            dest_fp.write(temp_fp.read())

def media_downloader_thread(medias_to_download:queue.Queue, destination_folder:str, download_state:queue.Queue) -> None:
    while not medias_to_download.empty():
        media_url, media_name  = medias_to_download.get()
        download_media(media_url, media_name, destination_folder, download_state)
        medias_to_download.task_done()

def print_download_state_thread(medias_to_download:List[Tuple[str, str]], download_state:queue.SimpleQueue) -> None:
    all_medias = {media_name for _, media_name in medias_to_download}
    medias_downloaded = set()
    current_medias = {}
    max_str_len = 0
    while medias_downloaded != all_medias:
        perc, media_name = download_state.get()
        if perc < 100:
            current_medias[media_name] = perc
            current_medias_str = " ".join(f"{n}[{p:02.0f}%]" for n, p in current_medias.items())
            max_str_len = max(max_str_len, len(current_medias_str))
            qnt_remaining = len(all_medias) - len(medias_downloaded)
            print(f"\rDownloading {len(current_medias)}/{qnt_remaining}: {current_medias_str} {' ' * (max_str_len - len(current_medias_str))}", end="")
        else:
            current_medias.pop(media_name)
            medias_downloaded.add(media_name)
            print(f"\rDownloaded {media_name} {' ' * max_str_len}")

def parallel_dowload(medias_to_download:List[Tuple[str, str]], destination_folder:str) -> None:
    if len(medias_to_download) == 0:
        return
    medias_to_download_queue = queue.Queue(len(medias_to_download))
    for media in medias_to_download:
        medias_to_download_queue.put(media)

    download_state = queue.SimpleQueue()
    for _ in range(NUM_THREADS):
        threading.Thread(
            target=media_downloader_thread,
            args=(medias_to_download_queue, destination_folder, download_state, )
        ).start()

    threading.Thread(
        target=print_download_state_thread,
        args=(medias_to_download, download_state, )
    ).start()

    try:
        medias_to_download_queue.join()
    except KeyboardInterrupt:
        pass


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
    medias_to_download = [
        (media_url, media_name)
            for media_url, media_name in medias
            if should_download_media(media_url, media_name, destination_folder)
    ]

    if len(medias) > 0:
        print("Total medias:", len(medias))
        print("Medias to download:", len(medias_to_download))
        parallel_dowload(medias_to_download, destination_folder)

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
