from os import environ
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import urllib.parse
import time
from random import randint
from fastapi import FastAPI
from pydantic import BaseModel

SELENIUM_URLS = environ["SELENIUM_URLS"].split(",")
if len(SELENIUM_URLS) == 0:
    raise Exception("No Selenium URLs provided")

# else create drivers
options = webdriver.FirefoxOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
DRIVERS = []

def clickable(driver, element: str) -> None:
    """Click on an element if it's clickable using Selenium."""
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.XPATH, element))).click()
    except Exception:  # Some buttons need to be visible to be clickable,
        driver.execute_script(  # so JavaScript can bypass this.
            'arguments[0].click();', visible(driver, element))

def visible(driver, element: str):
    """Check if an element is visible using Selenium."""
    return WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, element)))

def send_keys(driver, element: str, keys: str) -> None:
    """Send keys to an element if it's visible using Selenium."""
    try:
        visible(driver, element).send_keys(keys)
    except Exception:  # Some elements are not visible but are present.
        WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.XPATH, element))).send_keys(keys)

def login(driver):
    if visible(driver, '//button[contains(@dl-test, "menu-account-out-btn")]').text == 'Login':
        url = 'https://www.deepl.com/translator#en/de'
        # print("translate: %s"%url)
        driver.get(url)
        # if visible('//button[contains(text(), "Login")]'):
        
        # if clickable('//input[contains(, "Login")]'):
        clickable(driver, '//button[contains(@dl-test, "menu-account-out-btn")]')
        send_keys(driver, '//input[contains(@dl-test, "menu-login-username")]', environ["DEEPL_USERNAME"])
        send_keys(driver, '//input[contains(@dl-test, "menu-login-password")]', environ["DEEPL_PASSWORD"])
        clickable(driver, '//button[contains(@dl-test, "menu-login-submit")]')
        time.sleep(2)
        driver.get(url + "/#en/de/fish")
        time.sleep(1)
        
        
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    global DRIVERS
    # for host in SELENIUM_URLS: # cant do async for now, use first one only
    driver = webdriver.Remote(SELENIUM_URLS[1] + "/wd/hub", options=options)
    DRIVERS.append([driver, True]) # 2nd one is ready true false
    # log in 
    url = 'https://www.deepl.com/translator#en/de'
    driver.get(url)
    login(driver)

def findReadyDriver():
    global DRIVERS
    for _ in range(len(DRIVERS)):
        i = randint(0, len(DRIVERS) - 1)
        if DRIVERS[i][1]:
            return i
    # no driver found
    return None



class TranslationRequest(BaseModel):
    text: str
    sourceLanguage: str = "en"
    targetLanguage: str = "de"
    
class TranslationResponse(BaseModel):
    text: str
    driver_used: str

def getTranslation(text, sourceLang = "en", targetLang = "de"):
    global DRIVERS
    # if len(text) > 5000:
    #     raise Exception("Text too long, needs to be 5000 chars max")
    # find a driver that is ready
    driverpos = findReadyDriver()
    if driverpos is None:
        raise Exception("No driver available")
    driver = DRIVERS[driverpos][0]
    DRIVERS[driverpos][1] = False # set to false (in progress)
    
    try:
        # Define text to translate
        urlv = urllib.parse.quote(text, safe='')
        url = 'https://www.deepl.com/translator#%s/%s/%s'% (sourceLang, targetLang, urlv)
        # print("translate: %s"%url)
        driver.get(url)

        while True:
            element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, '//*[contains(concat( " ", @class, " " ), concat( " ", "lmt__target_textarea", " " ))]')))
            if(element.get_attribute('value') != ''):
                time.sleep(.1)
                text_target = element.get_attribute('value')
                break

        #print(text_target)
    except Exception as e:
        driver.quit()
        time.sleep(1) # wait 5 seconds before restarting selenium
        raise
    # driver.quit()
    DRIVERS[driverpos][1] = True # set to false (in progress)
    return text_target, driverpos

@app.post("/", response_model=TranslationResponse)
def getTrans(item: TranslationRequest):
    trans, driverpos = getTranslation(item.text, sourceLang = item.sourceLanguage, targetLang = item.targetLanguage)
    return TranslationResponse(
        text = trans,
        driver_used = driverpos
    )
@app.on_event("shutdown")
def shutdown_event():
    global DRIVERS
    for driver in DRIVERS:
        try:
            driver.shutdown()
        except:
            pass