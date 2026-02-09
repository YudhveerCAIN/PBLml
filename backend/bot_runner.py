from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

# Configure Chrome
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")

from selenium.webdriver.chrome.service import Service

driver = webdriver.Chrome(service=Service(), options=options)


try:
    # Open your tracking website
    driver.get("http://127.0.0.1:5500/index.html")

    # Wait very little (bots are fast)
    time.sleep(1)

    # Type instantly (bot-like)
    input_box = driver.find_element(By.TAG_NAME, "input")
    input_box.send_keys("bottypingtest")
    time.sleep(0.2)

    # Repetitive clicking
    box = driver.find_element(By.CLASS_NAME, "box")
    for _ in range(10):
        box.click()
        time.sleep(0.1)

    # Linear scrolling
    for _ in range(15):
        driver.execute_script("window.scrollBy(0, 100);")
        time.sleep(0.05)

    # Very short session
    time.sleep(1)

finally:
    driver.quit()
