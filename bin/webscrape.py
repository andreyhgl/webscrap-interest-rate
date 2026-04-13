#!/usr/bin/env python3

from bs4 import BeautifulSoup
import urllib3
import pandas as pd
import datetime
import os
import numpy as np

url = "https://www.swedbank.se/privat/boende-och-bolan/bolanerantor.html"

print(f"\n ~~~ scraping URL ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
print(f" {url}\n")

# Extract the html page
page = urllib3.request("GET", url)
soup = BeautifulSoup(page.data, 'html.parser')

print(f"\n Status code: {page.status}\n")
print(f" ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")

# locate the 'td' element
interests = soup.find_all('td')

# extract interest rates
values = []
for i in range(2, 33, 3): 
  val = interests[i].text

  # remove white space & extra characters
  val = val.replace("%", "")
  val = val.replace("\n", "")
  val = val.replace(",", ".")
  val = val.strip()
  val = float(val)
  
  values.append(val)

# date + values
date = [str(datetime.date.today())]
dat = pd.DataFrame([date + values])

# column names
colnames = ['date', '3m', '1y', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y']
dat.columns = colnames

def save_table(filename, dat):
    
  if not os.path.isfile(filename):
      
    # First time file is generated, include the header
    print(f"file {filename} is not found, generating one...")
    dat.to_csv(filename, header = True, index = False)
  
  else:

    # Extract the last row from database (exclude the date), make into array
    df = pd.read_csv(filename)
    last_row = np.array(df.iloc[-1, 1:])
    data = np.array(dat.iloc[:, 1:])

    test = last_row == data

    # if value is different, append to the csv
    if not test.all():
      print(f"updating file {filename}...")
      dat.to_csv(filename, header = False, index = False, mode = 'a')
    else:
      print(f"\nnothing to update in file {filename}\n\n")
      print(f"Today's interests rates are:\n{dat}")

filename = 'swedbank.csv'
save_table(filename, dat)