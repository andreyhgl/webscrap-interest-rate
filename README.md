![Python](https://img.shields.io/badge/python-3670A0?logo=python&logoColor=ffdd54)

# README

Extract the current mortgage interest rate (swedbank) and save if the rate is adjusted.

![interest_rate](images/lineplot.png)

```sh
# project tree

project/
|-- .github/workflows/schedule.yml
|-- bin/
|   |-- lineplot.py
|   ´-- webscrape.py
|-- env/requirements.txt
|-- img/lineplot.png
|-- swedbank.csv
`-- README.md
```

---

## Setup

The `requirements.txt` contains all the libraries used for the project. 

```sh
# To generate requirements.txt

pip3 install pipreqs
python -m pipreqs.pipreqs env/requirements.txt
```

The `webscrape.py` extract the current mortgage interest rate and saves it into `swedbank.csv`, that can be used for further analysis.

The `.github/workflows/schedule.yml` checks the homepage every work day.

> Github Actions has a built in function for schedule executable actions; CI/CD (Continous Integration and Continuous Deployment).

```sh
# generate the file

mkdir -p .github/workflows
touch .github/workflows/schedule.yml
```

Paste the the following into it:

```yml
name: check homepage

on:
  schedule:
    - cron: '0 13 * * 1-5' # mon - fri @ 13:00 PM (stockholm)

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
        cache: 'pip' # caching pip dependencies
    - run: pip install -r requirements.txt
    
    - name: check homepage
      run: |
        python webscrape.py
```

