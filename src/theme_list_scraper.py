## Resources:
# https://medium.com/ymedialabs-innovation/web-scraping-using-beautiful-soup-and-selenium-for-dynamic-page-2f8ad15efe25
# https://marketplace.visualstudio.com/search?target=VSCode&category=Themes&sortBy=Installs
# https://realpython.com/modern-web-automation-with-python-and-selenium/

import json
from os import path, readlink
from time import sleep, time
from typing import Callable

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

import theme_scraper

TIMEOUT = 120  # seconds
PATH = readlink(__file__) if path.islink(__file__) else __file__
SRC_DIR = path.dirname(PATH)
TOP_DIR = path.dirname(SRC_DIR)
DATA_DIR = path.join(TOP_DIR, "data")

get_html: Callable[[str], BeautifulSoup] = lambda url: BeautifulSoup(
    requests.get(url).text, "html.parser"
)

num_installs: Callable[[BeautifulSoup], str] = (
    lambda soup: soup.find_all(class_="installs-text")[0]
    .text.replace(",", "")
    .replace(" installs", "")
    .strip()
)


def get_all_themes(driver: webdriver.Chrome) -> list:
    driver.get(
        "https://marketplace.visualstudio.com/search?target=VSCode&category=Themes&sortBy=Installs"
    )
    window_height = 0
    keep_scrolling = True
    els = []
    n_iter = 0
    while keep_scrolling:
        body = driver.find_element(by=By.TAG_NAME, value="body")
        start = time()
        while time() - start < TIMEOUT:
            body.send_keys(Keys.PAGE_DOWN)
            new_height = driver.execute_script(
                "return document.documentElement.scrollHeight"
            )
            if new_height > window_height:
                window_height = new_height
                break
            sleep(0.05)
        else:
            keep_scrolling = False
        els = driver.find_elements(
            by=By.CLASS_NAME, value="gallery-item-card-container"
        )
        if n_iter % 10 == 0:
            print(f"Scraped {len(els)} themes")
        n_iter += 1

    return [el.get_attribute("href") for el in els]


def scrape_list():
    with theme_scraper.WebdriverContext(headless=True) as driver:
        theme_links = get_all_themes(driver)
        with open(path.join(DATA_DIR, "theme_urls.json"), "w") as f:
            json.dump(theme_links, f, indent=2)

        # test_html = get_item("https://marketplace.visualstudio.com/items?itemName=Equinusocio.vsc-community-material-theme")
        # print(num_installs(test_html))
        # print(test_html.find_all("button", text="Download Extension"))


if __name__ == "__main__":
    scrape_list()
