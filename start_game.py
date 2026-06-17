from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import time

options = Options()
options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
options.add_argument("--ignore-certificate-errors")

driver = webdriver.Edge(options=options)
driver.get("http://slither.io")
time.sleep(5)

nickname_feld = driver.find_element(By.ID, "nick")
nickname_feld.clear()
nickname_feld.send_keys("Der_Frido")

time.sleep(1)

play_button = driver.find_element(By.ID, "playh")
play_button.click()
print("Play geklickt!")

time.sleep(8)  # warten bis Spiel geladen
driver.save_screenshot("ingame.png")
print("Screenshot gemacht!")

input("Enter zum schliessen...")
driver.quit()