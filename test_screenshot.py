from selenium import webdriver
from selenium.webdriver.edge.options import Options
import time

options = Options()
options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
options.add_argument("--ignore-certificate-errors")

driver = webdriver.Edge(options=options)
driver.get("http://slither.io")
time.sleep(5)

driver.save_screenshot("screenshot.png")
print("Screenshot gespeichert!")

driver.quit()