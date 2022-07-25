import json
import plistlib
from dataclasses import asdict, dataclass, is_dataclass
from glob import glob
from os import path, remove
from pprint import pprint
from time import sleep, time
from typing import Any, Optional
from zipfile import ZipFile

import json5
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PAGELOAD_TIMEOUT = 10
DOWNLOAD_TIMEOUT = 60

# def parse_xml_dict(xml_dict: dict) -> dict:
#     for k in xml_dict['key']:
#     return xml_dict

# def tmtheme_to_json(tmtheme: dict) -> dict:
#     if 'plist' in tmtheme.keys() and 'dict' in tmtheme['plist'].keys():
#         out = tmtheme['plist']['dict']

#         return out
#     return tmtheme


def filter_chars(text: str, filter_chars: list[str]) -> str:
    return "".join([c for c in text if c not in filter_chars])


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


class WebdriverContext:
    def __init__(self, downloads_dir=None, headless=True):
        self.headless = headless
        self.downloads_dir = downloads_dir

    def __enter__(self):
        options = Options()
        options.headless = self.headless
        options.add_argument("--log-level=3")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        if self.downloads_dir:
            prefs = {
                "download.default_directory": self.downloads_dir,
                "safebrowsing.disable_download_protection": True,
            }
            options.add_experimental_option("prefs", prefs)
            # options.add_argument(f"download.default_directory={self.downloads_dir}")
        self.driver = webdriver.Chrome(options=options)
        return self.driver

    def __exit__(self, exc_type, exc_value, traceback):
        self.driver.quit()


@dataclass
class Theme:
    url: str
    name: str
    author: str
    verified: bool
    num_installs: int
    num_ratings: int
    average_rating: float
    description: str
    price: str
    categories: list[str]
    tags: list[str]
    repository: str | None


def analyze_page(driver: webdriver.Chrome, url: str) -> Theme:
    driver.get(url)
    categories_and_tags = []
    start = time()
    while (time() - start) < PAGELOAD_TIMEOUT:
        sleep(0.1)
        categories_and_tags = driver.find_elements(
            by=By.CSS_SELECTOR, value="a.meta-data-list-link"
        )
        if len(categories_and_tags) > 0:
            break
    repo_els = driver.find_elements(by=By.LINK_TEXT, value="Repository")
    if len(repo_els) > 0:
        repo_url = repo_els[0].get_attribute("href")
    else:
        repo_url = None
    installs_els = driver.find_elements(by=By.CSS_SELECTOR, value="span.installs-text")
    if len(installs_els) > 0:
        num_installs = int(
            installs_els[0]
            .text.replace(",", "")
            .replace(" install", "")
            .replace("s", "")
            .strip()
        )
    else:
        num_installs = 0
    return Theme(
        url=url,
        name=driver.find_element(by=By.CSS_SELECTOR, value="span.ux-item-name").text,
        author=driver.find_element(
            by=By.CSS_SELECTOR, value="a.ux-item-publisher-link"
        ).text,
        verified=driver.find_elements(
            by=By.CSS_SELECTOR, value="div.verified-domain-icon"
        )
        != [],
        num_installs=num_installs,
        num_ratings=int(
            driver.find_element(by=By.CSS_SELECTOR, value="span.ux-item-rating-count")
            .text.replace(",", "")
            .replace("(", "")
            .replace(")", "")
            .strip()
        ),
        average_rating=float(
            driver.find_element(by=By.CSS_SELECTOR, value="span.ux-item-review-rating")
            .get_attribute("title")
            .replace("Average rating:", "")
            .replace("out of 5", "")
            .strip()
        ),
        description=driver.find_element(
            by=By.CSS_SELECTOR, value="div.ux-item-shortdesc"
        ).text,
        price=driver.find_element(
            by=By.CSS_SELECTOR, value="span.item-price-category"
        ).text,
        categories=[
            el.text
            for el in categories_and_tags
            if "Category" in el.get_attribute("aria-label")
        ],
        tags=[
            el.text
            for el in categories_and_tags
            if "Tag" in el.get_attribute("aria-label")
        ],
        repository=repo_url,
    )


@dataclass
class DownloadResults:
    fpath: str
    err: Optional[str] = None


def download_vsix(
    driver: webdriver.Chrome, url: str, downloads_dir=""
) -> DownloadResults:
    name = url.replace("https://marketplace.visualstudio.com/items?itemName=", "")
    driver.get(url)
    start = time()
    but = []
    while (time() - start) < PAGELOAD_TIMEOUT:
        sleep(0.1)
        but = driver.find_elements(by=By.CSS_SELECTOR, value="button.root-47")
        if len(but) > 0:
            but[0].click()
            start = time()
            files = []
            while (time() - start) < DOWNLOAD_TIMEOUT:
                files = glob(path.join(downloads_dir, name) + "*.vsix")
                if len(files) > 0:
                    if len(files) > 1:
                        return DownloadResults(fpath="", err="Multiple files found")
                    folder_path = files[0].replace(".vsix", "")
                    try:
                        with ZipFile(files[0], "r") as zip_ref:
                            zip_ref.extractall(folder_path)
                        remove(files[0])
                    except Exception as e:
                        remove(files[0])
                        return DownloadResults(fpath="", err=str(e).split("'c:")[0])
                    start = time()
                    folder_paths = []
                    while (time() - start) < DOWNLOAD_TIMEOUT:
                        folder_paths = glob(path.join(downloads_dir, name) + "*")
                        if len(folder_paths) > 0:
                            return DownloadResults(fpath=folder_paths[0])
                sleep(0.1)
            return DownloadResults(
                fpath="", err="Download timed out. Try increasing DOWNLOAD_TIMEOUT."
            )

    return DownloadResults(
        fpath="",
        err="No button found. Try increasing PAGELOAD_TIMEOUT or rerunning theme_list_scraper.py.",
    )


@dataclass
class AnalysisResults:
    analysis: list[dict[str, Any]]
    err: Optional[str] = None


def analyze_vsix(full_path: str) -> AnalysisResults:
    out = []
    for _ in range(5):
        try:
            with open(
                path.join(full_path, "extension", "package.json"),
                "r",
                encoding="utf8",
            ) as f:
                package_text = f.read()
                package = json5.loads(package_text)
                if (
                    "contributes" in package.keys()
                    and "themes" in package["contributes"].keys()
                ):
                    # uiTheme
                    for p in filter(
                        lambda p: "path" in p.keys(), package["contributes"]["themes"]
                    ):
                        t = p["path"].replace("./", "")
                        u = p["uiTheme"] if "uiTheme" in p.keys() else ""
                        # print(
                        #     f"\tin for loop, opening {path.join(full_path, 'extension', t)}"
                        # )
                        with open(
                            path.join(full_path, "extension", t),
                            "rb",
                        ) as f:
                            if "displayName" in package.keys():
                                displayName = package["displayName"]
                            else:
                                displayName = full_path
                            if t[-4:] == "json":
                                text = f.read()
                                out.append(
                                    {
                                        "name": displayName,
                                        "theme": {
                                            "uiTheme": u,
                                            "path": t,
                                            "format": "json",
                                            "contents": json5.loads(text),
                                        },
                                    }
                                )
                            elif t[-7:].lower() == "tmtheme":
                                text = f.read()
                                out.append(
                                    {
                                        "name": displayName,
                                        "theme": {
                                            "uiTheme": u,
                                            "path": t,
                                            "format": "tmTheme",
                                            "contents": plistlib.loads(text),
                                        },
                                    }
                                )
                            else:
                                # TODO: verbosity levels
                                print(f"Skipping {t}, not a json or tmTheme file")
                                return AnalysisResults(
                                    analysis=out, err="Unknown file type"
                                )
                else:
                    # print(
                    #     f"[analyze_vsix] {full_path} is not a theme extension after all"
                    # )
                    return AnalysisResults(analysis=out, err="Not a theme extension")
            break
        except Exception as e:
            return AnalysisResults(analysis=out, err=str(e).split("'c:")[0])
    return AnalysisResults(analysis=out, err=None)


if __name__ == "__main__":
    woptions = Options()
    woptions.headless = True
    wdriver = webdriver.Chrome(options=woptions)

    pprint(
        analyze_page(
            wdriver,
            "https://marketplace.visualstudio.com/items?itemName=whizkydee.material-palenight-theme",
        )
    )
    pprint(
        analyze_page(
            wdriver,
            "https://marketplace.visualstudio.com/items?itemName=monokai.theme-monokai-pro-vscode",
        )
    )

    wdriver.quit()
