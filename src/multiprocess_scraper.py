from collections import defaultdict
from multiprocessing import Manager, Process
from multiprocessing.managers import ListProxy
from os import path, readlink
from shutil import rmtree
from time import sleep

from tqdm import tqdm

import json5
import json
from colorama import Fore, Style

import theme_scraper

ANALYZE_FAILED_ONLY = True

SCRAPE_METADATA = True
NUM_SCRAPERS = 8
ANALYZE_VSIX = True
NUM_VSIX_ANALYZERS = 12
LOG_METADATA = True
LOG_VSIX = True

HEADLESS = True
LOGLEVEL = 3

PATH = readlink(__file__) if path.islink(__file__) else __file__
SRC_DIR = path.dirname(PATH)
TOP_DIR = path.dirname(SRC_DIR)
LOG_DIR = path.join(TOP_DIR, "log")
DATA_DIR = path.join(TOP_DIR, "data")
TEMP_DIR = path.join(TOP_DIR, "temp")

error = (
    lambda x: print(Fore.RED + x + Style.RESET_ALL) if LOGLEVEL > 0 else lambda _: None
)
warn = (
    lambda x: print(Fore.YELLOW + x + Style.RESET_ALL)
    if LOGLEVEL > 1
    else lambda _: None
)
info = (
    lambda x: print(Fore.CYAN + x + Style.RESET_ALL) if LOGLEVEL > 2 else lambda _: None
)
debug = print if LOGLEVEL > 3 else lambda _: None


def format_failed_jobs(urls_failed: ListProxy) -> dict[str, list[str]]:
    out = defaultdict(list)
    for url in urls_failed:
        out[url["reason"]].append(url["url"])
    return out


def scrape(urls: ListProxy, results: ListProxy):
    with theme_scraper.WebdriverContext(headless=HEADLESS) as driver:
        while len(urls) > 0:
            try:
                url = urls.pop(0)
                results.append(theme_scraper.analyze_page(driver, url))
            except Exception as e:
                error(f"[Scraper] Ran into {e}...")


def analyze_vsix(
    urls_download: ListProxy,
    color_themes: ListProxy,
    urls_failed: ListProxy,
    download_dir: str = TEMP_DIR,
):
    with theme_scraper.WebdriverContext(
        downloads_dir=download_dir, headless=HEADLESS
    ) as driver:
        while len(urls_download) > 0:
            url = urls_download.pop(0)
            results = theme_scraper.download_vsix(
                driver, url, downloads_dir=download_dir
            )
            if not results.err:
                analysis_results = theme_scraper.analyze_vsix(results.fpath)
                if not analysis_results.err:
                    debug(f"[Analyzer] Analyzed: {url}")
                    color_themes.extend(analysis_results.analysis)
                else:
                    debug(
                        f"[Analyzer] Could not analyze {results.fpath}, adding to failed list"
                    )
                    urls_failed.append(
                        {"url": url, "reason": f"[Analysis] {analysis_results.err}"}
                    )

                rmtree(results.fpath, ignore_errors=True)
            else:
                debug(f"[Analyzer] Failed to download {url}, adding to failed list")
                urls_failed.append({"url": url, "reason": f"[Download] {results.err}"})


def log(urls: ListProxy, results: ListProxy):
    with tqdm(total=len(urls), desc="[Metadata]     ", position=0) as pbar:
        previous_len = len(urls)
        while len(urls) > 0:
            with open(path.join(LOG_DIR, "log.json"), "w") as f:
                json.dump(
                    list(results), f, indent=2, cls=theme_scraper.EnhancedJSONEncoder
                )
            pbar.update(previous_len - len(urls))
            previous_len = len(urls)
            sleep(3)


def log_vsix(urls_download: ListProxy, color_themes: ListProxy, urls_failed: ListProxy):
    with tqdm(total=len(urls_download), desc="[VSIX Analyzer]", position=1) as pbar:
        previous_len = len(urls_download)
        while len(urls_download) > 0:
            with open(path.join(LOG_DIR, "vsix_log.json"), "w") as f:
                json5.dump(
                    list(color_themes),
                    f,
                    indent=2,
                    cls=theme_scraper.EnhancedJSONEncoder,
                    quote_keys=True,
                    trailing_commas=False,
                )
            with open(path.join(LOG_DIR, "failed_vsix_log.json"), "w") as f:
                json5.dump(
                    format_failed_jobs(urls_failed),
                    f,
                    indent=2,
                    cls=theme_scraper.EnhancedJSONEncoder,
                    quote_keys=True,
                    trailing_commas=False,
                )
            pbar.update(previous_len - len(urls_download))
            previous_len = len(urls_download)
            sleep(3)


if __name__ == "__main__":
    rmtree(TEMP_DIR, ignore_errors=True)
    theme_urls = []

    # For retrying failed downloads:
    if ANALYZE_FAILED_ONLY:
        with open(path.join(DATA_DIR, "failed_vsix.json"), "r") as failed_file:
            failed_dict = json.load(failed_file)
            for k in failed_dict.keys():
                if k != "[Analysis] Not a theme extension":
                    theme_urls.extend(failed_dict[k])
    else:
        with open(path.join(DATA_DIR, "theme_urls.json"), "r") as theme_file:
            theme_urls: list[str] = json.load(theme_file)
            assert type(theme_urls) == list

    with Manager() as man:
        metadata_results = man.list()
        themes = man.list()
        jobs = man.list(theme_urls.copy())
        download_jobs = man.list(theme_urls.copy())
        failed_download_jobs = man.list()
        processes = []

        # Create workers
        if SCRAPE_METADATA and not ANALYZE_FAILED_ONLY:
            for i in range(NUM_SCRAPERS):
                p = Process(target=scrape, args=(jobs, metadata_results))
                p.start()
                processes.append(p)

            # Create logger
            if LOG_METADATA:
                l = Process(target=log, args=(jobs, metadata_results))
                l.start()
                processes.append(l)

        # Analyze VSIX
        if ANALYZE_VSIX:
            for i in range(NUM_VSIX_ANALYZERS):
                p = Process(
                    target=analyze_vsix,
                    args=(
                        download_jobs,
                        themes,
                        failed_download_jobs,
                        path.join(TEMP_DIR, f"analyzer_{i}"),
                    ),
                )
                p.start()
                processes.append(p)

            # Create logger
            if LOG_VSIX:
                l = Process(
                    target=log_vsix, args=(download_jobs, themes, failed_download_jobs)
                )
                l.start()
                processes.append(l)

        for p in processes:
            p.join()

        if SCRAPE_METADATA and LOG_METADATA and not ANALYZE_FAILED_ONLY:
            with open(path.join(DATA_DIR, "theme_metadata.json"), "w") as metadata_file:
                json.dump(
                    list(metadata_results),
                    metadata_file,
                    indent=2,
                    cls=theme_scraper.EnhancedJSONEncoder,
                )

        if ANALYZE_VSIX and LOG_VSIX:
            new_theme_list = list(themes)
            if ANALYZE_FAILED_ONLY:
                with open(path.join(DATA_DIR, "themes.json"), "r") as theme_input_file:
                    new_theme_list.extend(json.load(theme_input_file))

            with open(path.join(DATA_DIR, "themes.json"), "w") as theme_output_file:
                json.dump(
                    new_theme_list,
                    theme_output_file,
                    indent=2,
                    cls=theme_scraper.EnhancedJSONEncoder,
                )

            with open(
                path.join(DATA_DIR, "failed_vsix.json"), "w"
            ) as failed_output_file:
                json.dump(
                    format_failed_jobs(failed_download_jobs),
                    failed_output_file,
                    indent=2,
                    cls=theme_scraper.EnhancedJSONEncoder,
                )
