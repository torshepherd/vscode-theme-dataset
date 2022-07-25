# VS Code color theme dataset

This repo is the source code used to generate https://drive.google.com/drive/folders/1iXjZu1-WuOkGNENo4MS0cEQte7C36Qm6?usp=sharing.

Hosted on Drive because Github wouldn't let me push the dataset here lol.

## Details

The dataset contains

1. a list of metadata about all the themes listed on https://marketplace.visualstudio.com/search?target=VSCode&category=Themes&sortBy=Installs in both `json` and `csv` format
1. a list of theme color settings listed on https://marketplace.visualstudio.com/search?target=VSCode&category=Themes&sortBy=Installs in both `json` and `csv` format
1. a list of urls of all the themes listed on https://marketplace.visualstudio.com/search?target=VSCode&category=Themes&sortBy=Installs in `json` format
1. a list of failed scrapings from https://marketplace.visualstudio.com/search?target=VSCode&category=Themes&sortBy=Installs in `json` format, for me to maybe fix later

At the time of writing, the list is approximately ~8k themes.

## Why

I'm working on some extensions to generate color themes automatically, and I wanted to characterize the entire set of existing themes to try and pull some insights about how people like their colors.
