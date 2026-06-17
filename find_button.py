from selenium import webdriver
from selenium.webdriver.edge.options import Options
import time

options = Options()
options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
options.add_argument("--ignore-certificate-errors")

driver = webdriver.Edge(options=options)
driver.get("http://slither.io")
time.sleep(5)

# Sucht gezielt nach Buttons
buttons = driver.find_elements("tag name", "button")
divs = driver.find_elements("tag name", "div")

print("=== BUTTONS ===")
for b in buttons:
    print(b.get_attribute("id"), "|", b.get_attribute("class"), "|", b.text)

print("=== DIVS mit 'play' ===")
for d in divs:
    if "play" in str(d.get_attribute("id")).lower() or "play" in str(d.get_attribute("class")).lower():
        print(d.get_attribute("id"), "|", d.get_attribute("class"))

input("Enter zum schliessen...")
driver.quit()
